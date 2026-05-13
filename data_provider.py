import ccxt
import pandas as pd
from datetime import datetime, timezone
import time
import threading
import config

LOW_VOLUME_WARNING = "LOW_VOLUME_WARNING"
_THREAD_LOCAL = threading.local()


def get_exchange():
    exchange = getattr(_THREAD_LOCAL, "exchange", None)
    if exchange is not None:
        return exchange

    exchange = ccxt.binance({
        "enableRateLimit": True,
        "options": {"defaultType": "spot"},
    })
    _THREAD_LOCAL.exchange = exchange
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


def fetch_ohlcv(
    symbol: str,
    timeframe: str,
    days: int = 365,
    ohlcv_limit: int = None,
) -> pd.DataFrame:
    exchange = get_exchange()
    symbol = normalize_symbol(symbol)

    try:
        markets = exchange.load_markets()
    except Exception as e:
        raise RuntimeError(f"Cannot load markets: {e}")

    if symbol not in markets:
        raise ValueError(f"Symbol '{symbol}' not found on Binance spot. Check spelling.")

    tf_ms = {
        "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000,
        "30m": 1_800_000, "1h": 3_600_000, "2h": 7_200_000,
        "4h": 14_400_000, "1d": 86_400_000,
    }
    ms_per_candle = tf_ms.get(timeframe, 3_600_000)
    if ohlcv_limit is not None:
        limit = max(1, min(int(ohlcv_limit), 1000))
        try:
            candles = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        except Exception as e:
            raise RuntimeError(f"Error fetching OHLCV for {symbol} {timeframe}: {e}")
        all_candles = candles or []
    else:
        since_ms = int((time.time() * 1000) - days * 86_400_000)
        limit = 1000

        all_candles = []
        fetch_since = since_ms

        while True:
            try:
                candles = exchange.fetch_ohlcv(symbol, timeframe, since=fetch_since, limit=limit)
            except Exception as e:
                raise RuntimeError(f"Error fetching OHLCV for {symbol} {timeframe}: {e}")

            if not candles:
                break

            all_candles.extend(candles)

            if len(candles) < limit:
                break

            fetch_since = candles[-1][0] + ms_per_candle
            if fetch_since > int(time.time() * 1000):
                break

    if not all_candles:
        raise ValueError(f"No OHLCV data returned for {symbol} {timeframe}.")

    df = pd.DataFrame(all_candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.drop_duplicates(subset="timestamp").sort_values("timestamp").reset_index(drop=True)
    df = df[["timestamp", "datetime", "open", "high", "low", "close", "volume"]]
    return df


def fetch_ticker_volume(symbol: str) -> dict:
    exchange = get_exchange()
    symbol = normalize_symbol(symbol)
    try:
        ticker = exchange.fetch_ticker(symbol)
        return {
            "symbol": symbol,
            "last": ticker.get("last"),
            "quoteVolume": ticker.get("quoteVolume"),
            "baseVolume": ticker.get("baseVolume"),
        }
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}


def is_symbol_liquid(symbol: str, min_quote_volume: float = None) -> tuple:
    if min_quote_volume is None:
        min_quote_volume = config.MIN_24H_QUOTE_VOLUME_USDT

    ticker = fetch_ticker_volume(symbol)
    if "error" in ticker:
        return False, ticker

    qv = ticker.get("quoteVolume") or 0
    liquid = qv >= min_quote_volume
    ticker["liquid"] = liquid
    ticker["min_quote_volume"] = min_quote_volume
    ticker["warning"] = None if liquid else LOW_VOLUME_WARNING
    return liquid, ticker


def get_top_usdt_symbols_by_volume(limit: int = 100) -> list:
    exchange = get_exchange()
    try:
        tickers = exchange.fetch_tickers()
    except Exception as e:
        raise RuntimeError(f"Cannot fetch tickers: {e}")

    usdt_tickers = [
        (sym, data.get("quoteVolume") or 0)
        for sym, data in tickers.items()
        if sym.endswith("/USDT") and (data.get("quoteVolume") or 0) > 0
    ]
    usdt_tickers.sort(key=lambda x: x[1], reverse=True)
    return [sym for sym, _ in usdt_tickers[:limit]]
