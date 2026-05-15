import threading
import time
import warnings

import ccxt
import pandas as pd

import config
import rate_limiter


LOW_VOLUME_WARNING = "LOW_VOLUME_WARNING"
DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
MAX_OHLCV_PAGES = 50
_THREAD_LOCAL = threading.local()


def normalize_market_type(market_type: str = None) -> str:
    value = (market_type or "spot").strip().lower()
    aliases = {
        "spot": "spot",
        "cash": "spot",
        "futures": "futures",
        "future": "futures",
        "swap": "futures",
        "perp": "futures",
        "perpetual": "futures",
    }
    if value not in aliases:
        raise ValueError("market_type must be 'spot' or 'futures'.")
    return aliases[value]


def _normalize_exchange_mode(exchange_mode: str = None) -> str:
    mode = (exchange_mode or config.EXCHANGE_MODE).strip().lower()
    if mode not in {"manual", "fallback"}:
        raise ValueError("exchange_mode must be 'manual' or 'fallback'.")
    return mode


def _normalize_exchange_id(exchange_id: str = None) -> str:
    normalized = (exchange_id or config.DEFAULT_EXCHANGE).strip().lower()
    if normalized not in config.SUPPORTED_EXCHANGES:
        supported = ", ".join(config.SUPPORTED_EXCHANGES)
        raise ValueError(f"Exchange '{normalized}' is not enabled. Supported exchanges: {supported}.")
    return normalized


def _exchange_priority(exchange_priority=None) -> list:
    return list(exchange_priority or config.EXCHANGE_PRIORITY)


def _exchange_sequence(exchange_id=None, exchange_mode=None, exchange_priority=None) -> tuple:
    mode = _normalize_exchange_mode(exchange_mode)
    if mode == "manual":
        candidates = [_normalize_exchange_id(exchange_id)]
    else:
        candidates = [_normalize_exchange_id(exchange) for exchange in _exchange_priority(exchange_priority)]

    seen = set()
    cleaned = []
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        cleaned.append(candidate)
    return cleaned, mode


def _ccxt_exchange_id(exchange_id: str, market_type: str = "spot") -> str:
    if normalize_market_type(market_type) == "futures" and exchange_id == "kucoin":
        return "kucoinfutures"
    return exchange_id


def _exchange_options(exchange_id: str, market_type: str = "spot") -> dict:
    market_type = normalize_market_type(market_type)
    options = {"enableRateLimit": True}
    if market_type == "spot":
        options["options"] = {"defaultType": "spot"}
    elif exchange_id == "binance":
        options["options"] = {"defaultType": "future"}
    return options


def get_exchange(exchange_id: str = None, market_type: str = "spot"):
    exchange_id = _normalize_exchange_id(exchange_id)
    market_type = normalize_market_type(market_type)
    exchanges = getattr(_THREAD_LOCAL, "exchanges", None)
    if exchanges is None:
        exchanges = {}
        _THREAD_LOCAL.exchanges = exchanges
    cache_key = (exchange_id, market_type)
    if cache_key in exchanges:
        return exchanges[cache_key]

    ccxt_exchange_id = _ccxt_exchange_id(exchange_id, market_type)
    if not hasattr(ccxt, ccxt_exchange_id):
        raise ValueError(
            f"Exchange '{exchange_id}' does not support market_type '{market_type}' in this build."
        )

    exchange_class = getattr(ccxt, ccxt_exchange_id)
    exchange = exchange_class(_exchange_options(exchange_id, market_type))
    exchange.cta_exchange_id = exchange_id
    exchange.cta_market_type = market_type
    exchange.cta_ccxt_exchange_id = ccxt_exchange_id
    exchanges[cache_key] = exchange
    return exchange


def normalize_symbol(symbol: str) -> str:
    symbol = str(symbol).strip().upper()
    if "/" in symbol:
        return symbol

    if "-" in symbol:
        parts = symbol.split("-")
        if len(parts) == 2 and parts[0] and parts[1]:
            return f"{parts[0]}/{parts[1]}"
        symbol = symbol.replace("-", "")

    if "/" not in symbol:
        if symbol.endswith("USDT"):
            symbol = symbol[:-4] + "/USDT"
        elif symbol.endswith("BTC"):
            symbol = symbol[:-3] + "/BTC"
        else:
            symbol = symbol + "/USDT"
    return symbol


