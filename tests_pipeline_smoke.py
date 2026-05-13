import csv
import faulthandler
import os
import shutil
import sys
import traceback
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

import backtester
import config
import scanner
import signal_tracker
import technical_analyzer
import validator


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


@contextmanager
def patched_environment():
    patches = PatchSet()
    output_dir = Path.cwd() / ".cta_pipeline_smoke"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    patches.setattr(config, "OUTPUT_DIR", str(output_dir))
    patches.setattr(signal_tracker, "SIGNAL_CSV_PATH", str(output_dir / "signal_history.csv"))
    patches.setattr(signal_tracker, "SIGNAL_MD_PATH", str(output_dir / "signal_status.md"))
    try:
        yield output_dir, patches
    finally:
        patches.restore()
        if output_dir.exists():
            shutil.rmtree(output_dir)


def fake_backtest(symbol, timeframe):
    return {
        "verdict": "BACKTEST_OK",
        "profit_factor": 1.7,
        "total_return_pct": 12.3,
        "max_drawdown_pct": -4.5,
    }


def fake_scan_analysis(symbol, timeframes=None, **kwargs):
    setups = {
        "BETA/USDT": ("ENTER_NOW_CANDIDATE", 9, "1h"),
        "GAMMA/USDT": ("ENTER_NOW_CANDIDATE", 8, "2h"),
        "ALPHA/USDT": ("WAIT", 7, "4h"),
        "DELTA/USDT": ("AVOID", 10, "1h"),
        "NODATA/USDT": ("DATA_UNAVAILABLE", 0, None),
    }
    decision, score, recommended_tf = setups[symbol]
    confidence = score * 10 if score else 0

    best = {
        "symbol": symbol,
        "timeframe": recommended_tf,
        "decision": decision,
        "score": score,
        "confidence": confidence,
        "price": 1.0,
        "rsi": 50,
        "rr_ratio": 2.0,
        "closed_candle_vol_ratio": 1.2,
        "estimated_entry": 1.0,
        "estimated_stop_loss": 0.9,
        "estimated_take_profit": 1.2,
        "risk_pct": 10,
        "reward_pct": 20,
        "entry_now_text": "mock entry text",
        "main_reason": "mock reason",
        "entry_trigger": "mock trigger",
        "warnings": [],
    }

    timeframe_results = {}
    if decision != "DATA_UNAVAILABLE":
        selected_timeframes = list(timeframes or ["1h", "2h", "4h"])
        for tf in selected_timeframes[:3]:
            timeframe_results[tf] = dict(best, timeframe=tf)

    return {
        "symbol": symbol,
        "decision": decision,
        "recommended_timeframe": recommended_tf,
        "best_setup": best,
        "timeframe_results": timeframe_results,
        "exchange_mode": kwargs.get("exchange_mode") or "manual",
        "data_source_exchange": kwargs.get("exchange_id") or "mockex",
        "fallback_used": False,
        "warnings": [],
    }


def fake_fetch_scan_symbols(limit, min_quote_volume, exclude_stablecoins=True, exchange_id=None, exchange_mode=None):
    symbols = [
        ("ALPHA/USDT", 1_000_000),
        ("BETA/USDT", 2_000_000),
        ("GAMMA/USDT", 1_500_000),
        ("DELTA/USDT", 900_000),
        ("NODATA/USDT", 800_000),
    ]
    return symbols[:limit], [], {"stablecoins_excluded": 0}, {
        "exchange_id": exchange_id or "mockex",
        "exchange_mode": exchange_mode or "manual",
        "data_source_status": "OK",
        "fallback_used": False,
        "data_source_error": "",
    }


