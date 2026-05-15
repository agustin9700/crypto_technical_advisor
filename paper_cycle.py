import argparse
import logging
import time
import traceback

import config
import scanner
from paper_trader import PaperTrader


logger = logging.getLogger(__name__)


def _row_to_signal(row: dict) -> dict | None:
    try:
        entry_price = row.get("estimated_entry") or row.get("price")
        return {
            "symbol": row["symbol"],
            "direction": row.get("direction") or "LONG",
            "entry_price": float(entry_price),
            "sl_price": float(row["estimated_stop_loss"]),
            "tp_price": float(row["estimated_take_profit"]),
            "score": int(row.get("score") or 0),
            "timeframe": row.get("recommended_timeframe") or row.get("timeframe") or "",
            "source_signal": row.get("source_signal") or "SPOT",
        }
    except (KeyError, TypeError, ValueError) as exc:
        logger.warning("Señal inválida para paper trading: %s (%s)", row, exc)
        return None


def _log_closed_trades(closed_trades: list[dict]) -> None:
    for trade in closed_trades:
        logger.info(
            "Paper trade cerrado: %s %s %s PnL %.4f R %.3f",
            trade.get("reason"),
            trade.get("direction"),
            trade.get("symbol"),
            trade.get("net_pnl", 0.0),
            trade.get("r_multiple", 0.0),
        )


def _open_new_positions(
    trader: PaperTrader,
    scan_limit: int,
    scan_mode: str,
    workers: int,
    exchange_id: str,
) -> None:
    available_slots = config.MAX_OPEN_TRADES - len(trader.positions)
    if available_slots <= 0:
        return

    scan_result = scanner.run_scan(
        limit=scan_limit,
        mode=scan_mode,
        workers=workers,
        backtest_top_n=0,
        exchange_id=exchange_id,
        exchange_mode="manual",
    )
    rows = [
        row for row in scan_result.get("rows", [])
        if row.get("decision") == "ENTER_NOW_CANDIDATE"
        and (row.get("score") or 0) >= 7
    ]
    rows.sort(key=lambda row: row.get("score") or 0, reverse=True)

    for row in rows[:available_slots]:
        signal = _row_to_signal(row)
        if not signal:
            continue
        position = trader.open_position(signal)
        if position:
            logger.info(
                "Nueva posición paper abierta desde scanner: %s %s score %s",
                position.direction,
                position.symbol,
                position.score,
            )


def run_paper_cycle(
    exchange_id: str = "kucoin",
    capital_usdt: float = 1000.0,
    scan_interval_minutes: int = 60,
    scan_limit: int = 20,
    scan_mode: str = "fast",
    workers: int = 5,
    dry_run: bool = False,
) -> None:
    """
    Ejecuta el loop continuo de paper trading.

    Parámetros:
        exchange_id: Exchange sandbox preferido.
        capital_usdt: Capital inicial simulado.
        scan_interval_minutes: Minutos de espera entre scans.
        scan_limit: Cantidad de símbolos a escanear.
        scan_mode: Modo del scanner, "fast" o "full".
        workers: Cantidad de workers del scanner.
        dry_run: Si True, actualiza posiciones pero no abre nuevas.

    Retorno:
        None. Corre hasta interrupción con Ctrl+C.
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logger.info(
        "Iniciando paper cycle exchange=%s capital=%.2f interval=%sm dry_run=%s",
        exchange_id,
        capital_usdt,
        scan_interval_minutes,
        dry_run,
    )

    trader = PaperTrader.load_from_report(exchange_id=exchange_id, capital_usdt=capital_usdt)
    try:
        while True:
            try:
                trader = PaperTrader.load_from_report(exchange_id=exchange_id, capital_usdt=capital_usdt)
                closed = trader.update_positions()
                _log_closed_trades(closed)

                if len(trader.positions) < config.MAX_OPEN_TRADES and not dry_run:
                    _open_new_positions(
                        trader,
                        scan_limit=scan_limit,
                        scan_mode=scan_mode,
                        workers=workers,
                        exchange_id=exchange_id,
                    )

                summary = trader.get_summary()
                logger.info("Resumen paper trading: %s", summary)
                trader._save_report()

                time.sleep(max(int(scan_interval_minutes), 1) * 60)
            except Exception as exc:
                logger.error("Error capturado en paper cycle: %s", exc)
                logger.error(traceback.format_exc())
                time.sleep(max(int(scan_interval_minutes), 1) * 60)
    except KeyboardInterrupt:
        logger.info("Paper cycle interrumpido por usuario. Resumen final: %s", trader.get_summary())


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ejecuta el ciclo de paper trading.")
    parser.add_argument("--exchange", default="kucoin", help="Exchange sandbox a usar.")
    parser.add_argument("--capital", type=float, default=1000.0, help="Capital inicial en USDT.")
    parser.add_argument("--interval", type=int, default=60, help="Intervalo entre scans, en minutos.")
    parser.add_argument("--limit", type=int, default=20, help="Cantidad de simbolos a escanear.")
    parser.add_argument("--mode", choices=("fast", "full"), default="fast", help="Modo del scanner.")
    parser.add_argument("--workers", type=int, default=5, help="Cantidad de workers del scanner.")
    parser.add_argument("--dry-run", action="store_true", help="Actualiza posiciones sin abrir nuevas.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    run_paper_cycle(
        exchange_id=args.exchange,
        capital_usdt=args.capital,
        scan_interval_minutes=args.interval,
        scan_limit=args.limit,
        scan_mode=args.mode,
        workers=args.workers,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
