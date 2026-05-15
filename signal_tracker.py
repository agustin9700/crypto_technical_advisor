import os
import csv
import pandas as pd
from datetime import datetime, timezone, timedelta

import config
import data_provider
import storage
import utils

# Helper alias
_clean_optional = utils.clean_optional

SIGNAL_CSV_PATH = os.path.join(config.OUTPUT_DIR, "signal_history.csv")
SIGNAL_MD_PATH = os.path.join(config.OUTPUT_DIR, "signal_status.md")

COLUMNS = [
    "id", "created_at", "symbol", "timeframe", "source", "exchange_mode",
    "market_type",
    "data_source_exchange", "initial_decision",
    "final_verdict", "initial_price", "estimated_entry", "estimated_stop_loss", 
    "estimated_take_profit", "rr_ratio", "status", "last_checked_at", 
    "last_price", "move_pct", "hit_tp", "hit_sl", "strategy_profile", "notes"
]


def _ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    changed = False
    for column in COLUMNS:
        if column not in df.columns:
            df[column] = None
            changed = True
    if changed:
        extra_columns = [column for column in df.columns if column not in COLUMNS]
        df = df[COLUMNS + extra_columns]
    return df


def _ensure_file():
    if storage.is_sqlite_backend():
        storage.get_storage()
        return
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    if not os.path.exists(SIGNAL_CSV_PATH):
        df = pd.DataFrame(columns=COLUMNS)
        df.to_csv(SIGNAL_CSV_PATH, index=False)
        return

    try:
        df = pd.read_csv(SIGNAL_CSV_PATH)
    except pd.errors.EmptyDataError:
        df = pd.DataFrame(columns=COLUMNS)
        df.to_csv(SIGNAL_CSV_PATH, index=False)
        return

    migrated_df = _ensure_columns(df)
    if list(migrated_df.columns) != list(df.columns):
        migrated_df.to_csv(SIGNAL_CSV_PATH, index=False)


def _to_utc_timestamp(value):
    timestamp = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(timestamp):
        return None
    return timestamp





def _storage_row_to_tracking_row(row: dict) -> dict:
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
    return {
        "id": row.get("id"),
        "created_at": row.get("created_at"),
        "symbol": row.get("symbol"),
        "timeframe": row.get("timeframe"),
        "source": row.get("source") or raw.get("source") or "validator",
        "exchange_mode": row.get("exchange_mode") or raw.get("exchange_mode"),
        "market_type": row.get("market_type") or raw.get("market_type") or "spot",
        "data_source_exchange": row.get("exchange") or raw.get("data_source_exchange"),
        "initial_decision": row.get("decision") or raw.get("validation_decision"),
        "final_verdict": row.get("final_verdict") or raw.get("final_verdict"),
        "initial_price": row.get("initial_price") or raw.get("price"),
        "estimated_entry": row.get("entry") or raw.get("estimated_entry"),
        "estimated_stop_loss": row.get("stop_loss") or raw.get("estimated_stop_loss"),
        "estimated_take_profit": row.get("take_profit") or raw.get("estimated_take_profit"),
        "rr_ratio": row.get("rr_ratio") or raw.get("rr_ratio"),
        "status": row.get("status") or "OPEN",
        "last_checked_at": row.get("last_checked_at") or row.get("created_at"),
        "last_price": row.get("last_price") or row.get("initial_price") or raw.get("price"),
        "move_pct": row.get("move_pct") or 0.0,
        "hit_tp": bool(row.get("hit_tp")),
        "hit_sl": bool(row.get("hit_sl")),
        "strategy_profile": row.get("strategy_profile") or raw.get("strategy_profile"),
        "notes": row.get("notes") or raw.get("reason"),
    }


def load_signals_dataframe() -> pd.DataFrame:
    if storage.is_sqlite_backend():
        rows = [_storage_row_to_tracking_row(row) for row in storage.get_storage().list_signals()]
        return _ensure_columns(pd.DataFrame(rows, columns=COLUMNS))

    _ensure_file()
    try:
        return _ensure_columns(pd.read_csv(SIGNAL_CSV_PATH))
    except pd.errors.EmptyDataError:
        return _ensure_columns(pd.DataFrame(columns=COLUMNS))


