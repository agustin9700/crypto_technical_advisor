from datetime import timezone

import pandas as pd

import data_provider
import futures_analyzer
import technical_analyzer


class PatchSet:
    def __init__(self):
        self._changes = []

    def setattr(self, obj, name, value):
        self._changes.append((obj, name, getattr(obj, name)))
        setattr(obj, name, value)

    def restore(self):
        for obj, name, value in reversed(self._changes):
            setattr(obj, name, value)
        self._changes.clear()


def raw_frame(rows=240, market_type="spot"):
    dates = pd.date_range("2026-01-01", periods=rows, freq="h", tz=timezone.utc)
    close = pd.Series([100 + i * 0.1 for i in range(rows)], dtype="float64")
    df = pd.DataFrame({
        "timestamp": range(rows),
        "datetime": dates,
        "open": close,
        "high": close + 1,
        "low": close - 1,
        "close": close,
        "volume": [1000.0] * rows,
    })
    df.attrs = {
        "exchange_id": "mockex",
        "data_source_exchange": "mockex",
        "exchange_mode": "manual",
        "fallback_used": False,
        "market_type": market_type,
        "data_source_market_type": market_type,
        "market_symbol": "BTC/USDT:USDT" if market_type == "futures" else "BTC/USDT",
    }
    return df


def indicator_frame(rows=240, direction="long"):
    df = raw_frame(rows)
    if direction == "short":
        df["close"] = 80.0
        df["ema20"] = 84.0
        df["ema50"] = 88.0
        df["ema200"] = 100.0
        df["rsi"] = 38.0
        df["macd"] = -2.0
        df["macd_signal"] = -1.0
    else:
        df["close"] = 120.0
        df["ema20"] = 116.0
        df["ema50"] = 112.0
        df["ema200"] = 100.0
        df["rsi"] = 62.0
        df["macd"] = 2.0
        df["macd_signal"] = 1.0
    df["atr"] = 2.0
    df["atr_pct"] = 1.7
    df["vol_ratio"] = 1.5
    df["bb_mid"] = df["close"]
    df["bb_upper"] = df["close"] + 4
    df["bb_lower"] = df["close"] - 4
    return df


class FakeExchange:
    def __init__(self, exchange_id, markets):
        self.id = exchange_id
        self.markets = markets
        self.fetch_calls = []

    def load_markets(self):
        return self.markets

    def fetch_ohlcv(self, symbol, timeframe, since=None, limit=None):
        self.fetch_calls.append((symbol, timeframe, since, limit))
        return [
            [1, 100, 101, 99, 100, 1000],
            [2, 100, 102, 98, 101, 1100],
        ]


def spot_markets(symbol="BTC/USDT"):
    return {
        symbol: {
            "symbol": symbol,
            "base": "BTC",
            "quote": "USDT",
            "spot": True,
            "contract": False,
            "type": "spot",
        }
    }


def futures_markets(symbol="BTC/USDT:USDT"):
    return {
        symbol: {
            "symbol": symbol,
            "base": "BTC",
            "quote": "USDT",
            "spot": False,
            "contract": True,
            "swap": True,
            "type": "swap",
        }
    }


def test_spot_analyzer_requests_spot_data():
    calls = []
    patches = PatchSet()

    def fake_fetch(symbol, timeframe, **kwargs):
        calls.append(kwargs.get("market_type"))
        return raw_frame(market_type="spot")

    try:
        patches.setattr(data_provider, "fetch_ohlcv_with_fallback", fake_fetch)
        patches.setattr(technical_analyzer.indicators, "add_indicators", lambda df: indicator_frame())
        result = technical_analyzer.analyze_symbol_timeframe("BTC/USDT", "1h", exchange_id="mockex", exchange_mode="manual")
    finally:
        patches.restore()

    assert calls and set(calls) == {"spot"}, calls
    assert result["market_type"] == "spot", result