def test_scanner_ranks_and_backtest_rows(output_dir, patches):
    patches.setattr(scanner, "_fetch_scan_symbols", fake_fetch_scan_symbols)
    patches.setattr(technical_analyzer, "analyze_symbol_auto", fake_scan_analysis)
    patches.setattr(technical_analyzer, "apply_backtest_to_analysis", lambda analysis, backtest: analysis)
    patches.setattr(backtester, "run_quick_backtest", fake_backtest)

    result = scanner.run_scan(
        limit=5,
        mode="full",
        backtest_top_n=3,
        workers=1,
        output_dir=str(output_dir),
        exchange_id="mockex",
        exchange_mode="manual",
        exclude_low_history=True,
    )

    rows = result["rows"]
    ranks = [row.get("rank") for row in rows]
    assert ranks == [1, 2, 3, 4, 5], f"scanner ranks should be 1..5, got {ranks}"
    assert all(rank is not None for rank in ranks), f"scanner ranks include None: {ranks}"

    with open(result["csv_path"], newline="", encoding="utf-8") as f:
        csv_rows = list(csv.DictReader(f))
    csv_ranks = [int(row["rank"]) for row in csv_rows]
    assert csv_ranks == [1, 2, 3, 4, 5], f"CSV ranks should be 1..5, got {csv_ranks}"

    backtested_rows = [row for row in rows if row.get("backtest_verdict")]
    assert len(backtested_rows) == 3, f"expected 3 backtested rows, got {len(backtested_rows)}"
    for row in backtested_rows:
        assert row.get("backtest_verdict") == "BACKTEST_OK", f"missing backtest verdict in {row}"
        assert row.get("backtest_profit_factor") == 1.7, f"missing profit factor in {row}"
        assert row.get("backtest_total_return_pct") == 12.3, f"missing return pct in {row}"
        assert row.get("backtest_max_drawdown_pct") == -4.5, f"missing drawdown pct in {row}"
        assert row.get("validation_status") == "BACKTEST_CONFIRMED", f"unexpected validation status in {row}"

    with open(result["md_path"], encoding="utf-8") as f:
        markdown = f.read()
    assert "BACKTEST_OK" in markdown, "latest_scan.md should include backtest verdicts"
    assert "Return %" in markdown, "latest_scan.md should include backtest columns"

    counts = result["decision_counts"]
    assert counts.get("DATA_UNAVAILABLE") == 1, f"DATA_UNAVAILABLE count wrong: {counts}"
    assert counts.get("AVOID") == 1, f"DATA_UNAVAILABLE must not be counted as AVOID: {counts}"


def write_latest_scan(output_dir, row):
    df = pd.DataFrame([row])
    df.to_csv(output_dir / "latest_scan.csv", index=False)


def test_validator_timeframe_lock(output_dir, patches):
    called_timeframes = []

    def fake_validator_analysis(symbol, timeframes=None, **kwargs):
        called_timeframes.append(list(timeframes) if timeframes is not None else None)
        tf = timeframes[0]
        best = {
            "symbol": symbol,
            "timeframe": tf,
            "decision": "WAIT",
            "score": 7,
            "price": 1.0,
            "rsi": 50,
            "closed_candle_vol_ratio": 1.1,
            "estimated_entry": 1.0,
            "estimated_stop_loss": 0.9,
            "estimated_take_profit": 1.2,
            "rr_ratio": 2.0,
            "action_summary": "mock action",
        }
        return {
            "symbol": symbol,
            "decision": "WAIT",
            "recommended_timeframe": tf,
            "best_setup": best,
            "exchange_mode": kwargs.get("exchange_mode"),
            "data_source_exchange": kwargs.get("exchange_id"),
            "fallback_used": False,
        }

    write_latest_scan(output_dir, {
        "rank": 1,
        "symbol": "TEST/USDT",
        "decision": "WAIT",
        "recommended_timeframe": "2h",
        "score": 7,
        "exchange_mode": "manual",
        "data_source_exchange": "mockex",
    })
    patches.setattr(technical_analyzer, "analyze_symbol_auto", fake_validator_analysis)
    patches.setattr(technical_analyzer, "apply_backtest_to_analysis", lambda analysis, backtest: analysis)
    patches.setattr(backtester, "run_quick_backtest", fake_backtest)
    patches.setattr(signal_tracker, "record_signal", lambda validation_row: None)

    result = validator.run_validation(top_n=1, exchange_id="mockex", exchange_mode="manual")
    assert called_timeframes == [["2h"]], f"validator should lock to ['2h'], got {called_timeframes}"
    assert result["results"][0]["validation_timeframe"] == "2h", result["results"][0]


