import shutil
import gc
import os
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import config
import paper_trader
import signal_tracker
import storage


def test_sqlite_storage_roundtrip():
    tmp = Path.cwd() / ".cta_storage_test"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        db_path = tmp / "cta.sqlite3"
        db = storage.SQLiteStorage(str(db_path))

        signal = {
            "symbol": "BTC/USDT",
            "mode": "spot",
            "market_type": "spot",
            "exchange": "kucoin",
            "timeframe": "1h",
            "decision": "ENTER_NOW_CANDIDATE",
            "score": 8,
            "entry": 100.0,
            "stop_loss": 95.0,
            "take_profit": 110.0,
            "warnings": [],
            "reasons": ["mock"],
            "raw": {"source": "test"},
        }
        first_id = db.insert_signal(signal, idempotency_key="same-signal")
        second_id = db.insert_signal(signal, idempotency_key="same-signal")
        assert first_id == second_id

        trade_id = db.insert_paper_trade({
            "symbol": "BTC/USDT",
            "mode": "paper",
            "market_type": "spot",
            "exchange": "kucoin",
            "timeframe": "1h",
            "side": "LONG",
            "entry_price": 100.0,
            "stop_loss": 95.0,
            "take_profit": 110.0,
        })
        open_trades = db.get_open_trades()
        assert len(open_trades) == 1
        assert open_trades[0]["id"] == trade_id

        db.close_paper_trade(trade_id, close_price=110.0, pnl=10.0, pnl_pct=10.0, reason_close="TP")
        assert db.get_open_trades() == []
    finally:
        try:
            del db
        except UnboundLocalError:
            pass
        gc.collect()
        if tmp.exists():
            for _ in range(5):
                shutil.rmtree(tmp, ignore_errors=True)
                if not tmp.exists():
                    break
                time.sleep(0.1)


def test_sqlite_storage_concurrent_writers():
    tmp = Path.cwd() / ".cta_storage_test_concurrent"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        db = storage.SQLiteStorage(str(tmp / "cta.sqlite3"))

        def write_signal(i):
            return db.upsert_tracked_signal({
                "generated_at": f"2026-01-01T00:{i:02d}:00+00:00",
                "symbol": f"BTC{i}/USDT",
                "validation_timeframe": "1h",
                "exchange_mode": "manual",
                "market_type": "spot",
                "data_source_exchange": "mockex",
                "validation_decision": "ENTER_NOW_CANDIDATE",
                "final_verdict": "WATCHLIST",
                "validation_score": 7,
                "price": 100 + i,
                "estimated_entry": 100 + i,
                "estimated_stop_loss": 95 + i,
                "estimated_take_profit": 110 + i,
                "rr_ratio": 2.0,
                "reason": "test",
            })

        with ThreadPoolExecutor(max_workers=4) as executor:
            ids = list(executor.map(write_signal, range(12)))

        assert len(set(ids)) == 12
        assert len(db.list_signals(status="OPEN")) == 12
    finally:
        gc.collect()
        shutil.rmtree(tmp, ignore_errors=True)


def test_sqlite_backend_does_not_write_csv_outputs():
    tmp = Path.cwd() / ".cta_storage_test_outputs"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    old_backend = os.environ.get("STORAGE_BACKEND")
    old_sqlite = os.environ.get("SQLITE_PATH")
    old_config_backend = config.STORAGE_BACKEND
    old_output_dir = config.OUTPUT_DIR
    try:
        os.environ["STORAGE_BACKEND"] = "sqlite"
        os.environ["SQLITE_PATH"] = str(tmp / "outputs" / "cta.sqlite3")
        config.STORAGE_BACKEND = "sqlite"
        config.OUTPUT_DIR = str(tmp / "outputs")

        trader = paper_trader.PaperTrader.load_from_report(exchange_id="mockex", capital_usdt=1000.0)
        trader.open_position({
            "symbol": "BTC/USDT",
            "direction": "LONG",
            "entry_price": 100.0,
            "sl_price": 95.0,
            "tp_price": 110.0,
            "score": 8,
            "timeframe": "1h",
            "source_signal": "TEST",
        })
        signal_tracker.record_signal({
            "generated_at": "2026-01-01T00:00:00+00:00",
            "symbol": "ETH/USDT",
            "validation_timeframe": "1h",
            "exchange_mode": "manual",
            "market_type": "spot",
            "data_source_exchange": "mockex",
            "validation_decision": "ENTER_NOW_CANDIDATE",
            "final_verdict": "WATCHLIST",
            "validation_score": 7,
            "price": 100.0,
            "estimated_entry": 100.0,
            "estimated_stop_loss": 95.0,
            "estimated_take_profit": 110.0,
            "rr_ratio": 2.0,
            "reason": "test",
        })

        csv_files = list((tmp / "outputs").glob("*.csv"))
        assert csv_files == [], csv_files
        assert (tmp / "outputs" / "cta.sqlite3").exists()
    finally:
        if old_backend is None:
            os.environ.pop("STORAGE_BACKEND", None)
        else:
            os.environ["STORAGE_BACKEND"] = old_backend
        if old_sqlite is None:
            os.environ.pop("SQLITE_PATH", None)
        else:
            os.environ["SQLITE_PATH"] = old_sqlite
        config.STORAGE_BACKEND = old_config_backend
        config.OUTPUT_DIR = old_output_dir
        gc.collect()
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    test_sqlite_storage_roundtrip()
    test_sqlite_storage_concurrent_writers()
    test_sqlite_backend_does_not_write_csv_outputs()
    print("STORAGE SQLITE TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
