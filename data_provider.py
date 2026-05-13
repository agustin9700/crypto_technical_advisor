import threading
import time

import ccxt
import pandas as pd

import config


LOW_VOLUME_WARNING = "LOW_VOLUME_WARNING"
DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
_THREAD_LOCAL = threading.local()


def _exchange_priority(exchange_priority=None) -> list:
    return list(exchange_priority or config.EXCHANGE_PRIORITY)


def _exchange_options(exchange_id: str) -> dict:
    options = {"defaultType": "spot"}
    if exchange_id == "okx":
        options = {"defaultType": "spot"}
    return {
        "enableRateLimit": True,
        "options": options,
    }


def get_exchange(exchange_id: str = None):
    exchange_id = (exchange_id or config.DEFAULT_EXCHANGE).lower()
    exchanges = getattr(_THREAD_LOCAL, "exchanges", None)
    if exchanges is None:
        exchanges = {}
        _THREAD_LOCAL.exchanges = exchanges
    if exchange_id in exchanges:
        return exchanges[exchange_id]

    if not hasattr(ccxt, exchange_id):
        raise ValueError(f"Exchange '{exchange_id}' is not supported by ccxt.")

    exchange_class = getattr(ccxt, exchange_id)
    exchange = exchange_class(_exchange_options(exchange_id))
    exchanges[exchange_id] = exchange
    return exchange


def normalize_symbol(symbol: str) -> str:
    symbol = symbol.strip().upper()
    if "/" not in symbol:
        if symbol.endswith("USDT"):
            symbol = symbol[:-4] + "/USDT"
        elif symbol.endswith("BTC"):
            symbol = symbol[:-3] + "/BTC"
        else:
            symbol = symbol + "/USDT"
    return symbol


def _error_text(error: Exception) -> str:
    return f"{type(error).__name__}: {error}"


def _is_recoverable_exchange_error(error: Exception) -> bool:
    text = _error_text(error).lower()
    recoverable_markers = (
        "451",
        "restricted location",
        "service unavailable from a restricted location",
        "networkerror",
        "exchangenotavailable",
        "timeout",
        "ssl",
        "certificate",
        "connection",
        "max retries",
        "temporarily unavailable",
    )
    recoverable_types = (
        ccxt.NetworkError,
        ccxt.ExchangeNotAvailable,
        ccxt.RequestTimeout,
        ccxt.DDoSProtection,
    )
    return isinstance(error, recoverable_types) or any(marker in text for marker in recoverable_markers)


def _load_markets(exchange, exchange_id: str):
    try:
        return exchange.load_markets()
    except Exception as exc:
        raise RuntimeError(f"{exchange_id}: cannot load markets ({_error_text(exc)})") from exc


def _market_symbol(exchange, symbol: str) -> str:
    symbol = normalize_symbol(symbol)
    if symbol in exchange.markets:
        return symbol
    return None


def get_exchange_for_symbol(symbol, exchange_priority=None):
    symbol = normalize_symbol(symbol)
    errors = []
    for exchange_id in _exchange_priority(exchange_priority):
        try:
            exchange = get_exchange(exchange_id)
            _load_markets(exchange, exchange_id)
            market_symbol = _market_symbol(exchange, symbol)
            if not market_symbol:
                last_error = f"{exchange_id}: {symbol} not listed"
                errors.append(last_error)
                continue
            return exchange, exchange_id, market_symbol, errors
        except Exception as exc:
            errors.append(f"{exchange_id}: {_error_text(exc)}")
            if _is_recoverable_exchange_error(exc):
                continue
            continue
    raise RuntimeError(
        f"{DATA_UNAVAILABLE}: No se pudieron obtener datos desde los exchanges configurados. "
        f"Errores: {' | '.join(errors)}"
    )


def _ohlcv_dataframe(candles: list, exchange_id: str, status: str, last_error: str) -> pd.DataFrame:
    if not candles:
        raise ValueError("No OHLCV data returned.")

    df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.drop_duplicates(subset="timestamp").sort_values("timestamp").reset_index(drop=True)
    df = df[["timestamp", "datetime", "open", "high", "low", "close", "volume"]]
    df.attrs["exchange_id"] = exchange_id
    df.attrs["data_source_status"] = status
    df.attrs["data_source_error"] = last_error
    return df


def _fetch_ohlcv_from_exchange(exchange, symbol: str, timeframe: str, days: int, ohlcv_limit: int):
    tf_ms = {
        "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000,
        "30m": 1_800_000, "1h": 3_600_000, "2h": 7_200_000,
        "4h": 14_400_000, "1d": 86_400_000,
    }
    ms_per_candle = tf_ms.get(timeframe, 3_600_000)

    if ohlcv_limit is not None:
        limit = max(1, min(int(ohlcv_limit), 1000))
        return exchange.fetch_ohlcv(symbol, timeframe, limit=limit)

    since_ms = int((time.time() * 1000) - days * 86_400_000)
    limit = 1000
    all_candles = []
    fetch_since = since_ms

    while True:
        candles = exchange.fetch_ohlcv(symbol, timeframe, since=fetch_since, limit=limit)
        if not candles:
            break

        all_candles.extend(candles)
        if len(candles) < limit:
            break

        fetch_since = candles[-1][0] + ms_per_candle
        if fetch_since > int(time.time() * 1000):
            break

    return all_candles