def copy_df_with_attrs(df: pd.DataFrame) -> pd.DataFrame:
    copied = df.copy()
    copied.attrs = dict(getattr(df, "attrs", {}) or {})
    return copied


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
        "cloudfront",
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
        return rate_limiter.call(exchange.load_markets)
    except Exception as exc:
        raise RuntimeError(f"{exchange_id}: cannot load markets ({_error_text(exc)})") from exc


def _market_matches_type(market: dict, market_type: str) -> bool:
    market_type = normalize_market_type(market_type)
    if market_type == "spot":
        return bool(market.get("spot") or market.get("type") == "spot") and not market.get("contract")
    return bool(
        market.get("swap")
        or market.get("future")
        or market.get("contract")
        or market.get("type") in {"swap", "future"}
    )


def _market_symbol(exchange, symbol: str, market_type: str = "spot") -> str:
    symbol = normalize_symbol(symbol)
    market_type = normalize_market_type(market_type)
    if symbol in exchange.markets and _market_matches_type(exchange.markets[symbol], market_type):
        return symbol
    base, quote = symbol.split("/", 1)
    quote = quote.split(":", 1)[0]
    for market in exchange.markets.values():
        if not _market_matches_type(market, market_type):
            continue
        if market.get("base") == base and market.get("quote") == quote:
            return market.get("symbol")
    return None


def _source_meta(
    exchange_id: str,
    exchange_mode: str,
    index: int,
    last_error: str = "",
    market_type: str = "spot",
    market_symbol: str = None,
) -> dict:
    fallback_used = exchange_mode == "fallback" and index > 0
    status = "FALLBACK" if fallback_used else "OK"
    warnings = []
    if fallback_used:
        warnings.append(f"Fallback de exchange usado: {exchange_id}")
    return {
        "exchange_id": exchange_id,
        "data_source_exchange": exchange_id,
        "data_source_status": status,
        "exchange_mode": exchange_mode,
        "fallback_used": fallback_used,
        "data_source_error": last_error or "",
        "market_type": normalize_market_type(market_type),
        "data_source_market_type": normalize_market_type(market_type),
        "market_symbol": market_symbol,
        "data_warnings": warnings,
    }


def _data_unavailable_error(symbol: str, errors: list, exchange_mode: str, market_type: str = "spot") -> RuntimeError:
    mode_text = "manual" if exchange_mode == "manual" else "fallback"
    return RuntimeError(
        f"{DATA_UNAVAILABLE}: No se pudieron obtener datos desde los exchanges configurados. "
        f"Modo: {mode_text}. Market type: {normalize_market_type(market_type)}. "
        f"Symbol: {symbol}. Errores: {' | '.join(errors)}"
    )


def get_exchange_for_symbol(
    symbol,
    exchange_id=None,
    exchange_mode: str = None,
    exchange_priority=None,
    market_type: str = "spot",
):
    symbol = normalize_symbol(symbol)
    market_type = normalize_market_type(market_type)
    candidates, mode = _exchange_sequence(exchange_id, exchange_mode, exchange_priority)
    errors = []

    for index, candidate in enumerate(candidates):
        try:
            exchange = get_exchange(candidate, market_type=market_type)
            _load_markets(exchange, candidate)
            market_symbol = _market_symbol(exchange, symbol, market_type=market_type)
            if not market_symbol:
                errors.append(f"{candidate}: {symbol} not listed on {market_type} market")
                continue
            return exchange, candidate, market_symbol, errors
        except Exception as exc:
            errors.append(f"{candidate}: {_error_text(exc)}")
            if mode == "fallback" and _is_recoverable_exchange_error(exc):
                continue
            continue

    raise _data_unavailable_error(symbol, errors, mode, market_type=market_type)


