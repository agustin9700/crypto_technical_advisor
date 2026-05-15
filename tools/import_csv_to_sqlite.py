#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import storage


ROOT = Path(__file__).resolve().parents[1]


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def import_latest_scan(db: storage.SQLiteStorage, outputs_dir: Path) -> int:
    count = 0
    for row in _read_csv(outputs_dir / "latest_scan.csv"):
        db.insert_signal({
            "symbol": row.get("symbol"),
            "mode": "spot",
            "market_type": row.get("market_type") or "spot",
            "exchange": row.get("data_source_exchange"),
            "timeframe": row.get("recommended_timeframe"),
            "decision": row.get("decision"),
            "score": row.get("score"),
            "entry": row.get("estimated_entry"),
            "stop_loss": row.get("estimated_stop_loss"),
            "take_profit": row.get("estimated_take_profit"),
            "created_at": row.get("generated_at"),
            "warnings": [row.get("warnings")] if row.get("warnings") else [],
            "raw": row,
        })
        count += 1
    return count


def import_paper_trades(db: storage.SQLiteStorage, outputs_dir: Path) -> int:
    count = 0
    for row in _read_csv(outputs_dir / "paper_trading_report.csv"):
        db.insert_paper_trade({
            "symbol": row.get("symbol"),
            "mode": "paper",
            "market_type": row.get("market_type") or "spot",
            "exchange": row.get("exchange") or row.get("data_source_exchange"),
            "timeframe": row.get("timeframe"),
            "side": row.get("direction") or row.get("side"),
            "entry_price": row.get("entry_price"),
            "stop_loss": row.get("sl_price") or row.get("stop_loss"),
            "take_profit": row.get("tp_price") or row.get("take_profit"),
            "status": row.get("status") or "OPEN",
            "opened_at": row.get("entry_time") or row.get("opened_at"),
            "raw": row,
        })
        count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Import runtime CSV files into SQLite storage.")
    parser.add_argument("--db", default=None, help="SQLite path. Defaults to SQLITE_PATH/config.")
    parser.add_argument("--outputs", default=str(ROOT / "outputs"), help="Outputs directory.")
    args = parser.parse_args()

    db = storage.get_storage(args.db)
    outputs_dir = Path(args.outputs)
    scan_count = import_latest_scan(db, outputs_dir)
    paper_count = import_paper_trades(db, outputs_dir)
    print(f"Imported signals: {scan_count}")
    print(f"Imported paper trades: {paper_count}")
    print(f"SQLite DB: {db.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