def test_futures_analyzer_requests_futures_data():
    calls = []
    patches = PatchSet()

    def fake_fetch(symbol, timeframe, **kwargs):
        calls.append(kwargs.get("market_type"))
        return raw_frame(market_type="futures")

    try:
        patches.setattr(data_provider, "fetch_ohlcv_with_fallback", fake_fetch)
        patches.setattr(futures_analyzer.indicators, "add_indicators", lambda df: indicator_frame(direction="long"))
        result = futures_analyzer.analyze_futures_symbol_timeframe("BTC/USDT", "1h", exchange_id="mockex", exchange_mode="manual")
    finally:
        patches.restore()

    assert calls and set(calls) == {"futures"}, calls
    assert result["market_type"] == "futures", result
    assert result["market_symbol"] == "BTC/USDT:USDT", result


def test_ccxt_like_symbol_routing_spot_and_futures():
    patches = PatchSet()
    spot_exchange = FakeExchange("binance", spot_markets())
    futures_exchange = FakeExchange("binance", futures_markets())

    def fake_get_exchange(exchange_id=None, market_type="spot"):
        if market_type == "futures":
            return futures_exchange
        return spot_exchange

    try:
        patches.setattr(data_provider, "get_exchange", fake_get_exchange)
        spot_df = data_provider.fetch_ohlcv_with_fallback(
            "BTC/USDT",
            "1h",
            exchange_id="binance",
            exchange_mode="manual",
            market_type="spot",
            ohlcv_limit=2,
        )
        futures_df = data_provider.fetch_ohlcv_with_fallback(
            "BTC/USDT",
            "1h",
            exchange_id="binance",
            exchange_mode="manual",
            market_type="futures",
            ohlcv_limit=2,
        )
    finally:
        patches.restore()

    assert spot_exchange.fetch_calls[0][0] == "BTC/USDT"
    assert futures_exchange.fetch_calls[0][0] == "BTC/USDT:USDT"
    assert spot_df.attrs["market_symbol"] == "BTC/USDT"
    assert futures_df.attrs["market_symbol"] == "BTC/USDT:USDT"
    assert futures_df.attrs["market_type"] == "futures"


def test_fallback_keeps_futures_market_type_and_never_fetches_spot():
    patches = PatchSet()
    kucoin_spot_only = FakeExchange("kucoin", spot_markets())
    binance_futures = FakeExchange("binance", futures_markets())

    def fake_get_exchange(exchange_id=None, market_type="spot"):
        if exchange_id == "kucoin":
            return kucoin_spot_only
        return binance_futures

    try:
        patches.setattr(data_provider, "get_exchange", fake_get_exchange)
        df = data_provider.fetch_ohlcv_with_fallback(
            "BTC/USDT",
            "1h",
            exchange_mode="fallback",
            exchange_priority=["kucoin", "binance"],
            market_type="futures",
            ohlcv_limit=2,
        )
    finally:
        patches.restore()

    assert kucoin_spot_only.fetch_calls == []
    assert binance_futures.fetch_calls[0][0] == "BTC/USDT:USDT"
    assert df.attrs["data_source_exchange"] == "binance", df.attrs
    assert df.attrs["fallback_used"] is True, df.attrs
    assert df.attrs["market_type"] == "futures", df.attrs


def test_missing_futures_symbol_errors_without_spot_fallback():
    patches = PatchSet()
    kucoin_spot_only = FakeExchange("kucoin", spot_markets())
    binance_spot_only = FakeExchange("binance", spot_markets())

    def fake_get_exchange(exchange_id=None, market_type="spot"):
        return kucoin_spot_only if exchange_id == "kucoin" else binance_spot_only

    try:
        patches.setattr(data_provider, "get_exchange", fake_get_exchange)
        try:
            data_provider.fetch_ohlcv_with_fallback(
                "BTC/USDT",
                "1h",
                exchange_mode="fallback",
                exchange_priority=["kucoin", "binance"],
                market_type="futures",
                ohlcv_limit=2,
            )
        except RuntimeError as exc:
            error = str(exc)
        else:
            raise AssertionError("Expected futures missing symbol to raise")
    finally:
        patches.restore()

    assert "not listed on futures market" in error, error
    assert kucoin_spot_only.fetch_calls == []
    assert binance_spot_only.fetch_calls == []


def main():
    test_spot_analyzer_requests_spot_data()
    test_futures_analyzer_requests_futures_data()
    test_ccxt_like_symbol_routing_spot_and_futures()
    test_fallback_keeps_futures_market_type_and_never_fetches_spot()
    test_missing_futures_symbol_errors_without_spot_fallback()
    print("MARKET TYPE ROUTING TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