def _ohlcv_dataframe(candles: list, source_meta: dict) -> pd.DataFrame:
    if not candles:
        raise ValueError("No OHLCV data returned.")

    df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.drop_duplicates(subset="timestamp").sort_values("timestamp").reset_index(drop=True)
    df = df[["timestamp", "datetime", "open", "high", "low", "close", "volume"]]
    for key, value in source_meta.items():
        df.attrs[key] = value
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
        return rate_limiter.call(exchange.fetch_ohlcv, symbol, timeframe, limit=limit)

    since_ms = int((time.time() * 1000) - days * 86_400_000)
    limit = 1000
    all_candles = []
    fetch_since = since_ms
    last_timestamp = None
    page = 0
    exchange_name = getattr(exchange, "id", "exchange")

    while True:
        if page >= MAX_OHLCV_PAGES:
            print(
                f"WARNING: OHLCV pagination stopped at max pages "
                f"({MAX_OHLCV_PAGES}) for {symbol} {timeframe} on {exchange_name}"
            )
            break

        candles = rate_limiter.call(exchange.fetch_ohlcv, symbol, timeframe, since=fetch_since, limit=limit)
        page += 1
        if not candles:
            break

        current_last_timestamp = candles[-1][0]
        if last_timestamp is not None and current_last_timestamp <= last_timestamp:
            print(
                f"WARNING: OHLCV pagination stopped because timestamp did not advance "
                f"for {symbol} {timeframe} on {exchange_name}"
            )
            break

        all_candles.extend(candles)
        if len(candles) < limit:
            break

        next_fetch_since = current_last_timestamp + ms_per_candle
        if next_fetch_since <= fetch_since:
            print(
                f"WARNING: OHLCV pagination stopped because next cursor did not advance "
                f"for {symbol} {timeframe} on {exchange_name}"
            )
            break

        last_timestamp = current_last_timestamp
        fetch_since = next_fetch_since
        if fetch_since > int(time.time() * 1000):
            break

    return all_candles


def fetch_ohlcv_with_fallback(
    symbol: str,
    timeframe: str,
    days: int = None,
    ohlcv_limit: int = None,
    exchange_id=None,
    exchange_mode: str = None,
    exchange_priority=None,
    market_type: str = "spot",
) -> pd.DataFrame:
    symbol = normalize_symbol(symbol)
    market_type = normalize_market_type(market_type)
    days = days or 365
    errors = []
    last_error = ""
    candidates, mode = _exchange_sequence(exchange_id, exchange_mode, exchange_priority)

    for index, candidate in enumerate(candidates):
        try:
            exchange = get_exchange(candidate, market_type=market_type)
            _load_markets(exchange, candidate)
            market_symbol = _market_symbol(exchange, symbol, market_type=market_type)
            if not market_symbol:
                last_error = f"{candidate}: {symbol} not listed on {market_type} market"
                errors.append(last_error)
                continue
            candles = _fetch_ohlcv_from_exchange(exchange, market_symbol, timeframe, days, ohlcv_limit)
            return _ohlcv_dataframe(
                candles,
                _source_meta(candidate, mode, index, last_error, market_type=market_type, market_symbol=market_symbol),
            )
        except Exception as exc:
            last_error = f"{candidate}: {_error_text(exc)}"
            errors.append(last_error)
            if mode == "fallback":
                continue
            break

    raise _data_unavailable_error(symbol, errors, mode, market_type=market_type)