def record_signal(validation_row: dict):
    if storage.is_sqlite_backend():
        storage.get_storage().upsert_tracked_signal(validation_row)
        return

    _ensure_file()
    df = _ensure_columns(pd.read_csv(SIGNAL_CSV_PATH))
    
    symbol = validation_row.get("symbol")
    tf = validation_row.get("validation_timeframe")
    exchange_mode = utils.clean_optional(validation_row.get("exchange_mode")) or config.EXCHANGE_MODE
    data_source_exchange = utils.clean_optional(validation_row.get("data_source_exchange"))
    
    # Check for recent duplicates
    now = datetime.now(timezone.utc)
    if not df.empty:
        # Filter same symbol and TF
        recent = df[
            (df["symbol"] == symbol)
            & (df["timeframe"] == tf)
            & (df["status"] == "OPEN")
            & (df["exchange_mode"].fillna("") == exchange_mode)
            & (df["data_source_exchange"].fillna("") == (data_source_exchange or ""))
        ]
        if not recent.empty:
            last_dt = _to_utc_timestamp(recent["created_at"].max())
            if last_dt is not None and (now - last_dt.to_pydatetime()) < timedelta(hours=24):
                # Update TP/SL if they are missing or to freshen them up
                idx_to_update = recent["created_at"].idxmax()
                df.at[idx_to_update, "estimated_entry"] = validation_row.get("estimated_entry")
                df.at[idx_to_update, "estimated_stop_loss"] = validation_row.get("estimated_stop_loss")
                df.at[idx_to_update, "estimated_take_profit"] = validation_row.get("estimated_take_profit")
                df.at[idx_to_update, "rr_ratio"] = validation_row.get("rr_ratio")
                df.to_csv(SIGNAL_CSV_PATH, index=False)
                return

    created_at = _to_utc_timestamp(validation_row.get("generated_at"))
    created_at_iso = created_at.isoformat() if created_at is not None else now.isoformat()
    
    new_row = {
        "created_at": created_at_iso,
        "symbol": symbol,
        "timeframe": tf,
        "source": "validator",
        "exchange_mode": exchange_mode,
        "market_type": validation_row.get("market_type") or "spot",
        "data_source_exchange": data_source_exchange,
        "initial_decision": validation_row.get("validation_decision"),
        "final_verdict": validation_row.get("final_verdict"),
        "initial_price": validation_row.get("price"),
        "estimated_entry": validation_row.get("estimated_entry"),
        "estimated_stop_loss": validation_row.get("estimated_stop_loss"),
        "estimated_take_profit": validation_row.get("estimated_take_profit"),
        "rr_ratio": validation_row.get("rr_ratio"),
        "status": "OPEN",
        "last_checked_at": created_at_iso,
        "last_price": validation_row.get("price"),
        "move_pct": 0.0,
        "hit_tp": False,
        "hit_sl": False,
        "strategy_profile": validation_row.get("strategy_profile"),
        "notes": validation_row.get("reason")
    }
    
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(SIGNAL_CSV_PATH, index=False)


