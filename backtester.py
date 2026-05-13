import pandas as pd
import numpy as np

import config
import data_provider
import indicators
import support_resistance as sr_module


def _signal_at_bar(row: pd.Series, prev_row: pd.Series) -> bool:
    """Return True if entry conditions are met at this bar (no lookahead)."""
    price = row["close"]
    rsi_val = row["rsi"]
    ema200_val = row["ema200"]
    ema20_val = row["ema20"]
    ema50_val = row["ema50"]
    macd_val = row["macd"]
    macd_sig = row["macd_signal"]
    vol_ratio = row["vol_ratio"]

    # Score tally (simplified version of analyzer score for backtest)
    score = 0

    if price > ema200_val:
        score += 2
    if ema20_val > ema50_val:
        score += 1
    if price > ema50_val:
        score += 1
    if 50 <= rsi_val <= 70:
        score += 2
    elif 45 <= rsi_val < 50 and prev_row is not None and rsi_val > prev_row["rsi"]:
        score += 1
    if macd_val > macd_sig:
        score += 1
    if pd.notna(vol_ratio) and vol_ratio >= 1.2:
        score += 1

    # Penalties
    if pd.notna(vol_ratio) and vol_ratio < 0.8:
        score -= 1
    if rsi_val < 40:
        score -= 2
    if price < ema200_val and rsi_val < 50:
        score -= 2

    score = max(0, min(score, 10))

    # Regime filter
    regime_ok = price > ema200_val and rsi_val >= 50

    return score >= 7 and regime_ok


def run_quick_backtest(symbol: str, timeframe: str, days: int = None) -> dict:
    if days is None:
        days = config.BACKTEST_DAYS_DEFAULT

    symbol = data_provider.normalize_symbol(symbol)

    try:
        df_raw = data_provider.fetch_ohlcv(symbol, timeframe, days=days + 60)
    except Exception as e:
        return {"symbol": symbol, "timeframe": timeframe, "days": days,
                "error": str(e), "verdict": "NO_DATA"}

    if df_raw is None or len(df_raw) < 220:
        return {"symbol": symbol, "timeframe": timeframe, "days": days,
                "error": "Not enough data", "verdict": "NO_DATA"}

    df = indicators.add_indicators(df_raw)
    df = df.dropna(subset=["ema200", "rsi", "atr"]).reset_index(drop=True)

    capital = config.INITIAL_CAPITAL
    peak_capital = capital
    max_drawdown = 0.0
    trades = []

    in_trade = False
    entry_price = 0.0
    sl_price = 0.0
    tp_price = 0.0

    for i in range(1, len(df) - 1):
        if in_trade:
            bar = df.iloc[i]
            h = bar["high"]
            l = bar["low"]

            hit_sl = l <= sl_price
            hit_tp = h >= tp_price

            if hit_sl or hit_tp:
                # Conservative: if both, assume SL hit first
                if hit_sl:
                    exit_price = sl_price
                else:
                    exit_price = tp_price

                exit_price_adj = exit_price * (1 - config.SLIPPAGE_PCT)
                fee = exit_price_adj * config.FEE_PCT
                trade_return_pct = (exit_price_adj - entry_price) / entry_price * 100 - (config.FEE_PCT * 2 * 100)

                capital *= (1 + trade_return_pct / 100)
                peak_capital = max(peak_capital, capital)
                dd = (peak_capital - capital) / peak_capital * 100
                max_drawdown = max(max_drawdown, dd)

                trades.append({
                    "entry": entry_price,
                    "exit": exit_price_adj,
                    "return_pct": trade_return_pct,
                    "win": trade_return_pct > 0,
                })
                in_trade = False

        else:
            # Check signal on closed candle i-1, enter at open of candle i+1
            prev = df.iloc[i - 2] if i >= 2 else df.iloc[i - 1]
            sig_bar = df.iloc[i - 1]
            if _signal_at_bar(sig_bar, prev):
                next_bar = df.iloc[i]
                entry_price = next_bar["open"] * (1 + config.SLIPPAGE_PCT)
                atr_val = sig_bar["atr"]
                sl_price = entry_price - config.ATR_SL_MULT * atr_val
                tp_price = entry_price + config.ATR_TP_MULT * atr_val

                if sl_price <= 0 or entry_price <= 0:
                    continue

                in_trade = True

    # Metrics
    n_trades = len(trades)

    if n_trades == 0:
        return {
            "symbol": symbol, "timeframe": timeframe, "days": days,
            "n_trades": 0, "wins": 0, "losses": 0, "win_rate": 0,
            "profit_factor": 0, "total_return_pct": 0, "max_drawdown_pct": 0,
            "avg_trade_pct": 0, "best_trade_pct": 0, "worst_trade_pct": 0,
            "final_capital": capital, "verdict": "NOT_ENOUGH_TRADES",
        }

    wins = sum(1 for t in trades if t["win"])
    losses = n_trades - wins
    win_rate = wins / n_trades * 100

    gross_profit = sum(t["return_pct"] for t in trades if t["return_pct"] > 0)
    gross_loss = abs(sum(t["return_pct"] for t in trades if t["return_pct"] <= 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (1.5 if gross_profit > 0 else 0)

    total_return_pct = (capital - config.INITIAL_CAPITAL) / config.INITIAL_CAPITAL * 100
    returns = [t["return_pct"] for t in trades]
    avg_trade_pct = np.mean(returns)
    best_trade_pct = max(returns)
    worst_trade_pct = min(returns)

    # Verdict
    if n_trades < 10:
        verdict = "NOT_ENOUGH_TRADES"
    elif profit_factor >= 1.15 and total_return_pct > 0 and max_drawdown <= 20 and n_trades >= 20:
        verdict = "BACKTEST_OK"
    elif profit_factor >= 1.0:
        verdict = "BACKTEST_WEAK"
    else:
        verdict = "BACKTEST_BAD"

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "days": days,
        "n_trades": n_trades,
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 1),
        "profit_factor": round(profit_factor, 3),
        "total_return_pct": round(total_return_pct, 2),
        "max_drawdown_pct": round(max_drawdown, 2),
        "avg_trade_pct": round(avg_trade_pct, 3),
        "best_trade_pct": round(best_trade_pct, 3),
        "worst_trade_pct": round(worst_trade_pct, 3),
        "final_capital": round(capital, 2),
        "verdict": verdict,
    }
