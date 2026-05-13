import csv
import os
import pandas as pd
from datetime import datetime, timezone

import config
import technical_analyzer
import backtester
import signal_tracker
import utils

def _generate_markdown(df_validations: pd.DataFrame, output_path: str):
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    if df_validations.empty:
        md = f"# Crypto Technical Advisor — Top Validation\n\n## Resumen\n- Fecha/hora: {now_str}\n- Sin candidatos validados\n\n## Notas\nPaper/analysis only. No financial advice.\n"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md)
        return
    
    total = len(df_validations)
    confirmed = df_validations[df_validations["final_verdict"] == "CONFIRMED"]
    watchlist = df_validations[df_validations["final_verdict"] == "WATCHLIST"]
    rejected = df_validations[df_validations["final_verdict"] == "REJECTED"]
    no_clear = df_validations[df_validations["final_verdict"] == "NO_CLEAR_SETUP"]
    
    lines = [
        "# Crypto Technical Advisor — Top Validation",
        "",
        "## Resumen",
        f"- Fecha/hora: {now_str}",
        f"- Candidatos validados: {total}",
        f"- Confirmados: {len(confirmed)}",
        f"- Watchlist: {len(watchlist)}",
        f"- Rechazados / No Clear: {len(rejected) + len(no_clear)}",
        ""
    ]
    
    def add_table(title, df_subset):
        lines.append(f"## {title}")
        if df_subset.empty:
            lines.append("Sin resultados.\n")
            return
        
        lines.append("| Rank | Symbol | TF | Decision | Score | Price | BT | Reason |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for _, row in df_subset.iterrows():
            lines.append(f"| {row['rank']} | {row['symbol']} | {row['validation_timeframe']} | {row['validation_decision']} | {row['validation_score']} | {utils.format_price(row['price'])} | {row['backtest_verdict']} | {row['reason']} |")
        lines.append("")

    add_table("Confirmados", confirmed)
    add_table("Watchlist", watchlist)
    add_table("Rechazados", pd.concat([rejected, no_clear]).sort_values("rank"))
    
    lines += [
        "## Notas",
        "Paper/analysis only. No financial advice."
    ]
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _clean_optional(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    return text


def run_validation(top_n: int = 5, exchange_id=None, exchange_mode: str = "manual"):
    scan_csv = os.path.join(config.OUTPUT_DIR, "latest_scan.csv")
    if not os.path.exists(scan_csv):
        print(f"File not found: {scan_csv}")
        return None
    
    try:
        df_scan = pd.read_csv(scan_csv)
    except Exception as e:
        print(f"Failed to read scan csv: {e}")
        return None
    
    if "rank" not in df_scan.columns:
        print("No rank column in scan results.")
        return None
    
    df_scan = df_scan.sort_values("rank").head(top_n)
    
    results = []
    
    for _, row in df_scan.iterrows():
        symbol = row.get("symbol")
        rank = row.get("rank")
        scanner_decision = row.get("decision")
        scanner_timeframe = _clean_optional(row.get("recommended_timeframe"))
        scanner_score = row.get("score")
        row_exchange = _clean_optional(row.get("data_source_exchange"))
        row_exchange_mode = _clean_optional(row.get("exchange_mode"))
        if exchange_id:
            analysis_exchange = exchange_id
            analysis_exchange_mode = exchange_mode
        elif row_exchange:
            analysis_exchange = row_exchange
            analysis_exchange_mode = "manual"
        else:
            analysis_exchange = None
            analysis_exchange_mode = row_exchange_mode or exchange_mode
        
        bt_result = None
        if scanner_timeframe:
            print(f"Validating #{rank} {symbol} {scanner_timeframe}...")
            analysis = technical_analyzer.analyze_symbol_auto(
                symbol,
                timeframes=[scanner_timeframe],
                exchange_id=analysis_exchange,
                exchange_mode=analysis_exchange_mode,
            )
        else:
            print(f"Validating #{rank} {symbol}: no scanner timeframe")
            analysis = {
                "symbol": symbol,
                "decision": scanner_decision,
                "recommended_timeframe": None,
                "no_clear_setup": True,
                "exchange_mode": analysis_exchange_mode,
                "data_source_exchange": analysis_exchange,
                "fallback_used": False,
            }

        tf = analysis.get("recommended_timeframe") or scanner_timeframe
        if tf and not analysis.get("no_clear_setup"):
            bt_result = backtester.run_quick_backtest(symbol, tf)
            analysis = technical_analyzer.apply_backtest_to_analysis(analysis, bt_result)
            
        best = analysis.get("best_setup") or analysis
        
        val_decision = analysis.get("decision")
        val_score = best.get("score", 0)
        bt_verdict = (bt_result or {}).get("verdict", "NO_DATA")
        rr = best.get("rr_ratio", 0)
        
        final_verdict = ""
        reason = ""
        
        if not tf or analysis.get("no_clear_setup"):
            final_verdict = "NO_CLEAR_SETUP"
            reason = "No timeframe recommended"
        elif bt_verdict in ["BACKTEST_BAD", "NOT_ENOUGH_TRADES"]:
            final_verdict = "REJECTED"
            reason = f"Backtest verdict is {bt_verdict}"
        elif val_decision == "ENTER_NOW_CANDIDATE" and bt_verdict not in ["BACKTEST_BAD", "BACKTEST_WEAK", "NOT_ENOUGH_TRADES"] and rr >= 1.5:
            final_verdict = "CONFIRMED"
            reason = "Setup confirmed by backtest"
        elif val_score >= 7 and bt_verdict == "BACKTEST_WEAK":
            final_verdict = "WATCHLIST"
            reason = "High score but backtest is WEAK"
        elif val_decision == "WAIT" and val_score >= 6:
            final_verdict = "WATCHLIST"
            reason = "Wait with good structure"
        elif val_score < 6:
            final_verdict = "REJECTED"
            reason = f"Score too low ({val_score})"
        else:
            final_verdict = "REJECTED"
            reason = "Did not meet watchlist or confirmed criteria"
            
        res_row = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "rank": rank,
            "symbol": symbol,
            "scanner_decision": scanner_decision,
            "scanner_timeframe": scanner_timeframe,
            "scanner_score": scanner_score,
            "exchange_mode": analysis.get("exchange_mode") or analysis_exchange_mode,
            "data_source_exchange": analysis.get("data_source_exchange") or analysis_exchange,
            "fallback_used": analysis.get("fallback_used", False),
            "validation_decision": val_decision,
            "validation_timeframe": tf,
            "validation_score": val_score,
            "validation_status": analysis.get("action_summary") or best.get("action_summary"),
            "price": best.get("price"),
            "rsi": best.get("rsi"),
            "vol_ratio": best.get("closed_candle_vol_ratio"),
            "entry_trigger": analysis.get("entry_trigger") or best.get("entry_trigger"),
            "estimated_entry": best.get("estimated_entry"),
            "estimated_stop_loss": best.get("estimated_stop_loss"),
            "estimated_take_profit": best.get("estimated_take_profit"),
            "rr_ratio": rr,
            "backtest_verdict": bt_verdict,
            "backtest_profit_factor": (bt_result or {}).get("profit_factor"),
            "backtest_total_return_pct": (bt_result or {}).get("total_return_pct"),
            "backtest_max_drawdown_pct": (bt_result or {}).get("max_drawdown_pct"),
            "final_verdict": final_verdict,
            "reason": reason
        }
        results.append(res_row)
        
        if final_verdict in ["CONFIRMED", "WATCHLIST"]:
            signal_tracker.record_signal(res_row)

    df_res = pd.DataFrame(results)
    
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    csv_path = os.path.join(config.OUTPUT_DIR, "latest_validation.csv")
    md_path = os.path.join(config.OUTPUT_DIR, "latest_validation.md")
    
    if not df_res.empty:
        df_res.to_csv(csv_path, index=False)
        _generate_markdown(df_res, md_path)
    
    return {
        "csv_path": csv_path,
        "md_path": md_path,
        "results": results
    }