def _generate_markdown(df: pd.DataFrame):
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    lines = [
        "# Signal Tracking",
        ""
    ]
    
    def add_table(title, subset):
        lines.append(f"## {title}")
        if subset.empty:
            lines.append("Sin señales.\n")
            return
        
        lines.append("| Symbol | TF | Verdict | Initial Price | Last Price | Move % | TP | SL | Status | Created At |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        
        # Sort by created_at desc
        subset = subset.sort_values("created_at", ascending=False)
        
        for _, row in subset.iterrows():
            move = f"{row['move_pct']:.2f}%" if pd.notna(row['move_pct']) else "-"
            tp_val = utils.format_price(row.get('estimated_take_profit'))
            sl_val = utils.format_price(row.get('estimated_stop_loss'))
            
            tp_str = f"{tp_val} ✅" if row.get('hit_tp') else tp_val
            sl_str = f"{sl_val} ❌" if row.get('hit_sl') else sl_val
            
            lines.append(f"| {row['symbol']} | {row['timeframe']} | {row['final_verdict']} | {utils.format_price(row['initial_price'])} | {utils.format_price(row['last_price'])} | {move} | {tp_str} | {sl_str} | {row['status']} | {row['created_at'][:16]} |")
        lines.append("")

    add_table("Señales abiertas", df[df["status"] == "OPEN"])
    add_table("Cerradas por TP", df[df["status"] == "HIT_TP"])
    add_table("Cerradas por SL", df[df["status"] == "HIT_SL"])
    add_table("Expiradas", df[df["status"] == "EXPIRED"])
    
    with open(SIGNAL_MD_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _signal_group_key(row) -> tuple:
    symbol = row["symbol"]
    exchange_mode = _clean_optional(row.get("exchange_mode")) or config.EXCHANGE_MODE
    exchange_id = _clean_optional(row.get("data_source_exchange"))
    market_type = _clean_optional(row.get("market_type")) or "spot"
    return symbol, exchange_id, exchange_mode, market_type


def _evaluate_signal_row(df: pd.DataFrame, idx, row, df_current: pd.DataFrame, now: datetime) -> tuple:
    initial_price = float(row["initial_price"]) if pd.notna(row["initial_price"]) else 0.0
    tp = float(row["estimated_take_profit"]) if pd.notna(row["estimated_take_profit"]) else float('inf')
    sl = float(row["estimated_stop_loss"]) if pd.notna(row["estimated_stop_loss"]) else 0.0

    # filter candles >= created_at
    created_dt = _to_utc_timestamp(row["created_at"])
    if created_dt is None:
        return 0, 0

    recent_candles = df_current[df_current["datetime"] >= created_dt]

    if recent_candles.empty:
        return 0, 0

    current_price = float(recent_candles.iloc[-1]["close"])
    move_pct = ((current_price - initial_price) / initial_price) * 100 if initial_price > 0 else 0

    df.at[idx, "last_price"] = current_price
    df.at[idx, "move_pct"] = move_pct
    df.at[idx, "last_checked_at"] = now.isoformat()

    hit_tp = False
    hit_sl = False

    for _, candle in recent_candles.iterrows():
        high = float(candle["high"])
        low = float(candle["low"])

        if high >= tp and low <= sl:
            hit_sl = True
            df.at[idx, "notes"] = str(df.at[idx, "notes"]) + " | AMBIGUOUS_TP_SL_SAME_CANDLE"
            break
        elif low <= sl:
            hit_sl = True
            break
        elif high >= tp:
            hit_tp = True
            break

    closed_count = 0
    if hit_sl:
        df.at[idx, "hit_sl"] = True
        df.at[idx, "status"] = "HIT_SL"
        closed_count = 1
    elif hit_tp:
        df.at[idx, "hit_tp"] = True
        df.at[idx, "status"] = "HIT_TP"
        closed_count = 1
    elif (now - created_dt.to_pydatetime()).days >= 7:
        df.at[idx, "status"] = "EXPIRED"
        closed_count = 1

    return 1, closed_count


def update_signals():
    sqlite_backend = storage.is_sqlite_backend()
    if sqlite_backend:
        db = storage.get_storage()
        df = load_signals_dataframe()
    else:
        _ensure_file()
        df = _ensure_columns(pd.read_csv(SIGNAL_CSV_PATH))
    
    if df.empty:
        _generate_markdown(df)
        return {"updated": 0, "closed": 0, "ohlcv_requests": 0}
    
    open_mask = df["status"] == "OPEN"
    open_signals = df[open_mask]
    
    updated_count = 0
    closed_count = 0
    ohlcv_requests = 0
    now = datetime.now(timezone.utc)

    grouped_signals = {}
    for idx, row in open_signals.iterrows():
        grouped_signals.setdefault(_signal_group_key(row), []).append((idx, row))

    for (symbol, exchange_id, exchange_mode, market_type), signal_rows in grouped_signals.items():
        try:
            # fetch last 8 days of 15m candles to cover the max expiry of 7 days
            df_current = data_provider.fetch_ohlcv(
                symbol,
                "15m",
                days=8,
                exchange_id=exchange_id,
                exchange_mode=exchange_mode,
                market_type=market_type,
            )
            ohlcv_requests += 1
            if df_current is None or df_current.empty:
                continue

            for idx, row in signal_rows:
                row_updated, row_closed = _evaluate_signal_row(df, idx, row, df_current, now)
                updated_count += row_updated
                closed_count += row_closed
                if row_closed:
                    continue
        except Exception as e:
            print(f"Error updating signals for {symbol} ({exchange_id or 'default'}/{exchange_mode}): {e}")
            
    if sqlite_backend:
        for _, row in df.iterrows():
            signal_id = row.get("id")
            if signal_id is None or pd.isna(signal_id):
                continue
            db.update_tracked_signal(
                int(signal_id),
                {
                    "updated_at": now.isoformat(),
                    "last_checked_at": row.get("last_checked_at"),
                    "last_price": row.get("last_price"),
                    "move_pct": row.get("move_pct"),
                    "hit_tp": row.get("hit_tp"),
                    "hit_sl": row.get("hit_sl"),
                    "status": row.get("status"),
                    "notes": row.get("notes"),
                    "raw": row.to_dict(),
                },
            )
    else:
        df.to_csv(SIGNAL_CSV_PATH, index=False)
    _generate_markdown(df)
    
    return {"updated": updated_count, "closed": closed_count, "ohlcv_requests": ohlcv_requests}