def test_validator_data_unavailable_not_avoid(output_dir, patches):
    def should_not_call_analyzer(*args, **kwargs):
        raise AssertionError("analyzer should not run when scanner timeframe is missing")

    write_latest_scan(output_dir, {
        "rank": 1,
        "symbol": "NODATA/USDT",
        "decision": "DATA_UNAVAILABLE",
        "recommended_timeframe": "",
        "score": 0,
        "exchange_mode": "manual",
        "data_source_exchange": "mockex",
    })
    patches.setattr(technical_analyzer, "analyze_symbol_auto", should_not_call_analyzer)
    patches.setattr(signal_tracker, "record_signal", lambda validation_row: None)

    result = validator.run_validation(top_n=1, exchange_id="mockex", exchange_mode="manual")
    row = result["results"][0]
    assert row["validation_decision"] == "DATA_UNAVAILABLE", row
    assert row["validation_decision"] != "AVOID", row
    assert row["final_verdict"] == "NO_CLEAR_SETUP", row


def test_signal_tracker_grouping(output_dir, patches):
    created_at = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    rows = []
    for idx in range(3):
        rows.append({
            "created_at": created_at,
            "symbol": "TEST/USDT",
            "timeframe": "2h",
            "source": "validator",
            "exchange_mode": "manual",
            "data_source_exchange": "mockex",
            "initial_decision": "WAIT",
            "final_verdict": "WATCHLIST",
            "initial_price": 1.0 + idx * 0.1,
            "estimated_entry": 1.0 + idx * 0.1,
            "estimated_stop_loss": 0.5,
            "estimated_take_profit": 99.0,
            "rr_ratio": 2.0,
            "status": "OPEN",
            "last_checked_at": created_at,
            "last_price": 1.0 + idx * 0.1,
            "move_pct": 0.0,
            "hit_tp": False,
            "hit_sl": False,
            "notes": "mock",
        })
    pd.DataFrame(rows, columns=signal_tracker.COLUMNS).to_csv(signal_tracker.SIGNAL_CSV_PATH, index=False)

    fetch_calls = []

    def fake_fetch_ohlcv(symbol, timeframe, days=8, exchange_id=None, exchange_mode=None):
        fetch_calls.append((symbol, timeframe, exchange_id, exchange_mode))
        now = pd.Timestamp.now(tz="UTC")
        return pd.DataFrame({
            "datetime": [now - pd.Timedelta(minutes=30), now],
            "close": [1.2, 1.3],
            "high": [1.3, 1.4],
            "low": [1.0, 1.1],
        })

    patches.setattr(signal_tracker.data_provider, "fetch_ohlcv", fake_fetch_ohlcv)
    result = signal_tracker.update_signals()

    assert len(fetch_calls) == 1, f"expected 1 OHLCV request for grouped signals, got {fetch_calls}"
    assert result.get("ohlcv_requests") == 1, f"expected ohlcv_requests=1, got {result}"
    assert result.get("updated") == 3, f"expected 3 updated signals, got {result}"


def run_test(name, fn, output_dir, patches):
    try:
        fn(output_dir, patches)
        print(f"OK: {name}", flush=True)
    except Exception as exc:
        print(f"FAILED: {name}: {exc}", flush=True)
        raise


def main():
    faulthandler.dump_traceback_later(60, exit=True)
    tests = [
        ("scanner ranks and backtest rows", test_scanner_ranks_and_backtest_rows),
        ("validator timeframe lock", test_validator_timeframe_lock),
        ("validator DATA_UNAVAILABLE handling", test_validator_data_unavailable_not_avoid),
        ("signal tracker OHLCV grouping", test_signal_tracker_grouping),
    ]

    try:
        with patched_environment() as (output_dir, patches):
            for name, fn in tests:
                run_test(name, fn, output_dir, patches)
    except Exception:
        traceback.print_exc()
        return 1

    faulthandler.cancel_dump_traceback_later()
    print("PIPELINE SMOKE TESTS PASSED ✅", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
