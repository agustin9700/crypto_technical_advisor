import os
import csv
import pandas as pd
from datetime import datetime, timezone, timedelta

import config
import data_provider
import utils

SIGNAL_CSV_PATH = os.path.join(config.OUTPUT_DIR, "signal_history.csv")
SIGNAL_MD_PATH = os.path.join(config.OUTPUT_DIR, "signal_status.md")

COLUMNS = [
    "created_at", "symbol", "timeframe", "source", "initial_decision", 
    "final_verdict", "initial_price", "estimated_entry", "estimated_stop_loss", 
    "estimated_take_profit", "rr_ratio", "status", "last_checked_at", 
    "last_price", "move_pct", "hit_tp", "hit_sl", "notes"
]

def _ensure_file():
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    if not os.path.exists(SIGNAL_CSV_PATH):
        df = pd.DataFrame(columns=COLUMNS)
        df.to_csv(SIGNAL_CSV_PATH, index=False)

def record_signal(validation_row: dict):
    _ensure_file()
    df = pd.read_csv(SIGNAL_CSV_PATH)
    
    symbol = validation_row.get("symbol")
    tf = validation_row.get("validation_timeframe")
    
    # Check for recent duplicates
    now = datetime.now(timezone.utc)
    if not df.empty:
        # Filter same symbol and TF
        recent = df[(df["symbol"] == symbol) & (df["timeframe"] == tf) & (df["status"] == "OPEN")]
        if not recent.empty:
            last_dt = pd.to_datetime(recent["created_at"].max())
            if (now - last_dt) < timedelta(hours=24):
                # Update TP/SL if they are missing or to freshen them up
                idx_to_update = recent["created_at"].idxmax()
                df.at[idx_to_update, "estimated_entry"] = validation_row.get("estimated_entry")
                df.at[idx_to_update, "estimated_stop_loss"] = validation_row.get("estimated_stop_loss")
                df.at[idx_to_update, "estimated_take_profit"] = validation_row.get("estimated_take_profit")
                df.at[idx_to_update, "rr_ratio"] = validation_row.get("rr_ratio")
                df.to_csv(SIGNAL_CSV_PATH, index=False)
                return
    
    new_row = {
        "created_at": validation_row.get("generated_at"),
        "symbol": symbol,
        "timeframe": tf,
        "source": "validator",
        "initial_decision": validation_row.get("validation_decision"),
        "final_verdict": validation_row.get("final_verdict"),
        "initial_price": validation_row.get("price"),
        "estimated_entry": validation_row.get("estimated_entry"),
        "estimated_stop_loss": validation_row.get("estimated_stop_loss"),
        "estimated_take_profit": validation_row.get("estimated_take_profit"),
        "rr_ratio": validation_row.get("rr_ratio"),
        "status": "OPEN",
        "last_checked_at": validation_row.get("generated_at"),
        "last_price": validation_row.get("price"),
        "move_pct": 0.0,
        "hit_tp": False,
        "hit_sl": False,
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


def update_signals():
    _ensure_file()
    df = pd.read_csv(SIGNAL_CSV_PATH)
    
    if df.empty:
        _generate_markdown(df)
        return {"updated": 0, "closed": 0}
    
    open_mask = df["status"] == "OPEN"
    open_signals = df[open_mask]
    
    updated_count = 0
    closed_count = 0
    now = datetime.now(timezone.utc)
    
    for idx, row in open_signals.iterrows():
        symbol = row["symbol"]
        initial_price = float(row["initial_price"]) if pd.notna(row["initial_price"]) else 0.0
        tp = float(row["estimated_take_profit"]) if pd.notna(row["estimated_take_profit"]) else float('inf')
        sl = float(row["estimated_stop_loss"]) if pd.notna(row["estimated_stop_loss"]) else 0.0
        
        try:
            # fetch last 8 days of 15m candles to cover the max expiry of 7 days
            df_current = data_provider.fetch_ohlcv(symbol, "15m", days=8)
            if df_current is not None and not df_current.empty:
                # filter candles >= created_at
                created_dt = pd.to_datetime(row["created_at"])
                if created_dt.tzinfo is None:
                    created_dt = created_dt.tz_localize("UTC")
                
                recent_candles = df_current[df_current["datetime"] >= created_dt]
                
                if not recent_candles.empty:
                    current_price = float(recent_candles.iloc[-1]["close"])
                    move_pct = ((current_price - initial_price) / initial_price) * 100 if initial_price > 0 else 0
                    
                    df.at[idx, "last_price"] = current_price
                    df.at[idx, "move_pct"] = move_pct
                    df.at[idx, "last_checked_at"] = now.isoformat()
                    updated_count += 1
                    
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
                    
                    if hit_sl:
                        df.at[idx, "hit_sl"] = True
                        df.at[idx, "status"] = "HIT_SL"
                        closed_count += 1
                    elif hit_tp:
                        df.at[idx, "hit_tp"] = True
                        df.at[idx, "status"] = "HIT_TP"
                        closed_count += 1
                    elif (now - created_dt).days >= 7:
                        df.at[idx, "status"] = "EXPIRED"
                        closed_count += 1
        except Exception as e:
            print(f"Error updating signal for {symbol}: {e}")
            
    df.to_csv(SIGNAL_CSV_PATH, index=False)
    _generate_markdown(df)
    
    return {"updated": updated_count, "closed": closed_count}
