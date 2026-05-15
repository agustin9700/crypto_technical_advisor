import io
import sys
from contextlib import redirect_stdout

import pandas as pd

import cli
import futures_analyzer
import technical_analyzer


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


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


def synthetic_ohlcv(rows: int = 240, base: float = 100.0) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=rows, freq="h", tz="UTC")
    close = pd.Series([base + i * 0.01 for i in range(rows)])
    return pd.DataFrame({
        "timestamp": range(rows),
        "datetime": dates,
        "open": close,
        "high": close + 1,
        "low": close - 1,
        "close": close,
        "volume": [1000.0] * rows,
    })


def indicator_frame(kind: str) -> pd.DataFrame:
    df = synthetic_ohlcv()
    if kind == "long":
        values = {
            "close": 120.0,
            "ema20": 116.0,
            "ema50": 112.0,
            "ema200": 100.0,
            "rsi": 62.0,
            "macd": 2.0,
            "macd_signal": 1.0,
            "vol_ratio": 1.5,
            "atr": 2.0,
            "atr_pct": 1.7,
        }
    elif kind == "short":
        values = {
            "close": 80.0,
            "ema20": 84.0,
            "ema50": 88.0,
            "ema200": 100.0,
            "rsi": 38.0,
            "macd": -2.0,
            "macd_signal": -1.0,
            "vol_ratio": 1.5,
            "atr": 2.0,
            "atr_pct": 2.5,
        }
    elif kind == "neutral":
        values = {
            "close": 100.0,
            "ema20": 100.0,
            "ema50": 100.0,
            "ema200": 100.0,
            "rsi": 50.0,
            "macd": 0.0,
            "macd_signal": 0.0,
            "vol_ratio": 0.9,
            "atr": 2.0,
            "atr_pct": 2.0,
        }
    else:
        raise ValueError(kind)

    for column, value in values.items():
        df[column] = value
    df["bb_mid"] = df["close"]
    df["bb_upper"] = df["close"] + 4
    df["bb_lower"] = df["close"] - 4
    df["macd_hist"] = df["macd"] - df["macd_signal"]
    df["vol_ma20"] = df["volume"] / df["vol_ratio"].replace(0, pd.NA)
    return df


def run_timeframe_case(kind: str):
    patches = PatchSet()
    try:
        raw = synthetic_ohlcv()
        raw.attrs = {
            "exchange_id": "mockex",
            "exchange_mode": "manual",
            "fallback_used": False,
            "data_source_error": "",
        }
        patches.setattr(futures_analyzer, "_fetch_ohlcv_cached", lambda *args, **kwargs: raw)
        patches.setattr(futures_analyzer.indicators, "add_indicators", lambda df: indicator_frame(kind))
        if kind == "long":
            patches.setattr(futures_analyzer.strategy_engine, "_latest_futures_levels", lambda df, price: ([95], [118], 95, 130, 118, None))
            patches.setattr(futures_analyzer.strategy_engine, "_futures_structure_flags", lambda df: (True, False))
        elif kind == "short":
            patches.setattr(futures_analyzer.strategy_engine, "_latest_futures_levels", lambda df, price: ([82], [105], 70, 105, None, 82))
            patches.setattr(futures_analyzer.strategy_engine, "_futures_structure_flags", lambda df: (False, True))
        else:
            patches.setattr(futures_analyzer.strategy_engine, "_latest_futures_levels", lambda df, price: ([95], [105], 95, 105, None, None))
            patches.setattr(futures_analyzer.strategy_engine, "_futures_structure_flags", lambda df: (False, False))
        return futures_analyzer.analyze_futures_symbol_timeframe(
            "TEST/USDT",
            "1h",
            exchange_id="mockex",
            exchange_mode="manual",
        )
    finally:
        patches.restore()


def test_long_clear():
    result = run_timeframe_case("long")
    assert result["decision"] == "LONG", result
    assert result["direction"] == "LONG", result
    assert result["entry_now"] in [True, False], result
    assert result["long_score"] >= 7, result
    assert result["long_score"] >= result["short_score"] + 2, result
    assert result["stop_loss"] < result["entry_price"], result
    assert result["take_profit_1"] > result["entry_price"], result
    assert result["take_profit_2"] > result["entry_price"], result
    assert result["rr_ratio"] >= 1.0, result


def test_short_clear():
    result = run_timeframe_case("short")
    assert result["decision"] == "SHORT", result
    assert result["direction"] == "SHORT", result
    assert result["short_score"] >= 7, result
    assert result["short_score"] >= result["long_score"] + 2, result
    assert result["stop_loss"] > result["entry_price"], result
    assert result["take_profit_1"] < result["entry_price"], result
    assert result["take_profit_2"] < result["entry_price"], result
    assert result["rr_ratio"] >= 1.0, result


def test_neutral_no_setup():
    result = run_timeframe_case("neutral")
    assert result["decision"] in ["WAIT", "AVOID"], result
    assert result["direction"] == "NEUTRAL", result


def test_data_unavailable():
    patches = PatchSet()
    try:
        patches.setattr(
            futures_analyzer,
            "_fetch_ohlcv_cached",
            lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("mock network down")),
        )
        result = futures_analyzer.analyze_futures_symbol_timeframe(
            "TEST/USDT",
            "1h",
            exchange_id="mockex",
            exchange_mode="manual",
        )
    finally:
        patches.restore()

    assert result["decision"] == "DATA_UNAVAILABLE", result
    assert result["status"] == "DATA_UNAVAILABLE", result
    assert result["data_source_error"] is not None, result
    assert result["decision"] != "AVOID", result