def fetch_ohlcv(
    symbol: str,
    timeframe: str,
    days: int = 365,
    ohlcv_limit: int = None,
    exchange_id=None,
    exchange_mode: str = None,
    exchange_priority=None,
    market_type: str = "spot",
) -> pd.DataFrame:
    return fetch_ohlcv_with_fallback(
        symbol,
        timeframe,
        days=days,
        ohlcv_limit=ohlcv_limit,
        exchange_id=exchange_id,
        exchange_mode=exchange_mode,
        exchange_priority=exchange_priority,
        market_type=market_type,
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


def fetch_ticker_volume_with_fallback(
    symbol: str,
    exchange_id=None,
    exchange_mode: str = None,
    exchange_priority=None,
    market_type: str = "spot",
) -> dict:
    symbol = normalize_symbol(symbol)
    market_type = normalize_market_type(market_type)
    errors = []
    last_error = ""
    candidates, mode = _exchange_sequence(exchange_id, exchange_mode, exchange_priority)

    for index, candidate in enumerate(candidates):
        try:
            exchange = get_exchange(candidate, market_type=market_type)
            _load_markets(exchange, candidate)
            market_symbol = _market_symbol(exchange, symbol, market_type=market_type)
            if not market_symbol:
                last_error = f"{candidate}: {symbol} not listed on {market_type} market"
                errors.append(last_error)
                continue
            ticker = rate_limiter.call(exchange.fetch_ticker, market_symbol)
            return {
                "symbol": symbol,
                "last": ticker.get("last"),
                "quoteVolume": _quote_volume_from_ticker(ticker),
                "baseVolume": ticker.get("baseVolume"),
                **_source_meta(candidate, mode, index, last_error, market_type=market_type, market_symbol=market_symbol),
            }
        except Exception as exc:
            last_error = f"{candidate}: {_error_text(exc)}"
            errors.append(last_error)
            if mode == "fallback":
                continue
            break

    return {
        "symbol": symbol,
        "error": str(_data_unavailable_error(symbol, errors, mode, market_type=market_type)),
        "exchange_mode": mode,
        "fallback_used": False,
        "data_source_error": " | ".join(errors),
        "market_type": market_type,
    }


def fetch_ticker_volume(symbol: str, exchange_id=None, exchange_mode: str = None, market_type: str = "spot") -> dict:
    return fetch_ticker_volume_with_fallback(
        symbol,
        exchange_id=exchange_id,
        exchange_mode=exchange_mode,
        market_type=market_type,
    )


def is_symbol_liquid(
    symbol: str,
    min_quote_volume: float = None,
    exchange_id=None,
    exchange_mode: str = None,
    market_type: str = "spot",
) -> tuple:
    if min_quote_volume is None:
        min_quote_volume = config.MIN_24H_QUOTE_VOLUME_USDT

    ticker = fetch_ticker_volume_with_fallback(
        symbol,
        exchange_id=exchange_id,
        exchange_mode=exchange_mode,
        market_type=market_type,
    )
    if "error" in ticker:
        return False, ticker

    qv = ticker.get("quoteVolume") or 0
    liquid = qv >= min_quote_volume
    ticker["liquid"] = liquid
    ticker["min_quote_volume"] = min_quote_volume
    ticker["warning"] = None if liquid else LOW_VOLUME_WARNING
    return liquid, ticker


def _top_symbols_for_exchange(exchange_id: str, limit: int, market_type: str = "spot") -> tuple:
    market_type = normalize_market_type(market_type)
    exchange = get_exchange(exchange_id, market_type=market_type)
    _load_markets(exchange, exchange_id)
    tickers = rate_limiter.call(exchange.fetch_tickers)
    usdt_tickers = []

    for sym, data in tickers.items():
        market = exchange.markets.get(sym)
        if not market or not _market_matches_type(market, market_type):
            continue
        if market.get("quote") != "USDT":
            continue
        quote_volume = _quote_volume_from_ticker(data)
        if quote_volume <= 0:
            continue
        display_symbol = f"{market.get('base')}/{market.get('quote')}"
        usdt_tickers.append((display_symbol, quote_volume))

    usdt_tickers.sort(key=lambda x: x[1], reverse=True)
    return [sym for sym, _ in usdt_tickers[:limit]], usdt_tickers[:limit]


def get_top_usdt_symbols_by_volume_result(
    exchange_id=None,
    limit: int = 100,
    exchange_mode: str = None,
    exchange_priority=None,
    market_type: str = "spot",
) -> dict:
    errors = []
    market_type = normalize_market_type(market_type)
    candidates, mode = _exchange_sequence(exchange_id, exchange_mode, exchange_priority)

    for index, candidate in enumerate(candidates):
        try:
            symbols, ranked = _top_symbols_for_exchange(candidate, limit, market_type=market_type)
            if not symbols:
                errors.append(f"{candidate}: no {market_type} USDT tickers with volume")
                continue
            return {
                "symbols": symbols,
                "ranked": ranked,
                **_source_meta(candidate, mode, index, " | ".join(errors), market_type=market_type),
            }
        except Exception as exc:
            errors.append(f"{candidate}: {_error_text(exc)}")
            if mode == "fallback":
                continue
            break

    raise _data_unavailable_error("USDT universe", errors, mode, market_type=market_type)


def get_top_usdt_symbols_by_volume(
    exchange_id=None,
    limit: int = 100,
    exchange_mode: str = None,
    exchange_priority=None,
    market_type: str = "spot",
) -> list:
    if isinstance(exchange_id, int) and limit == 100:
        warnings.warn(
            "Passing limit as the first positional argument is deprecated; "
            "use get_top_usdt_symbols_by_volume(limit=...) instead.",
            UserWarning,
            stacklevel=2,
        )
        limit = exchange_id
        exchange_id = None
    result = get_top_usdt_symbols_by_volume_result(
        exchange_id=exchange_id,
        limit=limit,
        exchange_mode=exchange_mode,
        exchange_priority=exchange_priority,
        market_type=market_type,
    )
    return result["symbols"]


def get_top_usdt_symbols_by_volume_with_fallback(
    limit: int = 100,
    exchange_priority=None,
    exchange_id=None,
    exchange_mode: str = "fallback",
    market_type: str = "spot",
) -> dict:
    return get_top_usdt_symbols_by_volume_result(
        exchange_id=exchange_id,
        limit=limit,
        exchange_mode=exchange_mode,
        exchange_priority=exchange_priority,
        market_type=market_type,
    )
