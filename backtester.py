import pandas as pd
import numpy as np

import config
import data_provider
import indicators
import strategy_engine


PESSIMISTIC_INTRABAR = True


def _entry_side(signal: dict, mode: str) -> str | None:
    decision = signal.get("decision")
    mode = (mode or "spot").lower()
    if mode == "futures" and decision in ("LONG", "SHORT"):
        return decision
    if decision in ("ENTER_NOW_CANDIDATE", "LONG"):
        return "LONG"
    return None


def run_quick_backtest(
    symbol: str,
    timeframe: str,
    days: int = None,
    exchange_id=None,
    exchange_mode: str = None,
    market_type: str = "spot",
    mode: str = "spot",
) -> dict:
    if days is None:
        days = config.BACKTEST_DAYS_DEFAULT

    symbol = data_provider.normalize_symbol(symbol)
    market_type = data_provider.normalize_market_type(market_type)
    mode = (mode or market_type or "spot").strip().lower()
    exchange_mode = exchange_mode or config.EXCHANGE_MODE

    try:
        df_raw = data_provider.fetch_ohlcv(
            symbol,
            timeframe,
            days=days + 60,
            exchange_id=exchange_id,
            exchange_mode=exchange_mode,
            market_type=market_type,
        )
    except Exception as e:
        return {"symbol": symbol, "timeframe": timeframe, "days": days,
                "exchange": exchange_id, "exchange_mode": exchange_mode,
                "market_type": market_type, "mode": mode,
                "error": str(e), "verdict": "NO_DATA"}

    if df_raw is None or len(df_raw) < 220:
        return {"symbol": symbol, "timeframe": timeframe, "days": days,
                "exchange": exchange_id, "exchange_mode": exchange_mode,
                "market_type": market_type, "mode": mode,
                "error": "Not enough data", "verdict": "NO_DATA"}

    df = indicators.add_indicators(df_raw)
    df = df.dropna(subset=["ema200", "rsi", "atr"]).reset_index(drop=True)
    source_exchange = (getattr(df_raw, "attrs", {}) or {}).get("data_source_exchange") or exchange_id
    source_market_type = (getattr(df_raw, "attrs", {}) or {}).get("market_type") or market_type

    capital = config.INITIAL_CAPITAL
    peak_capital = capital
    max_drawdown = 0.0
    trades = []
    gap_losses = 0

    in_trade = False
    entry_price = 0.0
    sl_price = 0.0
    tp_price = 0.0
    risk_amount = 0.0
    units = 0.0
    side = "LONG"

    for i in range(1, len(df) - 1):
        if in_trade:
            bar = df.iloc[i]
            h = bar["high"]
            l = bar["low"]

            if side == "SHORT":
                hit_sl = h >= sl_price
                hit_tp = l <= tp_price
            else:
                hit_sl = l <= sl_price
                hit_tp = h >= tp_price

            if hit_sl or hit_tp:
                if hit_sl and hit_tp:
                    exit_price = sl_price if PESSIMISTIC_INTRABAR else tp_price
                elif hit_sl:
                    exit_price = sl_price
                else:
                    exit_price = tp_price

                exit_price_adj = (
                    exit_price * (1 + config.SLIPPAGE_PCT)
                    if side == "SHORT"
                    else exit_price * (1 - config.SLIPPAGE_PCT)
                )
                gross_pnl = (
                    units * (entry_price - exit_price_adj)
                    if side == "SHORT"
                    else units * (exit_price_adj - entry_price)
                )
                fee_cost = (
                    units * entry_price * config.FEE_PCT
                    + units * exit_price_adj * config.FEE_PCT
                )
                net_pnl = gross_pnl - fee_cost
                trade_return_pct = net_pnl / risk_amount * 100 if risk_amount > 0 else 0.0
                r_multiple = net_pnl / risk_amount if risk_amount > 0 else 0.0

                capital += net_pnl
                peak_capital = max(peak_capital, capital)
                dd = (peak_capital - capital) / peak_capital * 100
                max_drawdown = max(max_drawdown, dd)

                trades.append({
                    "entry": entry_price,
                    "exit": exit_price_adj,
                    "side": side,
                    "return_pct": trade_return_pct,
                    "net_pnl": net_pnl,
                    "risk_amount": risk_amount,
                    "r_multiple": r_multiple,
                    "win": trade_return_pct > 0,
                })
                in_trade = False

        else:
            # Check signal on closed candle i-1, enter at open of candle i+1
            history = df.iloc[max(0, i - 260):i].copy()
            signal = strategy_engine.evaluate_signal(
                history,
                symbol=symbol,
                mode=mode,
                timeframe=timeframe,
                exchange_id=source_exchange,
                market_type=source_market_type,
            )
            side = _entry_side(signal, mode)
            if side:
                next_bar = df.iloc[i]
                entry_price = (
                    next_bar["open"] * (1 - config.SLIPPAGE_PCT)
                    if side == "SHORT"
                    else next_bar["open"] * (1 + config.SLIPPAGE_PCT)
                )
                sl_price = signal.get("stop_loss")
                tp_price = signal.get("take_profit")
                if not sl_price or not tp_price:
                    atr_val = history.iloc[-1]["atr"]
                    if side == "SHORT":
                        _, sl_price, tp_price, *_ = strategy_engine.compute_short_rr(entry_price, atr_val)
                    else:
                        _, sl_price, tp_price, *_ = strategy_engine.compute_long_rr(entry_price, atr_val)

                if sl_price <= 0 or entry_price <= 0:
                    continue

                risk_amount = capital * config.RISK_PER_TRADE_PCT
                stop_distance = max(abs(entry_price - sl_price), 1e-8)
                units = risk_amount / stop_distance

                gap_loss = next_bar["open"] >= sl_price if side == "SHORT" else next_bar["open"] <= sl_price
                if gap_loss:
                    exit_price_adj = (
                        next_bar["open"] * (1 + config.SLIPPAGE_PCT)
                        if side == "SHORT"
                        else next_bar["open"] * (1 - config.SLIPPAGE_PCT)
                    )
                    gross_pnl = (
                        units * (entry_price - exit_price_adj)
                        if side == "SHORT"
                        else units * (exit_price_adj - entry_price)
                    )
                    fee_cost = (
                        units * entry_price * config.FEE_PCT
                        + units * exit_price_adj * config.FEE_PCT
                    )
                    net_pnl = gross_pnl - fee_cost
                    trade_return_pct = net_pnl / risk_amount * 100 if risk_amount > 0 else 0.0
                    r_multiple = net_pnl / risk_amount if risk_amount > 0 else 0.0

                    capital += net_pnl
                    peak_capital = max(peak_capital, capital)
                    dd = (peak_capital - capital) / peak_capital * 100
                    max_drawdown = max(max_drawdown, dd)
                    gap_losses += 1

                    trades.append({
                        "entry": entry_price,
                        "exit": exit_price_adj,
                        "side": side,
                        "return_pct": trade_return_pct,
                        "net_pnl": net_pnl,
                        "risk_amount": risk_amount,
                        "r_multiple": r_multiple,
                        "win": trade_return_pct > 0,
                        "gap_loss": True,
                    })
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
            "exchange": source_exchange,
            "exchange_mode": exchange_mode,
            "market_type": source_market_type,
            "mode": mode,
            "strategy_engine": "strategy_engine.evaluate_signal",
            "risk_per_trade_pct": config.RISK_PER_TRADE_PCT,
            "avg_r_multiple": 0,
            "expectancy_r": 0,
            "gap_losses": gap_losses,
            "sharpe_ratio": None,
            "calmar_ratio": None,
            "consecutive_losses_max": 0,
        }

    wins = sum(1 for t in trades if t["win"])
    losses = n_trades - wins
    win_rate = wins / n_trades * 100

    gross_profit = sum(t["net_pnl"] for t in trades if t["net_pnl"] > 0)
    gross_loss = abs(sum(t["net_pnl"] for t in trades if t["net_pnl"] <= 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (1.5 if gross_profit > 0 else 0)

    total_return_pct = (capital - config.INITIAL_CAPITAL) / config.INITIAL_CAPITAL * 100
    returns = [t["return_pct"] for t in trades]
    r_multiples = [t["r_multiple"] for t in trades]
    avg_trade_pct = np.mean(returns)
    best_trade_pct = max(returns)
    worst_trade_pct = min(returns)
    avg_r_multiple = float(np.mean(r_multiples))
    win_rs = [r for r in r_multiples if r > 0]
    loss_rs = [abs(r) for r in r_multiples if r <= 0]
    avg_win_r = float(np.mean(win_rs)) if win_rs else 0.0
    avg_loss_r = float(np.mean(loss_rs)) if loss_rs else 0.0
    expectancy_r = (win_rate / 100 * avg_win_r) - ((1 - win_rate / 100) * avg_loss_r)
    timeframe_value = str(timeframe or "").strip().lower()
    try:
        if timeframe_value.endswith("m"):
            tf_hours = float(timeframe_value[:-1]) / 60
            trades_per_year = 8760 / (24 * tf_hours)
        elif timeframe_value.endswith("h"):
            tf_hours = float(timeframe_value[:-1])
            trades_per_year = 8760 / (24 * tf_hours)
        else:
            trades_per_year = 365
    except (TypeError, ValueError, ZeroDivisionError):
        trades_per_year = 365
    std_trade_pct = float(np.std(returns, ddof=1)) if n_trades >= 5 else 0.0
    sharpe_ratio = (
        avg_trade_pct / std_trade_pct * np.sqrt(trades_per_year)
        if std_trade_pct > 0 and n_trades >= 5
        else None
    )
    calmar_ratio = total_return_pct / max_drawdown if max_drawdown > 0 else None
    consecutive_losses_max = 0
    current_losses = 0
    for trade in trades:
        if trade["win"]:
            current_losses = 0
        else:
            current_losses += 1
            consecutive_losses_max = max(consecutive_losses_max, current_losses)

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
        "exchange": source_exchange,
        "exchange_mode": exchange_mode,
        "market_type": source_market_type,
        "mode": mode,
        "strategy_engine": "strategy_engine.evaluate_signal",
        "risk_per_trade_pct": config.RISK_PER_TRADE_PCT,
        "avg_r_multiple": round(avg_r_multiple, 3),
        "expectancy_r": round(expectancy_r, 3),
        "gap_losses": gap_losses,
        "sharpe_ratio": round(sharpe_ratio, 3) if sharpe_ratio is not None else None,
        "calmar_ratio": round(calmar_ratio, 3) if calmar_ratio is not None else None,
        "consecutive_losses_max": consecutive_losses_max,
    }
