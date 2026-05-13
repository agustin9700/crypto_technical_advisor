import os
import time
import pandas as pd
from datetime import datetime, timezone

import config
import scanner
import validator
import signal_tracker
import utils

def run_cycle(scan_limit: int = 20, top_n: int = 3, workers: int = 5):
    start_time = time.time()
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    
    # 1. Scanner
    scan_start = time.time()
    scan_result = scanner.run_market_scan(
        limit=scan_limit, 
        mode="fast", 
        backtest_top=0, 
        workers=workers
    )
    scan_end = time.time()
    scan_time = scan_end - scan_start
    
    scan_counts = scan_result.get("decision_counts", {})
    
    # 2. Validation
    val_start = time.time()
    val_result = validator.run_validation(top_n=top_n)
    val_end = time.time()
    val_time = val_end - val_start
    
    confirmed = 0
    watchlist = 0
    rejected = 0
    if val_result and "results" in val_result:
        for r in val_result["results"]:
            fv = r.get("final_verdict")
            if fv == "CONFIRMED":
                confirmed += 1
            elif fv == "WATCHLIST":
                watchlist += 1
            else:
                rejected += 1
    
    # 3. Signals Update
    sig_start = time.time()
    
    # Read history before to find newly closed
    sig_csv = os.path.join(config.OUTPUT_DIR, "signal_history.csv")
    df_sig_before = pd.DataFrame()
    if os.path.exists(sig_csv):
        df_sig_before = pd.read_csv(sig_csv)
    
    sig_result = signal_tracker.update_signals()
    sig_end = time.time()
    sig_time = sig_end - sig_start
    
    # Read history after to find OPEN and NEWLY CLOSED
    df_sig_after = pd.DataFrame()
    if os.path.exists(sig_csv):
        df_sig_after = pd.read_csv(sig_csv)
        
    df_open = pd.DataFrame()
    df_newly_closed = pd.DataFrame()
    
    if not df_sig_after.empty:
        df_open = df_sig_after[df_sig_after["status"] == "OPEN"]
        
        # Determine newly closed
        if not df_sig_before.empty:
            # Those that were OPEN before but not OPEN now, and status in HIT_TP/HIT_SL
            merged = df_sig_after.merge(df_sig_before[['symbol', 'timeframe', 'created_at', 'status']], 
                                        on=['symbol', 'timeframe', 'created_at'], 
                                        suffixes=('', '_before'))
            df_newly_closed = merged[
                (merged['status_before'] == 'OPEN') & 
                (merged['status'].isin(['HIT_TP', 'HIT_SL']))
            ]
        else:
            # If no before, none are newly closed (or all closed are new)
            df_newly_closed = df_sig_after[df_sig_after["status"].isin(["HIT_TP", "HIT_SL"])]
            
    total_time = time.time() - start_time
    
    # Generate CSV
    row = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scan_limit": scan_limit,
        "top_n": top_n,
        "workers": workers,
        "total_time_sec": total_time,
        "scan_time_sec": scan_time,
        "scan_enter_now": scan_counts.get("ENTER_NOW_CANDIDATE", 0),
        "scan_wait": scan_counts.get("WAIT", 0),
        "scan_avoid": scan_counts.get("AVOID", 0),
        "val_confirmed": confirmed,
        "val_watchlist": watchlist,
        "val_rejected": rejected,
        "signals_updated": sig_result.get("updated", 0),
        "signals_closed_new": len(df_newly_closed)
    }
    
    csv_path = os.path.join(config.OUTPUT_DIR, "latest_cycle_summary.csv")
    pd.DataFrame([row]).to_csv(csv_path, index=False)
    
    # Generate Markdown
    md_path = os.path.join(config.OUTPUT_DIR, "latest_cycle_summary.md")
    
    lines = [
        "# Crypto Technical Advisor — Cycle Summary",
        "",
        "## Resumen",
        f"- Fecha/hora: {now_str}",
        f"- Scanner limit: {scan_limit}",
        f"- Top validado: {top_n}",
        f"- Workers: {workers}",
        f"- Tiempo total: {total_time:.2f} segundos",
        "",
        "## Scanner",
        f"- ENTER_NOW_CANDIDATE: {scan_counts.get('ENTER_NOW_CANDIDATE', 0)}",
        f"- WAIT: {scan_counts.get('WAIT', 0)}",
        f"- AVOID: {scan_counts.get('AVOID', 0)}",
        f"- Tiempo scanner: {scan_time:.2f} segundos",
        "",
        "## Validación",
        f"- Confirmados: {confirmed}",
        f"- Watchlist: {watchlist}",
        f"- Rechazados: {rejected}",
        ""
    ]
    
    def render_sig_table(title, df_subset):
        lines.append(f"## {title}")
        if df_subset.empty:
            lines.append("Sin señales.\n")
            return
        
        lines.append("| Symbol | TF | Verdict | Initial Price | Last Price | Move % | TP | SL | Status |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        
        subset = df_subset.sort_values("created_at", ascending=False)
        for _, r in subset.iterrows():
            move = f"{r['move_pct']:.2f}%" if pd.notna(r.get('move_pct')) else "-"
            tp_val = utils.format_price(r.get('estimated_take_profit'))
            sl_val = utils.format_price(r.get('estimated_stop_loss'))
            
            tp_str = f"{tp_val} ✅" if r.get('hit_tp') else tp_val
            sl_str = f"{sl_val} ❌" if r.get('hit_sl') else sl_val
            
            lines.append(f"| {r['symbol']} | {r['timeframe']} | {r['final_verdict']} | {utils.format_price(r['initial_price'])} | {utils.format_price(r['last_price'])} | {move} | {tp_str} | {sl_str} | {r['status']} |")
        lines.append("")

    render_sig_table("Señales abiertas", df_open)
    render_sig_table("Señales cerradas nuevas", df_newly_closed)
    
    lines += [
        "## Archivos generados",
        "- outputs/latest_scan.md",
        "- outputs/latest_validation.md",
        "- outputs/signal_status.md"
    ]
    
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        
    return {
        "scan_time": scan_time,
        "val_time": val_time,
        "sig_time": sig_time,
        "total_time": total_time,
        "md_path": md_path,
        "signals_updated": sig_result.get("updated", 0)
    }