def auto_result(timeframe: str, decision: str, long_score: int, short_score: int, volume_confirms: bool = True):
    direction = "LONG" if decision == "LONG" else "SHORT" if decision == "SHORT" else "NEUTRAL"
    return {
        "mode": "FUTURES",
        "symbol": "TEST/USDT",
        "timeframe": timeframe,
        "recommended_timeframe": timeframe,
        "decision": decision,
        "direction": direction,
        "entry_now": decision in ("LONG", "SHORT") and volume_confirms,
        "entry_price": 100.0,
        "stop_loss": 95.0,
        "take_profit_1": 107.5,
        "take_profit_2": 112.5,
        "rr_ratio": 2.5,
        "risk_pct_to_stop": 5.0,
        "long_score": long_score,
        "short_score": short_score,
        "confidence": max(long_score, short_score) * 10,
        "main_reason": "mock",
        "action_summary": "mock",
        "missing_conditions": [],
        "warnings": [],
        "invalidation": "mock",
        "suggested_leverage_label": "bajo",
        "suggested_leverage_max": 2,
        "leverage_warning": futures_analyzer.LEVERAGE_WARNING,
        "data_source_exchange": "mockex",
        "exchange_mode": "manual",
        "fallback_used": False,
        "data_source_error": "",
        "volume_confirms": volume_confirms,
        "no_clear_setup": decision not in ("LONG", "SHORT"),
    }


def test_auto_timeframe_prefers_1h_over_15m_when_similar():
    patches = PatchSet()
    mapping = {
        "15m": auto_result("15m", "LONG", 8, 5, True),
        "1h": auto_result("1h", "LONG", 8, 5, True),
        "4h": auto_result("4h", "WAIT", 6, 5, False),
    }
    try:
        patches.setattr(
            futures_analyzer,
            "analyze_futures_symbol_timeframe",
            lambda symbol, timeframe, **kwargs: mapping.get(timeframe, auto_result(timeframe, "WAIT", 5, 5, False)),
        )
        result = futures_analyzer.analyze_futures_symbol_auto("TEST/USDT", timeframes=["15m", "1h", "4h"])
    finally:
        patches.restore()

    assert result["recommended_timeframe"] == "1h", result


def test_auto_timeframe_allows_15m_only_when_strict_rules_pass():
    patches = PatchSet()
    mapping = {
        "15m": auto_result("15m", "LONG", 8, 4, True),
        "1h": auto_result("1h", "WAIT", 5, 5, False),
        "2h": auto_result("2h", "WAIT", 5, 5, False),
        "4h": auto_result("4h", "WAIT", 6, 5, False),
    }
    try:
        patches.setattr(
            futures_analyzer,
            "analyze_futures_symbol_timeframe",
            lambda symbol, timeframe, **kwargs: mapping[timeframe],
        )
        result = futures_analyzer.analyze_futures_symbol_auto("TEST/USDT", timeframes=["15m", "1h", "2h", "4h"])
    finally:
        patches.restore()

    assert result["recommended_timeframe"] == "15m", result
    assert result["decision"] == "LONG", result


def test_leverage_defensive():
    cases = [
        (0.8, 2),
        (1.5, 3),
        (3.0, 2),
    ]
    for risk_pct, expected_max in cases:
        result = futures_analyzer.strategy_engine.futures_leverage_fields(risk_pct, atr_pct=1.0)
        assert result["suggested_leverage_label"], result
        assert result["suggested_leverage_max"] <= 3, result
        assert result["suggested_leverage_max"] == expected_max, result
        assert "apalancamiento" in result["leverage_warning"].lower(), result

    high_vol = futures_analyzer.strategy_engine.futures_leverage_fields(1.5, atr_pct=5.0)
    assert high_vol["suggested_leverage_max"] <= 2, high_vol


def test_cli_futures_routes_to_futures_analyzer():
    patches = PatchSet()
    calls = {"futures": 0, "spot": 0}

    def fake_futures_auto(symbol, **kwargs):
        calls["futures"] += 1
        return auto_result("1h", "LONG", 8, 4, True)

    def fake_spot(*args, **kwargs):
        calls["spot"] += 1
        raise AssertionError("technical_analyzer should not be called when --futures is active")

    old_argv = sys.argv[:]
    try:
        patches.setattr(cli.futures_analyzer, "analyze_futures_symbol_auto", fake_futures_auto)
        patches.setattr(technical_analyzer, "analyze_symbol_auto", fake_spot)
        sys.argv = [
            "cli.py",
            "--futures",
            "--symbol",
            "BTC/USDT",
            "--auto",
            "--exchange",
            "kucoin",
            "--exchange-mode",
            "manual",
        ]
        with redirect_stdout(io.StringIO()) as buffer:
            cli.main()
        output = buffer.getvalue()
    finally:
        sys.argv = old_argv
        patches.restore()

    assert calls["futures"] == 1, calls
    assert calls["spot"] == 0, calls
    assert "FUTURES" in output, output


def run_test(name, fn):
    try:
        fn()
        print(f"OK: {name}", flush=True)
    except Exception as exc:
        print(f"FAILED: {name}: {exc}", flush=True)
        raise


def main():
    tests = [
        ("LONG claro", test_long_clear),
        ("SHORT claro", test_short_clear),
        ("neutral sin setup", test_neutral_no_setup),
        ("DATA_UNAVAILABLE", test_data_unavailable),
        ("auto timeframe prefiere 1h", test_auto_timeframe_prefers_1h_over_15m_when_similar),
        ("auto timeframe permite 15m estricto", test_auto_timeframe_allows_15m_only_when_strict_rules_pass),
        ("leverage defensivo", test_leverage_defensive),
        ("CLI routing futures", test_cli_futures_routes_to_futures_analyzer),
    ]
    for name, fn in tests:
        run_test(name, fn)
    print("FUTURES SMOKE TESTS PASSED ✅", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
