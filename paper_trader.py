import logging
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

import ccxt
import numpy as np
import pandas as pd

import config
import data_provider
import storage


logger = logging.getLogger(__name__)

REPORT_FILENAME = "paper_trading_report.csv"
EQUITY_FILENAME = "paper_equity_curve.csv"
OPEN_POSITIONS_FILENAME = "paper_open_positions.csv"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso_utc(dt) -> str:
    if dt is None:
        return _now_utc().isoformat()
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    return str(dt)


def _parse_utc(value) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return _now_utc()


def _output_path(filename: str) -> str:
    return os.path.join(config.OUTPUT_DIR, filename)


@dataclass
class PaperPosition:
    """Representa una posición abierta en paper trading."""

    symbol: str
    direction: str
    entry_price: float
    sl_price: float
    tp_price: float
    units: float
    risk_amount: float
    entry_time: datetime
    timeframe: str
    score: int
    source_signal: str
    exchange_order_id: str
    status: str
    market_type: str = "spot"
    storage_id: int | None = None


class PaperTrader:
    """
    Motor de paper trading conectado a exchange sandbox u offline local.

    Inicializa capital, posiciones abiertas, historial cerrado y curva de equity.
    Si no hay credenciales disponibles opera en modo offline sin llamadas al
    exchange sandbox.
    """

    def __init__(self, exchange_id="kucoin", capital_usdt=1000.0):
        """
        Inicializa el motor de paper trading.

        Parámetros:
            exchange_id: Exchange objetivo para paper trading.
            capital_usdt: Capital inicial simulado en USDT.

        Retorno:
            None. Deja lista la instancia para abrir o actualizar posiciones.
        """
        self.exchange_id = str(exchange_id or "kucoin").lower()
        self.initial_capital_usdt = float(capital_usdt)
        self.capital_usdt = float(capital_usdt)
        self.positions: list[PaperPosition] = []
        self.closed_trades: list[dict] = []
        self.equity_curve: list[dict] = []
        self.exchange = None
        self.mode = "offline"
        self._last_prices: dict[str, float] = {}

        self._connect_exchange()

    def open_position(self, signal: dict) -> PaperPosition | None:
        """
        Abre una posición a partir de una señal del scanner o analyzer.

        Parámetros:
            signal: Dict con symbol, direction, entry_price, sl_price, tp_price,
                score, timeframe y source_signal.

        Retorno:
            PaperPosition creada o None si falla alguna validación.
        """
        signal = signal or {}
        symbol = signal.get("symbol")
        direction = str(signal.get("direction") or "LONG").upper()

        if len(self.positions) >= config.MAX_OPEN_TRADES:
            logger.info("No se abre %s: máximo de posiciones alcanzado", symbol)
            return None
        if any(pos.symbol == symbol and pos.status == "OPEN" for pos in self.positions):
            logger.info("No se abre %s: ya existe posición abierta", symbol)
            return None
        if direction not in ("LONG", "SHORT"):
            logger.warning("No se abre %s: direction inválida %s", symbol, direction)
            return None

        try:
            entry_price = float(signal["entry_price"])
            sl_price = float(signal["sl_price"])
            tp_price = float(signal["tp_price"])
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("No se abre %s: señal incompleta o inválida (%s)", symbol, exc)
            return None

        stop_distance = abs(entry_price - sl_price)
        if not symbol or entry_price <= 0 or sl_price <= 0 or tp_price <= 0 or stop_distance <= 0:
            logger.warning("No se abre %s: precios inválidos en señal", symbol)
            return None

        risk_amount = self.capital_usdt * config.RISK_PER_TRADE_PCT
        units = risk_amount / max(stop_distance, 1e-8)
        order_id = self._create_entry_order(symbol, direction, units, entry_price)
        if order_id is None:
            return None

        position = PaperPosition(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            sl_price=sl_price,
            tp_price=tp_price,
            units=units,
            risk_amount=risk_amount,
            entry_time=_now_utc(),
            timeframe=str(signal.get("timeframe") or ""),
            score=int(signal.get("score") or 0),
            source_signal=str(signal.get("source_signal") or "SPOT"),
            exchange_order_id=str(order_id),
            status="OPEN",
            market_type=str(signal.get("market_type") or "spot"),
        )
        self.positions.append(position)
        self._last_prices[symbol] = entry_price
        self._snapshot_equity()
        self._save_report()
        logger.info("Posición paper abierta: %s %s %.8f units", direction, symbol, units)
        return position

    def update_positions(self) -> list[dict]:
        """
        Actualiza precios, cierra posiciones que tocaron SL/TP y guarda equity.

        Parámetros:
            None.

        Retorno:
            Lista de dicts con los trades cerrados durante este update.
        """
        closed = []
        for position in list(self.positions):
            current_price = self._get_current_price(position.symbol)
            if current_price is None:
                logger.warning("No se pudo actualizar precio de %s", position.symbol)
                continue

            self._last_prices[position.symbol] = current_price
            if position.direction == "LONG":
                sl_hit = current_price <= position.sl_price
                tp_hit = current_price >= position.tp_price
            else:
                sl_hit = current_price >= position.sl_price
                tp_hit = current_price <= position.tp_price

            if sl_hit or tp_hit:
                reason = "SL" if sl_hit else "TP"
                closed.append(self._close_position(position, reason))

        self._snapshot_equity()
        self._save_report()
        return closed

    def _close_position(self, pos: PaperPosition, reason: str) -> dict:
        """
        Cierra una posición abierta y calcula PnL neto.

        Parámetros:
            pos: Posición abierta a cerrar.
            reason: Motivo de cierre, "TP", "SL" o "MANUAL".

        Retorno:
            Dict con todos los campos del trade cerrado.
        """
        reason = str(reason or "MANUAL").upper()
        exit_price = self._exit_price_for_reason(pos, reason)
        self._create_close_order(pos)

        if pos.direction == "LONG":
            pnl = pos.units * (exit_price - pos.entry_price)
        else:
            pnl = pos.units * (pos.entry_price - exit_price)

        fee = (
            pos.units * pos.entry_price * config.FEE_PCT
            + pos.units * exit_price * config.FEE_PCT
        )
        net_pnl = pnl - fee
        r_multiple = net_pnl / pos.risk_amount if pos.risk_amount else 0.0
        self.capital_usdt += net_pnl

        status = {
            "TP": "CLOSED_TP",
            "SL": "CLOSED_SL",
            "MANUAL": "CLOSED_MANUAL",
        }.get(reason, "CLOSED_MANUAL")
        pos.status = status
        if pos in self.positions:
            self.positions.remove(pos)

        trade = {
            "opened_at": _iso_utc(pos.entry_time),
            "closed_at": _now_utc().isoformat(),
            "symbol": pos.symbol,
            "direction": pos.direction,
            "timeframe": pos.timeframe,
            "score": pos.score,
            "entry_price": pos.entry_price,
            "exit_price": exit_price,
            "sl_price": pos.sl_price,
            "tp_price": pos.tp_price,
            "units": pos.units,
            "risk_amount": pos.risk_amount,
            "net_pnl": net_pnl,
            "r_multiple": r_multiple,
            "reason": reason,
            "capital_after": self.capital_usdt,
        }
        if storage.is_sqlite_backend():
            self._persist_position_open(pos)
            storage.get_storage().close_paper_trade(
                int(pos.storage_id),
                close_price=exit_price,
                pnl=net_pnl,
                pnl_pct=(net_pnl / pos.entry_price * 100 if pos.entry_price else None),
                reason_close=reason,
                closed_at=trade["closed_at"],
                raw=trade,
            )
        self.closed_trades.append(trade)
        self._snapshot_equity()
        self._save_report()
        logger.info(
            "Posición cerrada %s %s por %s: PnL neto %.4f, R %.3f",
            pos.direction,
            pos.symbol,
            reason,
            net_pnl,
            r_multiple,
        )
        return trade

    def close_position_manual(self, symbol: str) -> dict | None:
        """
        Cierra manualmente una posición abierta por símbolo.

        Parámetros:
            symbol: Par a cerrar, por ejemplo "BTC/USDT".

        Retorno:
            Dict del trade cerrado o None si no existe posición abierta.
        """
        for position in list(self.positions):
            if position.symbol == symbol:
                price = self._get_current_price(position.symbol)
                if price is not None:
                    self._last_prices[position.symbol] = price
                return self._close_position(position, "MANUAL")
        logger.info("No hay posición abierta para cierre manual: %s", symbol)
        return None

    def get_summary(self) -> dict:
        """
        Retorna un resumen actual del paper trader.

        Parámetros:
            None.

        Retorno:
            Dict con capital, retorno, win rate, R-multiple, drawdown y modo.
        """
        closed_count = len(self.closed_trades)
        r_values = [float(t.get("r_multiple", 0) or 0) for t in self.closed_trades]
        wins = [r for r in r_values if r > 0]
        losses = [abs(r) for r in r_values if r <= 0]
        win_rate = len(wins) / closed_count * 100 if closed_count else 0.0
        avg_r = float(np.mean(r_values)) if r_values else 0.0
        avg_win_r = float(np.mean(wins)) if wins else 0.0
        avg_loss_r = float(np.mean(losses)) if losses else 0.0
        expectancy_r = (win_rate / 100 * avg_win_r) - ((1 - win_rate / 100) * avg_loss_r)
        equity = self._current_equity()
        retorno_total_pct = (
            (equity - self.initial_capital_usdt) / self.initial_capital_usdt * 100
            if self.initial_capital_usdt
            else 0.0
        )
        max_drawdown_pct = self._max_drawdown_pct()
        sharpe_ratio = self._sharpe_ratio(r_values)

        return {
            "capital_inicial": round(self.initial_capital_usdt, 4),
            "capital_actual": round(equity, 4),
            "retorno_total_pct": round(retorno_total_pct, 4),
            "posiciones_abiertas": len(self.positions),
            "trades_cerrados": closed_count,
            "win_rate": round(win_rate, 4),
            "avg_r_multiple": round(avg_r, 4),
            "expectancy_r": round(expectancy_r, 4),
            "max_drawdown_pct": round(max_drawdown_pct, 4),
            "sharpe_ratio": round(sharpe_ratio, 4) if sharpe_ratio is not None else None,
            "mejor_trade_r": round(max(r_values), 4) if r_values else 0.0,
            "peor_trade_r": round(min(r_values), 4) if r_values else 0.0,
            "modo": self.mode,
            "exchange": self.exchange_id,
        }

    def _save_report(self) -> None:
        """
        Guarda reportes CSV de trades cerrados, equity y posiciones abiertas.

        Parámetros:
            None.

        Retorno:
            None. Crea config.OUTPUT_DIR si no existe.
        """
        if storage.is_sqlite_backend():
            self._save_sqlite_state()
            return

        os.makedirs(config.OUTPUT_DIR, exist_ok=True)
        report_columns = [
            "opened_at",
            "closed_at",
            "symbol",
            "direction",
            "timeframe",
            "score",
            "entry_price",
            "exit_price",
            "sl_price",
            "tp_price",
            "units",
            "risk_amount",
            "net_pnl",
            "r_multiple",
            "reason",
            "capital_after",
        ]
        pd.DataFrame(self.closed_trades, columns=report_columns).to_csv(
            _output_path(REPORT_FILENAME),
            index=False,
        )
        pd.DataFrame(self.equity_curve, columns=["timestamp", "equity"]).to_csv(
            _output_path(EQUITY_FILENAME),
            index=False,
        )
        open_columns = [
            "symbol",
            "direction",
            "entry_price",
            "sl_price",
            "tp_price",
            "units",
            "risk_amount",
            "entry_time",
            "timeframe",
            "score",
            "source_signal",
            "exchange_order_id",
            "status",
            "market_type",
            "storage_id",
        ]
        open_rows = [self._position_to_dict(position) for position in self.positions]
        pd.DataFrame(open_rows, columns=open_columns).to_csv(
            _output_path(OPEN_POSITIONS_FILENAME),
            index=False,
        )

    def _current_equity(self) -> float:
        """
        Calcula capital actual más PnL no realizado de posiciones abiertas.

        Parámetros:
            None.

        Retorno:
            Equity actual estimada.
        """
        unrealized = 0.0
        for position in self.positions:
            unrealized += self._unrealized_pnl(position)
        return self.capital_usdt + unrealized

    @classmethod
    def load_from_report(cls, exchange_id="kucoin", capital_usdt=1000.0) -> "PaperTrader":
        """
        Reconstruye PaperTrader desde los CSVs guardados.

        Parámetros:
            exchange_id: Exchange objetivo del trader reconstruido.
            capital_usdt: Capital inicial a usar si no existe historial.

        Retorno:
            Instancia PaperTrader con trades, equity y posiciones restauradas.
        """
        trader = cls(exchange_id=exchange_id, capital_usdt=capital_usdt)
        if storage.is_sqlite_backend():
            trader._load_from_sqlite()
            return trader

        report_path = _output_path(REPORT_FILENAME)
        equity_path = _output_path(EQUITY_FILENAME)
        open_path = _output_path(OPEN_POSITIONS_FILENAME)

        if os.path.exists(report_path):
            try:
                report_df = pd.read_csv(report_path)
                trader.closed_trades = report_df.to_dict("records")
                if not report_df.empty and "capital_after" in report_df.columns:
                    trader.capital_usdt = float(report_df.iloc[-1]["capital_after"])
            except pd.errors.EmptyDataError:
                trader.closed_trades = []

        if os.path.exists(equity_path):
            try:
                equity_df = pd.read_csv(equity_path)
                trader.equity_curve = equity_df.to_dict("records")
            except pd.errors.EmptyDataError:
                trader.equity_curve = []

        if os.path.exists(open_path):
            try:
                open_df = pd.read_csv(open_path)
                trader.positions = [
                    trader._position_from_dict(row)
                    for row in open_df.to_dict("records")
                    if row.get("status", "OPEN") == "OPEN"
                ]
            except pd.errors.EmptyDataError:
                trader.positions = []

        return trader

    def _save_sqlite_state(self) -> None:
        for position in self.positions:
            self._persist_position_open(position)

    def _position_storage_key(self, position: PaperPosition) -> str:
        return "|".join([
            "paper",
            self.exchange_id,
            position.symbol,
            position.direction,
            _iso_utc(position.entry_time),
            str(position.entry_price),
        ])

    def _position_storage_payload(self, position: PaperPosition) -> dict:
        raw = self._position_to_dict(position)
        return {
            "idempotency_key": self._position_storage_key(position),
            "symbol": position.symbol,
            "mode": "paper",
            "market_type": position.market_type,
            "exchange": self.exchange_id,
            "timeframe": position.timeframe,
            "side": position.direction,
            "entry_price": position.entry_price,
            "stop_loss": position.sl_price,
            "take_profit": position.tp_price,
            "status": "OPEN",
            "opened_at": _iso_utc(position.entry_time),
            "reason_open": position.source_signal,
            "raw": raw,
        }

    def _persist_position_open(self, position: PaperPosition) -> None:
        if position.storage_id:
            return
        position.storage_id = storage.get_storage().upsert_open_paper_trade(
            self._position_storage_payload(position),
            idempotency_key=self._position_storage_key(position),
        )

    def _load_from_sqlite(self) -> None:
        db = storage.get_storage()
        self.positions = [self._position_from_storage(row) for row in db.get_open_trades()]
        self.closed_trades = [self._closed_trade_from_storage(row) for row in db.list_paper_trades(status="CLOSED")]
        if self.closed_trades:
            last_capital = self.closed_trades[-1].get("capital_after")
            if last_capital is not None:
                self.capital_usdt = float(last_capital)
            else:
                self.capital_usdt = self.initial_capital_usdt + sum(
                    float(row.get("net_pnl") or 0.0) for row in self.closed_trades
                )
        self.equity_curve = [{"timestamp": _now_utc().isoformat(), "equity": self._current_equity()}]

    def _position_from_storage(self, row: dict) -> PaperPosition:
        raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
        source = dict(raw)
        source.update({
            "symbol": row.get("symbol"),
            "direction": row.get("side") or raw.get("direction"),
            "entry_price": row.get("entry_price"),
            "sl_price": row.get("stop_loss") or raw.get("sl_price"),
            "tp_price": row.get("take_profit") or raw.get("tp_price"),
            "timeframe": row.get("timeframe") or raw.get("timeframe"),
            "status": row.get("status") or raw.get("status") or "OPEN",
            "market_type": row.get("market_type") or raw.get("market_type") or "spot",
            "storage_id": row.get("id"),
        })
        return self._position_from_dict(source)

    def _closed_trade_from_storage(self, row: dict) -> dict:
        raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
        if raw:
            return raw
        return {
            "opened_at": row.get("opened_at"),
            "closed_at": row.get("closed_at"),
            "symbol": row.get("symbol"),
            "direction": row.get("side"),
            "timeframe": row.get("timeframe"),
            "entry_price": row.get("entry_price"),
            "exit_price": row.get("close_price"),
            "sl_price": row.get("stop_loss"),
            "tp_price": row.get("take_profit"),
            "net_pnl": row.get("pnl"),
            "r_multiple": 0.0,
            "reason": row.get("reason_close"),
        }

    def _create_entry_order(self, symbol: str, direction: str, units: float, entry_price: float) -> str | None:
        if self.mode != "online" or self.exchange is None:
            return f"offline-{symbol}-{int(_now_utc().timestamp())}"

        side = "buy" if direction == "LONG" else "sell"
        order = self._exchange_call(
            self.exchange.create_order,
            symbol,
            "limit",
            side,
            units,
            entry_price,
        )
        if not order:
            return None
        logger.info("Orden sandbox creada: %s %s %s", side, symbol, order.get("id"))
        return order.get("id") or order.get("clientOrderId") or str(order)

    def _create_close_order(self, pos: PaperPosition) -> str | None:
        if self.mode != "online" or self.exchange is None:
            return None

        side = "sell" if pos.direction == "LONG" else "buy"
        order = self._exchange_call(
            self.exchange.create_order,
            pos.symbol,
            "market",
            side,
            pos.units,
        )
        if not order:
            logger.warning("No se pudo crear orden de cierre sandbox para %s", pos.symbol)
            return None
        logger.info("Orden sandbox de cierre creada: %s %s %s", side, pos.symbol, order.get("id"))
        return order.get("id") or order.get("clientOrderId") or str(order)

    def _connect_exchange(self) -> None:
        key = os.getenv("PAPER_API_KEY")
        secret = os.getenv("PAPER_API_SECRET")
        password = os.getenv("PAPER_API_PASSWORD")

        target_exchange = self.exchange_id
        if target_exchange == "kucoin" and not (key and secret and password):
            if key and secret:
                logger.warning("KuCoin sandbox requiere PAPER_API_PASSWORD; intentando Binance Testnet")
                target_exchange = "binance"
            else:
                logger.warning("Modo offline: sin conexión a exchange sandbox")
                return
        elif target_exchange == "binance" and not (key and secret):
            logger.warning("Modo offline: sin conexión a exchange sandbox")
            return
        elif target_exchange not in ("kucoin", "binance"):
            logger.warning("Exchange paper no soportado (%s); modo offline", target_exchange)
            return

        try:
            exchange_class = getattr(ccxt, target_exchange)
            params = {
                "apiKey": key,
                "secret": secret,
                "enableRateLimit": True,
            }
            if target_exchange == "kucoin":
                params["password"] = password
            if target_exchange == "binance":
                params["options"] = {"defaultType": "spot"}

            exchange = exchange_class(params)
            if hasattr(exchange, "set_sandbox_mode"):
                exchange.set_sandbox_mode(True)

            markets = self._exchange_call(exchange.load_markets)
            if markets is None:
                logger.warning("No se pudo inicializar sandbox; modo offline")
                return

            self.exchange = exchange
            self.exchange_id = target_exchange
            self.mode = "online"
            logger.info("Conectado a %s sandbox en modo paper", target_exchange)
        except ccxt.NetworkError as exc:
            logger.error("Error de red conectando sandbox: %s", exc)
        except ccxt.ExchangeError as exc:
            logger.error("Error de exchange conectando sandbox: %s", exc)
        except Exception as exc:
            logger.error("No se pudo conectar sandbox; modo offline: %s", exc)

        if self.mode != "online":
            logger.warning("Modo offline: sin conexión a exchange sandbox")

    def _exchange_call(self, func, *args, **kwargs):
        for attempt in range(2):
            try:
                return func(*args, **kwargs)
            except ccxt.NetworkError as exc:
                if attempt == 0:
                    logger.warning("Error de red CCXT; reintento en 5s: %s", exc)
                    time.sleep(5)
                    continue
                logger.error("Error de red CCXT tras reintento: %s", exc)
                return None
            except ccxt.ExchangeError as exc:
                logger.error("Error de exchange CCXT: %s", exc)
                return None
        return None

    def _get_current_price(self, symbol: str) -> float | None:
        try:
            df = data_provider.fetch_ohlcv(symbol, "1m", days=1)
            if df is None or df.empty:
                return None
            return float(df.iloc[-1]["close"])
        except Exception as exc:
            logger.warning("Precio offline no disponible para %s: %s", symbol, exc)
            return self._last_prices.get(symbol)

    def _exit_price_for_reason(self, pos: PaperPosition, reason: str) -> float:
        if pos.symbol in self._last_prices:
            return float(self._last_prices[pos.symbol])
        if reason == "TP":
            return pos.tp_price
        if reason == "SL":
            return pos.sl_price
        return pos.entry_price

    def _snapshot_equity(self) -> None:
        self.equity_curve.append({
            "timestamp": _now_utc().isoformat(),
            "equity": self._current_equity(),
        })

    def _unrealized_pnl(self, position: PaperPosition) -> float:
        current_price = self._last_prices.get(position.symbol)
        if current_price is None:
            current_price = self._get_current_price(position.symbol)
        if current_price is None:
            return 0.0
        if position.direction == "LONG":
            return position.units * (current_price - position.entry_price)
        return position.units * (position.entry_price - current_price)

    def _max_drawdown_pct(self) -> float:
        values = [float(row.get("equity", 0) or 0) for row in self.equity_curve]
        if not values:
            values = [self._current_equity()]
        peak = values[0]
        max_drawdown = 0.0
        for value in values:
            peak = max(peak, value)
            if peak > 0:
                max_drawdown = max(max_drawdown, (peak - value) / peak * 100)
        return max_drawdown

    def _sharpe_ratio(self, r_values: list[float]) -> float | None:
        if len(r_values) < 5:
            return None
        std_r = float(np.std(r_values, ddof=1))
        if std_r == 0:
            return None
        return float(np.mean(r_values) / std_r * np.sqrt(len(r_values)))

    def _position_to_dict(self, position: PaperPosition) -> dict:
        row = asdict(position)
        row["entry_time"] = _iso_utc(position.entry_time)
        return row

    def _position_from_dict(self, row: dict) -> PaperPosition:
        storage_id = row.get("storage_id")
        try:
            if storage_id is not None and not pd.isna(storage_id) and str(storage_id).strip():
                storage_id = int(float(storage_id))
            else:
                storage_id = None
        except (TypeError, ValueError):
            storage_id = None
        return PaperPosition(
            symbol=str(row.get("symbol")),
            direction=str(row.get("direction", "LONG")).upper(),
            entry_price=float(row.get("entry_price")),
            sl_price=float(row.get("sl_price")),
            tp_price=float(row.get("tp_price")),
            units=float(row.get("units")),
            risk_amount=float(row.get("risk_amount")),
            entry_time=_parse_utc(row.get("entry_time")),
            timeframe=str(row.get("timeframe") or ""),
            score=int(float(row.get("score") or 0)),
            source_signal=str(row.get("source_signal") or "SPOT"),
            exchange_order_id=str(row.get("exchange_order_id") or ""),
            status=str(row.get("status") or "OPEN"),
            market_type=str(row.get("market_type") or "spot"),
            storage_id=storage_id,
        )
