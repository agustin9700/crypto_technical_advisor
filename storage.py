from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import config


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_storage_backend() -> str:
    return (os.getenv("STORAGE_BACKEND") or getattr(config, "STORAGE_BACKEND", "sqlite")).strip().lower()


def is_sqlite_backend() -> bool:
    return get_storage_backend() == "sqlite"


def is_csv_backend() -> bool:
    return get_storage_backend() == "csv"


def get_sqlite_path(path: str | None = None) -> str:
    return path or os.getenv("SQLITE_PATH") or getattr(config, "SQLITE_PATH", "outputs/crypto_technical_advisor.sqlite3")


def _json(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, default=str)


def _loads(value: str | None, default=None):
    if not value:
        return {} if default is None else default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {} if default is None else default


def _clean_optional(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    return text


class SQLiteStorage:
    def __init__(self, path: str | None = None):
        self.path = Path(get_sqlite_path(path))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self.path, timeout=30) as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    idempotency_key TEXT UNIQUE,
                    symbol TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    market_type TEXT NOT NULL,
                    exchange TEXT,
                    timeframe TEXT,
                    source TEXT,
                    exchange_mode TEXT,
                    decision TEXT,
                    score REAL,
                    entry REAL,
                    stop_loss REAL,
                    take_profit REAL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT,
                    initial_price REAL,
                    rr_ratio REAL,
                    status TEXT NOT NULL DEFAULT 'OPEN',
                    last_checked_at TEXT,
                    last_price REAL,
                    move_pct REAL,
                    hit_tp INTEGER NOT NULL DEFAULT 0,
                    hit_sl INTEGER NOT NULL DEFAULT 0,
                    final_verdict TEXT,
                    notes TEXT,
                    warnings_json TEXT NOT NULL DEFAULT '[]',
                    reasons_json TEXT NOT NULL DEFAULT '[]',
                    raw_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS paper_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    idempotency_key TEXT UNIQUE,
                    symbol TEXT NOT NULL,
                    mode TEXT,
                    market_type TEXT,
                    exchange TEXT,
                    timeframe TEXT,
                    side TEXT,
                    entry_price REAL,
                    stop_loss REAL,
                    take_profit REAL,
                    status TEXT NOT NULL,
                    opened_at TEXT NOT NULL,
                    closed_at TEXT,
                    close_price REAL,
                    pnl REAL,
                    pnl_pct REAL,
                    reason_open TEXT,
                    reason_close TEXT,
                    raw_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS trade_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id INTEGER,
                    event_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    raw_json TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY(trade_id) REFERENCES paper_trades(id)
                );

                CREATE TABLE IF NOT EXISTS scanner_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    mode TEXT,
                    market_type TEXT,
                    exchange TEXT,
                    raw_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS backtest_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    mode TEXT,
                    market_type TEXT,
                    exchange TEXT,
                    timeframe TEXT,
                    verdict TEXT,
                    created_at TEXT NOT NULL,
                    raw_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS validation_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT,
                    mode TEXT,
                    market_type TEXT,
                    exchange TEXT,
                    timeframe TEXT,
                    final_verdict TEXT,
                    created_at TEXT NOT NULL,
                    raw_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS cycle_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    exchange TEXT,
                    exchange_mode TEXT,
                    market_type TEXT,
                    raw_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS price_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    market_type TEXT NOT NULL,
                    exchange TEXT,
                    timeframe TEXT,
                    price REAL,
                    updated_at TEXT NOT NULL,
                    raw_json TEXT NOT NULL DEFAULT '{}',
                    UNIQUE(symbol, market_type, exchange, timeframe)
                );
                """
            )
            self._ensure_columns(conn)

    def _ensure_columns(self, conn) -> None:
        expected = {
            "signals": {
                "source": "TEXT",
                "exchange_mode": "TEXT",
                "updated_at": "TEXT",
                "initial_price": "REAL",
                "rr_ratio": "REAL",
                "status": "TEXT NOT NULL DEFAULT 'OPEN'",
                "last_checked_at": "TEXT",
                "last_price": "REAL",
                "move_pct": "REAL",
                "hit_tp": "INTEGER NOT NULL DEFAULT 0",
                "hit_sl": "INTEGER NOT NULL DEFAULT 0",
                "final_verdict": "TEXT",
                "notes": "TEXT",
            },
            "paper_trades": {
                "idempotency_key": "TEXT",
            },
        }
        for table, columns in expected.items():
            current = {
                row[1]
                for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
            }
            for column, definition in columns.items():
                if column not in current:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_paper_trades_idempotency "
            "ON paper_trades(idempotency_key)"
        )

    def insert_signal(self, signal: dict, idempotency_key: str | None = None) -> int:
        created_at = signal.get("created_at") or utc_now()
        key = idempotency_key or signal.get("idempotency_key")
        if not key:
            key = "|".join([
                str(signal.get("symbol")),
                str(signal.get("mode") or "spot"),
                str(signal.get("market_type") or "spot"),
                str(signal.get("exchange") or ""),
                str(signal.get("timeframe") or ""),
                str(signal.get("decision") or ""),
                str(signal.get("entry") or ""),
                created_at[:16],
            ])

        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO signals (
                    idempotency_key, symbol, mode, market_type, exchange, timeframe,
                    source, exchange_mode, decision, score, entry, stop_loss, take_profit, created_at,
                    updated_at, initial_price, rr_ratio, status, last_checked_at,
                    last_price, move_pct, hit_tp, hit_sl, final_verdict, notes,
                    warnings_json, reasons_json, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key,
                    signal.get("symbol"),
                    signal.get("mode") or "spot",
                    signal.get("market_type") or "spot",
                    signal.get("exchange"),
                    signal.get("timeframe"),
                    signal.get("source"),
                    signal.get("exchange_mode"),
                    signal.get("decision"),
                    signal.get("score"),
                    signal.get("entry"),
                    signal.get("stop_loss"),
                    signal.get("take_profit"),
                    created_at,
                    signal.get("updated_at") or created_at,
                    signal.get("initial_price"),
                    signal.get("rr_ratio"),
                    signal.get("status") or "OPEN",
                    signal.get("last_checked_at") or created_at,
                    signal.get("last_price"),
                    signal.get("move_pct") or 0.0,
                    int(bool(signal.get("hit_tp"))),
                    int(bool(signal.get("hit_sl"))),
                    signal.get("final_verdict"),
                    signal.get("notes"),
                    _json(signal.get("warnings") or []),
                    _json(signal.get("reasons") or []),
                    _json(signal.get("raw") or signal),
                ),
            )
            row = conn.execute("SELECT id FROM signals WHERE idempotency_key = ?", (key,)).fetchone()
            return int(row["id"])

    def upsert_tracked_signal(self, validation_row: dict) -> int:
        now = utc_now()
        created_at = validation_row.get("generated_at") or now
        symbol = validation_row.get("symbol")
        timeframe = validation_row.get("validation_timeframe") or validation_row.get("recommended_timeframe")
        exchange_mode = _clean_optional(validation_row.get("exchange_mode")) or getattr(config, "EXCHANGE_MODE", "manual")
        exchange = _clean_optional(validation_row.get("data_source_exchange"))
        market_type = _clean_optional(validation_row.get("market_type")) or "spot"
        recent_after = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

        signal = {
            "created_at": created_at,
            "updated_at": now,
            "symbol": symbol,
            "timeframe": timeframe,
            "source": "validator",
            "exchange_mode": exchange_mode,
            "exchange": exchange,
            "mode": market_type,
            "market_type": market_type,
            "decision": validation_row.get("validation_decision"),
            "final_verdict": validation_row.get("final_verdict"),
            "score": validation_row.get("validation_score"),
            "initial_price": validation_row.get("price"),
            "entry": validation_row.get("estimated_entry"),
            "stop_loss": validation_row.get("estimated_stop_loss"),
            "take_profit": validation_row.get("estimated_take_profit"),
            "rr_ratio": validation_row.get("rr_ratio"),
            "status": "OPEN",
            "last_checked_at": created_at,
            "last_price": validation_row.get("price"),
            "move_pct": 0.0,
            "hit_tp": False,
            "hit_sl": False,
            "notes": validation_row.get("reason"),
            "raw": validation_row,
        }

        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT id FROM signals
                WHERE status = 'OPEN'
                  AND symbol = ?
                  AND COALESCE(timeframe, '') = COALESCE(?, '')
                  AND COALESCE(exchange_mode, '') = COALESCE(?, '')
                  AND COALESCE(exchange, '') = COALESCE(?, '')
                  AND market_type = ?
                  AND created_at >= ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (symbol, timeframe, exchange_mode, exchange, market_type, recent_after),
            ).fetchone()
            if row:
                signal_id = int(row["id"])
                conn.execute(
                    """
                    UPDATE signals
                    SET updated_at = ?, entry = ?, stop_loss = ?, take_profit = ?,
                        rr_ratio = ?, score = ?, decision = ?, final_verdict = ?,
                        last_checked_at = ?, last_price = ?, notes = ?, raw_json = ?
                    WHERE id = ?
                    """,
                    (
                        now,
                        signal["entry"],
                        signal["stop_loss"],
                        signal["take_profit"],
                        signal["rr_ratio"],
                        signal["score"],
                        signal["decision"],
                        signal["final_verdict"],
                        signal["last_checked_at"],
                        signal["last_price"],
                        signal["notes"],
                        _json(validation_row),
                        signal_id,
                    ),
                )
                return signal_id

        key = "|".join([
            "tracked",
            str(symbol),
            str(timeframe or ""),
            str(exchange or ""),
            str(exchange_mode or ""),
            str(market_type),
            str(created_at)[:16],
        ])
        return self.insert_signal(signal, idempotency_key=key)

    def list_signals(self, status: str | None = None) -> list[dict]:
        query = "SELECT * FROM signals"
        params = ()
        if status:
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY created_at DESC"
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._signal_row_to_dict(row) for row in rows]

    def _signal_row_to_dict(self, row) -> dict:
        data = dict(row)
        data["warnings"] = _loads(data.pop("warnings_json", None), [])
        data["reasons"] = _loads(data.pop("reasons_json", None), [])
        data["raw"] = _loads(data.pop("raw_json", None), {})
        data["hit_tp"] = bool(data.get("hit_tp"))
        data["hit_sl"] = bool(data.get("hit_sl"))
        return data

    def update_tracked_signal(self, signal_id: int, updates: dict) -> None:
        allowed = {
            "status",
            "updated_at",
            "last_checked_at",
            "last_price",
            "move_pct",
            "hit_tp",
            "hit_sl",
            "notes",
            "raw",
        }
        assignments = []
        params = []
        for key, value in updates.items():
            if key not in allowed:
                continue
            column = "raw_json" if key == "raw" else key
            assignments.append(f"{column} = ?")
            if key == "raw":
                params.append(_json(value))
            elif key in {"hit_tp", "hit_sl"}:
                params.append(int(bool(value)))
            else:
                params.append(value)
        if not assignments:
            return
        params.append(signal_id)
        with self.connect() as conn:
            conn.execute(
                f"UPDATE signals SET {', '.join(assignments)} WHERE id = ?",
                tuple(params),
            )

    def insert_paper_trade(self, trade: dict) -> int:
        return self.upsert_open_paper_trade(trade, idempotency_key=trade.get("idempotency_key"), force_insert=True)

    def upsert_open_paper_trade(self, trade: dict, idempotency_key: str | None = None, force_insert: bool = False) -> int:
        key = idempotency_key or trade.get("idempotency_key")
        if not key:
            key = "|".join([
                "paper",
                str(trade.get("exchange") or ""),
                str(trade.get("symbol")),
                str(trade.get("side") or trade.get("direction") or ""),
                str(trade.get("opened_at") or ""),
                str(trade.get("entry_price") or ""),
            ])
        verb = "INSERT" if force_insert else "INSERT OR IGNORE"
        with self.connect() as conn:
            cursor = conn.execute(
                f"""
                {verb} INTO paper_trades (
                    idempotency_key, symbol, mode, market_type, exchange, timeframe, side, entry_price,
                    stop_loss, take_profit, status, opened_at, reason_open, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key,
                    trade.get("symbol"),
                    trade.get("mode") or "paper",
                    trade.get("market_type") or "spot",
                    trade.get("exchange"),
                    trade.get("timeframe"),
                    trade.get("side") or trade.get("direction"),
                    trade.get("entry_price"),
                    trade.get("stop_loss"),
                    trade.get("take_profit"),
                    trade.get("status") or "OPEN",
                    trade.get("opened_at") or utc_now(),
                    trade.get("reason_open"),
                    _json(trade.get("raw") or trade),
                ),
            )
            if cursor.lastrowid:
                return int(cursor.lastrowid)
            row = conn.execute("SELECT id FROM paper_trades WHERE idempotency_key = ?", (key,)).fetchone()
            return int(row["id"])

    def close_paper_trade(self, trade_id: int, close_price: float, pnl: float, pnl_pct: float = None,
                          reason_close: str = None, closed_at: str = None, raw: dict | None = None) -> None:
        closed_at = closed_at or utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE paper_trades
                SET status = 'CLOSED', closed_at = ?, close_price = ?, pnl = ?,
                    pnl_pct = ?, reason_close = ?, raw_json = COALESCE(?, raw_json)
                WHERE id = ?
                """,
                (closed_at, close_price, pnl, pnl_pct, reason_close, _json(raw) if raw else None, trade_id),
            )
            conn.execute(
                """
                INSERT INTO trade_events (trade_id, event_type, created_at, raw_json)
                VALUES (?, 'CLOSED', ?, ?)
                """,
                (trade_id, closed_at, _json({"close_price": close_price, "pnl": pnl, "reason": reason_close})),
            )

    def list_paper_trades(self, status: str | None = None) -> list[dict]:
        query = "SELECT * FROM paper_trades"
        params = ()
        if status:
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY opened_at"
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        result = []
        for row in rows:
            data = dict(row)
            raw = _loads(data.pop("raw_json", None), {})
            merged = dict(raw)
            merged.update(data)
            merged["raw"] = raw
            result.append(merged)
        return result

    def get_open_trades(self) -> list[dict]:
        return self.list_paper_trades(status="OPEN")

    def insert_scanner_run(self, scan_result: dict) -> int:
        now = scan_result.get("generated_at") or utc_now()
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO scanner_runs (
                    started_at, finished_at, mode, market_type, exchange, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    now,
                    utc_now(),
                    scan_result.get("scan_mode"),
                    scan_result.get("market_type") or "spot",
                    scan_result.get("data_source_exchange"),
                    _json(scan_result),
                ),
            )
            return int(cursor.lastrowid)

    def get_latest_scanner_rows(self) -> list[dict]:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT raw_json FROM scanner_runs ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if not row:
            return []
        raw = _loads(row["raw_json"], {})
        return list(raw.get("rows") or [])

    def insert_validation_results(self, rows: list[dict]) -> None:
        if not rows:
            return
        with self.connect() as conn:
            for row in rows:
                conn.execute(
                    """
                    INSERT INTO validation_results (
                        symbol, mode, market_type, exchange, timeframe,
                        final_verdict, created_at, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("symbol"),
                        row.get("market_type") or "spot",
                        row.get("market_type") or "spot",
                        row.get("data_source_exchange"),
                        row.get("validation_timeframe"),
                        row.get("final_verdict"),
                        row.get("generated_at") or utc_now(),
                        _json(row),
                    ),
                )

    def insert_backtest_result(self, result: dict) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO backtest_results (
                    symbol, mode, market_type, exchange, timeframe,
                    verdict, created_at, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.get("symbol"),
                    result.get("mode"),
                    result.get("market_type"),
                    result.get("exchange"),
                    result.get("timeframe"),
                    result.get("verdict"),
                    utc_now(),
                    _json(result),
                ),
            )
            return int(cursor.lastrowid)

    def insert_cycle_summary(self, row: dict) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO cycle_runs (
                    created_at, exchange, exchange_mode, market_type, raw_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    row.get("generated_at") or utc_now(),
                    row.get("data_source_exchange"),
                    row.get("exchange_mode"),
                    row.get("market_type") or "spot",
                    _json(row),
                ),
            )
            return int(cursor.lastrowid)


def get_storage(path: str | None = None) -> SQLiteStorage:
    return SQLiteStorage(path)