def fetch_ohlcv_with_fallback(
    symbol: str,
    timeframe: str,
    days: int = None,
    ohlcv_limit: int = None,
    exchange_priority=None,
) -> pd.DataFrame:
    symbol = normalize_symbol(symbol)
    days = days or 365
    errors = []
    last_error = ""

    for index, exchange_id in enumerate(_exchange_priority(exchange_priority)):
        try:
            exchange = get_exchange(exchange_id)
            _load_markets(exchange, exchange_id)
            market_symbol = _market_symbol(exchange, symbol)
            if not market_symbol:
                last_error = f"{exchange_id}: {symbol} not listed"
                errors.append(last_error)
                continue
            candles = _fetch_ohlcv_from_exchange(exchange, market_symbol, timeframe, days, ohlcv_limit)
            status = "OK" if index == 0 else "FALLBACK"
            return _ohlcv_dataframe(candles, exchange_id, status, last_error)
        except Exception as exc:
            last_error = f"{exchange_id}: {_error_text(exc)}"
            errors.append(last_error)
            continue

    raise RuntimeError(
        f"{DATA_UNAVAILABLE}: No se pudieron obtener datos desde los exchanges configurados. "
        f"Errores: {' | '.join(errors)}"
    )


def fetch_ohlcv(symbol: str, timeframe: str, days: int = 365, ohlcv_limit: int = None) -> pd.DataFrame:
    return fetch_ohlcv_with_fallback(
        symbol,
        timeframe,
        days=days,
        ohlcv_limit=ohlcv_limit,
    )


def _quote_volume_from_ticker(ticker: dict) -> float:
    quote_volume = ticker.get("quoteVolume")
    if quote_volume is not None:
        return quote_volume or 0
    last = ticker.get("last") or ticker.get("close") or 0
    base_volume = ticker.get("baseVolume") or 0
    try:
        return float(last) * float(base_volume)
    except (TypeError, ValueError):
        return 0


def fetch_ticker_volume_with_fallback(symbol: str, exchange_priority=None) -> dict:
    symbol = normalize_symbol(symbol)
    errors = []
    last_error = ""
    for index, exchange_id in enumerate(_exchange_priority(exchange_priority)):
        try:
            exchange = get_exchange(exchange_id)
            _load_markets(exchange, exchange_id)
            market_symbol = _market_symbol(exchange, symbol)
            if not market_symbol:
                last_error = f"{exchange_id}: {symbol} not listed"
                errors.append(last_error)
                continue
            ticker = exchange.fetch_ticker(market_symbol)
            return {
                "symbol": symbol,
                "last": ticker.get("last"),
                "quoteVolume": _quote_volume_from_ticker(ticker),
                "baseVolume": ticker.get("baseVolume"),
                "exchange_id": exchange_id,
                "data_source_status": "OK" if index == 0 else "FALLBACK",
                "data_source_error": last_error,
            }
        except Exception as exc:
            last_error = f"{exchange_id}: {_error_text(exc)}"
            errors.append(last_error)
            continue

    return {
        "symbol": symbol,
        "error": (
            f"{DATA_UNAVAILABLE}: No se pudieron obtener datos desde los exchanges configurados. "
            f"Errores: {' | '.join(errors)}"
        ),
    }


def fetch_ticker_volume(symbol: str) -> dict:
    return fetch_ticker_volume_with_fallback(symbol)


def is_symbol_liquid(symbol: str, min_quote_volume: float = None) -> tuple:
    if min_quote_volume is None:
        min_quote_volume = config.MIN_24H_QUOTE_VOLUME_USDT

    ticker = fetch_ticker_volume_with_fallback(symbol)
    if "error" in ticker:
        return False, ticker

    qv = ticker.get("quoteVolume") or 0
    liquid = qv >= min_quote_volume
    ticker["liquid"] = liquid
    ticker["min_quote_volume"] = min_quote_volume
    ticker["warning"] = None if liquid else LOW_VOLUME_WARNING
    return liquid, ticker


def _top_symbols_for_exchange(exchange_id: str, limit: int) -> tuple:
    exchange = get_exchange(exchange_id)
    _load_markets(exchange, exchange_id)
    tickers = exchange.fetch_tickers()
    usdt_tickers = []

    for sym, data in tickers.items():
        if not sym.endswith("/USDT") or ":" in sym:
            continue
        quote_volume = _quote_volume_from_ticker(data)
        if quote_volume <= 0:
            continue
        usdt_tickers.append((sym, quote_volume))

    usdt_tickers.sort(key=lambda x: x[1], reverse=True)
    return [sym for sym, _ in usdt_tickers[:limit]], usdt_tickers[:limit]


def get_top_usdt_symbols_by_volume(exchange_id=None, limit: int = 100) -> list:
    if isinstance(exchange_id, int) and limit == 100:
        limit = exchange_id
        exchange_id = None
    if exchange_id is None:
        return get_top_usdt_symbols_by_volume_with_fallback(limit=limit)["symbols"]
    symbols, _ = _top_symbols_for_exchange(exchange_id, limit)
    return symbols


def get_top_usdt_symbols_by_volume_with_fallback(limit: int = 100, exchange_priority=None) -> dict:
    errors = []
    for index, exchange_id in enumerate(_exchange_priority(exchange_priority)):
        try:
            symbols, ranked = _top_symbols_for_exchange(exchange_id, limit)
            if not symbols:
                errors.append(f"{exchange_id}: no USDT tickers with volume")
                continue
            return {
                "symbols": symbols,
                "ranked": ranked,
                "exchange_id": exchange_id,
                "data_source_status": "OK" if index == 0 else "FALLBACK",
                "data_source_error": " | ".join(errors),
            }
        except Exception as exc:
            errors.append(f"{exchange_id}: {_error_text(exc)}")
            continue

    raise RuntimeError(
        f"{DATA_UNAVAILABLE}: No se pudieron obtener datos desde los exchanges configurados. "
        f"Errores: {' | '.join(errors)}"
    )
