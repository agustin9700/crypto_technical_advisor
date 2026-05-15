import pandas as pd
import numpy as np
from datetime import datetime, timezone

def normalize_strategy_profile(df, default="legacy"):
    """Asegura que exista la columna strategy_profile y rellena vacíos."""
    if df is None or df.empty:
        return df
    
    if "strategy_profile" not in df.columns:
        df = df.copy()
        df["strategy_profile"] = default
        return df
        
    df = df.copy()
    df["strategy_profile"] = df["strategy_profile"].fillna(default).replace("", default)
    return df

def calculate_trade_metrics(trades_df):
    """Calcula métricas agregadas para un conjunto de trades."""
    if trades_df is None or trades_df.empty:
        return {
            "total_trades": 0, "open_trades": 0, "closed_trades": 0,
            "winning_trades": 0, "losing_trades": 0, "winrate": 0.0,
            "total_pnl": 0.0, "avg_pnl": 0.0, "best_trade": 0.0, "worst_trade": 0.0,
            "avg_pnl_pct": 0.0, "avg_duration_hours": 0.0, "profit_factor": 0.0, "expectancy": 0.0
        }

    # Asegurar que net_pnl sea numérico
    if "net_pnl" in trades_df.columns:
        pnl_col = "net_pnl"
    elif "pnl" in trades_df.columns:
        pnl_col = "pnl"
    else:
        pnl_col = None

    if pnl_col:
        trades_df[pnl_col] = pd.to_numeric(trades_df[pnl_col], errors="coerce").fillna(0.0)

    closed = trades_df[trades_df["status"].isin(["CLOSED", "EXITED", "hit_tp", "hit_sl"])]
    open_t = trades_df[~trades_df["status"].isin(["CLOSED", "EXITED", "hit_tp", "hit_sl"])]
    
    total = len(trades_df)
    n_closed = len(closed)
    n_open = len(open_t)
    
    if n_closed == 0:
        return {
            "total_trades": total, "open_trades": n_open, "closed_trades": 0,
            "winning_trades": 0, "losing_trades": 0, "winrate": 0.0,
            "total_pnl": 0.0, "avg_pnl": 0.0, "best_trade": 0.0, "worst_trade": 0.0,
            "avg_pnl_pct": 0.0, "avg_duration_hours": 0.0, "profit_factor": 0.0, "expectancy": 0.0
        }

    pnl_series = closed[pnl_col]
    wins = closed[pnl_series > 0]
    losses = closed[pnl_series <= 0]
    
    n_wins = len(wins)
    n_losses = len(losses)
    winrate = (n_wins / n_closed) * 100
    
    total_pnl = pnl_series.sum()
    avg_pnl = pnl_series.mean()
    best = pnl_series.max()
    worst = pnl_series.min()
    
    # Profit Factor
    gross_profits = wins[pnl_col].sum()
    gross_losses = abs(losses[pnl_col].sum())
    profit_factor = gross_profits / gross_losses if gross_losses > 0 else (float('inf') if gross_profits > 0 else 0.0)
    
    # Expectancy
    avg_win = wins[pnl_col].mean() if n_wins > 0 else 0.0
    avg_loss = abs(losses[pnl_col].mean()) if n_losses > 0 else 0.0
    # E = (Probability of Win * Avg Win) - (Probability of Loss * Avg Loss)
    expectancy = ((n_wins / n_closed) * avg_win) - ((n_losses / n_closed) * avg_loss)
    
    # Duration
    duration_hrs = 0.0
    if "opened_at" in closed.columns and "closed_at" in closed.columns:
        try:
            opened = pd.to_datetime(closed["opened_at"], utc=True, errors="coerce")
            closed_at = pd.to_datetime(closed["closed_at"], utc=True, errors="coerce")
            durations = (closed_at - opened).dt.total_seconds() / 3600
            duration_hrs = durations.mean() if not durations.isna().all() else 0.0
        except Exception:
            duration_hrs = 0.0

    return {
        "total_trades": total,
        "open_trades": n_open,
        "closed_trades": n_closed,
        "winning_trades": n_wins,
        "losing_trades": n_losses,
        "winrate": round(winrate, 2),
        "total_pnl": round(total_pnl, 4),
        "avg_pnl": round(avg_pnl, 4),
        "best_trade": round(best, 4),
        "worst_trade": round(worst, 4),
        "avg_pnl_pct": 0.0, # Requiere price_entry y price_exit o pnl_pc
        "avg_duration_hours": round(duration_hrs, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float('inf') else "∞",
        "expectancy": round(expectancy, 4)
    }

def calculate_signal_metrics(signals_df):
    """Calcula métricas de calidad de señales."""
    if signals_df is None or signals_df.empty:
        return {
            "total_signals": 0, "avg_score": 0.0, "max_score": 0.0, "min_score": 0.0,
            "signals_by_decision": {}, "signals_by_market_type": {}, "signals_by_timeframe": {}
        }
    
    # Asegurar score numérico
    signals_df["score"] = pd.to_numeric(signals_df.get("score", 0), errors="coerce").fillna(0.0)
    
    metrics = {
        "total_signals": len(signals_df),
        "avg_score": round(signals_df["score"].mean(), 2),
        "max_score": signals_df["score"].max(),
        "min_score": signals_df["score"].min(),
        "signals_by_decision": signals_df["decision"].value_counts().to_dict() if "decision" in signals_df.columns else {},
        "signals_by_market_type": signals_df["market_type"].value_counts().to_dict() if "market_type" in signals_df.columns else {},
        "signals_by_timeframe": signals_df["timeframe"].value_counts().to_dict() if "timeframe" in signals_df.columns else {},
    }
    return metrics

def calculate_strategy_comparison(signals_df, trades_df):
    """Genera un DataFrame comparativo consolidado por perfil."""
    signals_df = normalize_strategy_profile(signals_df)
    trades_df = normalize_strategy_profile(trades_df)
    
    profiles = set()
    if signals_df is not None and not signals_df.empty:
        profiles.update(signals_df["strategy_profile"].unique())
    if trades_df is not None and not trades_df.empty:
        profiles.update(trades_df["strategy_profile"].unique())
    
    if not profiles:
        profiles = ["legacy"]
        
    comparison_data = []
    for profile in sorted(list(profiles)):
        s_sub = signals_df[signals_df["strategy_profile"] == profile] if signals_df is not None and not signals_df.empty else pd.DataFrame()
        t_sub = trades_df[trades_df["strategy_profile"] == profile] if trades_df is not None and not trades_df.empty else pd.DataFrame()
        
        s_metrics = calculate_signal_metrics(s_sub)
        t_metrics = calculate_trade_metrics(t_sub)
        
        row = {
            "strategy_profile": profile,
            "total_signals": s_metrics["total_signals"],
            "avg_score": s_metrics["avg_score"],
            "total_trades": t_metrics["total_trades"],
            "closed_trades": t_metrics["closed_trades"],
            "winrate": t_metrics["winrate"],
            "total_pnl": t_metrics["total_pnl"],
            "avg_pnl": t_metrics["avg_pnl"],
            "best_trade": t_metrics["best_trade"],
            "worst_trade": t_metrics["worst_trade"],
            "profit_factor": t_metrics["profit_factor"],
            "expectancy": t_metrics["expectancy"],
            "avg_duration_hours": t_metrics["avg_duration_hours"]
        }
        comparison_data.append(row)
        
    return pd.DataFrame(comparison_data)

def calculate_equity_curve(trades_df):
    """Genera datos de curva de equidad a partir de trades cerrados."""
    trades_df = normalize_strategy_profile(trades_df)
    if trades_df is None or trades_df.empty:
        return pd.DataFrame(columns=["timestamp", "equity", "strategy_profile"])
    
    # Solo trades con PnL
    pnl_col = "net_pnl" if "net_pnl" in trades_df.columns else ("pnl" if "pnl" in trades_df.columns else None)
    if not pnl_col:
        return pd.DataFrame(columns=["timestamp", "equity", "strategy_profile"])
    
    # Solo cerrados
    closed = trades_df[trades_df["status"].isin(["CLOSED", "EXITED", "hit_tp", "hit_sl"])].copy()
    if closed.empty:
        return pd.DataFrame(columns=["timestamp", "equity", "strategy_profile"])
    
    closed["closed_at_dt"] = pd.to_datetime(closed["closed_at"], utc=True, errors="coerce")
    closed = closed.dropna(subset=["closed_at_dt"]).sort_values("closed_at_dt")
    
    result_dfs = []
    for profile in closed["strategy_profile"].unique():
        p_sub = closed[closed["strategy_profile"] == profile].copy()
        p_sub["equity"] = p_sub[pnl_col].cumsum()
        p_sub = p_sub.rename(columns={"closed_at_dt": "timestamp"})
        result_dfs.append(p_sub[["timestamp", "equity", "strategy_profile"]])
        
    if not result_dfs:
        return pd.DataFrame(columns=["timestamp", "equity", "strategy_profile"])
        
    return pd.concat(result_dfs).sort_values("timestamp")

def calculate_profile_summary(signals_df, trades_df):
    """Cálculos resumidos para cards de alto nivel."""
    comp_df = calculate_strategy_comparison(signals_df, trades_df)
    if comp_df.empty:
        return {}
    
    # Convertir ∞ a un número muy grande para comparaciones
    def clean_pf(pf):
        if pf == "∞": return float('inf')
        return float(pf)

    best_pnl_row = comp_df.loc[comp_df["total_pnl"].idxmax()] if not comp_df.empty else None
    best_wr_row = comp_df.loc[comp_df["winrate"].idxmax()] if not comp_df.empty else None
    
    pf_values = comp_df["profit_factor"].apply(clean_pf)
    best_pf_row = comp_df.loc[pf_values.idxmax()] if not comp_df.empty and not pf_values.isna().all() else None
    
    best_score_row = comp_df.loc[comp_df["avg_score"].idxmax()] if not comp_df.empty else None
    most_signals_row = comp_df.loc[comp_df["total_signals"].idxmax()] if not comp_df.empty else None

    return {
        "best_pnl_profile": best_pnl_row["strategy_profile"] if best_pnl_row is not None else "N/A",
        "best_pnl_value": best_pnl_row["total_pnl"] if best_pnl_row is not None else 0.0,
        
        "best_winrate_profile": best_wr_row["strategy_profile"] if best_wr_row is not None else "N/A",
        "best_winrate_value": best_wr_row["winrate"] if best_wr_row is not None else 0.0,
        
        "best_profit_factor_profile": best_pf_row["strategy_profile"] if best_pf_row is not None else "N/A",
        "best_profit_factor_value": best_pf_row["profit_factor"] if best_pf_row is not None else 0.0,
        
        "most_signals_profile": most_signals_row["strategy_profile"] if most_signals_row is not None else "N/A",
        "most_signals_count": most_signals_row["total_signals"] if most_signals_row is not None else 0,
        
        "best_score_profile": best_score_row["strategy_profile"] if best_score_row is not None else "N/A",
        "best_score_value": best_score_row["avg_score"] if best_score_row is not None else 0.0,
        
        "total_profiles": len(comp_df["strategy_profile"].unique()) if not comp_df.empty else 0
    }
