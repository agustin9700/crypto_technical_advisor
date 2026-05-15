from datetime import timezone

import pandas as pd

import backtester
import futures_analyzer
import strategy_engine


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


def synthetic_ohlcv(rows=260):
    dates = pd.date_range("2026-01-01", periods=rows, freq="h", tz=timezone.utc)
    close = pd.Series([100 + i * 0.1 for i in range(rows)], dtype="float64")
    return pd.DataFrame({
        "timestamp": range(rows),
        "datetime": dates,
        "open": close,
        "high": close + 1,
        "low": close - 1,
        "close": close,
        "volume": [1000.0] * rows,
    })


def indicator_frame(rows=260):
    df = synthetic_ohlcv(rows)
    df["ema20"] = df["close"] - 1
    df["ema50"] = df["close"] - 2
    df["ema200"] = df["close"] - 10
    df["rsi"] = 60.0
    df["atr"] = 2.0
    df["atr_pct"] = 2.0
    df["macd"] = 2.0
    df["macd_signal"] = 1.0
    df["vol_ratio"] = 1.4
    return df


def test_strategy_engine_spot_signal():
    result = strategy_engine.evaluate_signal(
        indicator_frame(),
        symbol="BTC/USDT",
        mode="spot",
        timeframe="1h",
        exchange_id="kucoin",
        market_type="spot",
    )
    assert result["decision"] == "ENTER_NOW_CANDIDATE", result
    assert result["market_type"] == "spot", result
    assert result["risk_reward"] >= 1.499, result


def test_backtester_routes_to_strategy_engine():
    patches = PatchSet()
    calls = []
    raw = synthetic_ohlcv(260)
    raw.attrs = {"data_source_exchange": "mockex", "market_type": "spot"}

    def fake_fetch(symbol, timeframe, days=365, ohlcv_limit=None, exchange_id=None, exchange_mode=None, exchange_priority=None, market_type="spot"):
        assert exchange_id == "mockex"
        assert exchange_mode == "manual"
        assert market_type == "spot"
        return raw

    def fake_eval(df, symbol, mode, timeframe, exchange_id=None, market_type="spot", config=None):
        calls.append((symbol, mode, timeframe, exchange_id, market_type))
        return {"decision": "WAIT", "stop_loss": None, "take_profit": None}

    try:
        patches.setattr(backtester.data_provider, "fetch_ohlcv", fake_fetch)
        patches.setattr(backtester.indicators, "add_indicators", lambda df: indicator_frame(len(df)))
        patches.setattr(backtester.strategy_engine, "evaluate_signal", fake_eval)
        result = backtester.run_quick_backtest(
            "BTC/USDT",
            "1h",
            days=30,
            exchange_id="mockex",
            exchange_mode="manual",
            market_type="spot",
            mode="spot",
        )
    finally:
        patches.restore()

    assert calls, "backtester should call strategy_engine.evaluate_signal"
    assert result["strategy_engine"] == "strategy_engine.evaluate_signal", result
    assert result["exchange"] == "mockex", result
    assert result["market_type"] == "spot", result


def test_backtester_routes_futures_to_strategy_engine():
    patches = PatchSet()
    calls = []
    raw = synthetic_ohlcv(260)
    raw.attrs = {"data_source_exchange": "mockex", "market_type": "futures"}

    def fake_fetch(symbol, timeframe, days=365, ohlcv_limit=None, exchange_id=None, exchange_mode=None, exchange_priority=None, market_type="spot"):
        assert market_type == "futures"
        return raw

    def fake_eval(df, symbol, mode, timeframe, exchange_id=None, market_type="spot", config=None):
        calls.append((mode, market_type))
        return {"decision": "SHORT", "stop_loss": 110.0, "take_profit": 90.0}

    try:
        patches.setattr(backtester.data_provider, "fetch_ohlcv", fake_fetch)
        patches.setattr(backtester.indicators, "add_indicators", lambda df: indicator_frame(len(df)))
        patches.setattr(backtester.strategy_engine, "evaluate_signal", fake_eval)
        result = backtester.run_quick_backtest(
            "BTC/USDT",
            "1h",
            days=30,
            exchange_id="mockex",
            exchange_mode="manual",
            market_type="futures",
            mode="futures",
        )
    finally:
        patches.restore()

    assert calls and calls[0] == ("futures", "futures"), calls
    assert not hasattr(backtester, "_signal_at_bar")
    assert result["strategy_engine"] == "strategy_engine.evaluate_signal", result
    assert result["market_type"] == "futures", result


def test_futures_analyzer_delegates_to_strategy_engine():
    patches = PatchSet()
    calls = []
    raw = synthetic_ohlcv(260)
    raw.attrs = {
        "exchange_id": "mockex",
        "data_source_exchange": "mockex",
        "exchange_mode": "manual",
        "market_type": "futures",
        "data_source_market_type": "futures",
        "market_symbol": "BTC/USDT:USDT",
        "data_warnings": [],
    }

    def fake_eval(df, symbol, mode, timeframe, exchange_id=None, market_type="spot", config=None):
        calls.append((symbol, mode, timeframe, exchange_id, market_type))
        return {
            "decision": "LONG",
            "score": 9.0,
            "reasons": ["shared"],
            "warnings": [],
            "entry": 100.0,
            "stop_loss": 95.0,
            "take_profit": 107.5,
            "risk_reward": 1.5,
            "symbol": symbol,
            "timeframe": timeframe,
            "exchange": exchange_id,
            "market_type": market_type,
            "raw": {
                "long_score": 9,
                "short_score": 2,
                "confidence": 90,
                "direction": "LONG",
                "entry_now": True,
                "entry_price": 100.0,
                "stop_loss": 95.0,
                "take_profit_1": 107.5,
                "take_profit_2": 112.5,
                "rr_ratio": 2.5,
                "risk_pct_to_stop": 5.0,
                "main_reason": "shared",
                "action_summary": "shared",
                "missing_conditions": [],
                "volume_confirms": True,
                "price": 100.0,
                "rsi": 60.0,
                "atr": 2.0,
                "atr_pct": 2.0,
            },
        }

    try:
        patches.setattr(futures_analyzer.data_provider, "fetch_ohlcv_with_fallback", lambda *args, **kwargs: raw)
        patches.setattr(futures_analyzer.indicators, "add_indicators", lambda df: indicator_frame(len(df)))
        patches.setattr(futures_analyzer.strategy_engine, "evaluate_signal", fake_eval)
        result = futures_analyzer.analyze_futures_symbol_timeframe(
            "BTC/USDT",
            "1h",
            exchange_id="mockex",
            exchange_mode="manual",
        )
    finally:
        patches.restore()

    assert calls and calls[0] == ("BTC/USDT", "futures", "1h", "mockex", "futures"), calls
    assert result["decision"] == "LONG", result
    assert result["strategy_signal"]["score"] == 9.0, result
    assert result["long_score"] == 9, result


def main():
    test_strategy_engine_spot_signal()
    test_backtester_routes_to_strategy_engine()
    test_backtester_routes_futures_to_strategy_engine()
    test_futures_analyzer_delegates_to_strategy_engine()
    print("STRATEGY ENGINE TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
