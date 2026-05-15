import pandas as pd
import pytest
import performance_metrics

def test_normalize_strategy_profile_empty():
    df = pd.DataFrame()
    res = performance_metrics.normalize_strategy_profile(df)
    assert res.empty

def test_normalize_strategy_profile_legacy():
    df = pd.DataFrame({"symbol": ["BTC/USDT"]})
    res = performance_metrics.normalize_strategy_profile(df, default="legacy")
    assert "strategy_profile" in res.columns
    assert res["strategy_profile"].iloc[0] == "legacy"

def test_calculate_trade_metrics_empty():
    df = pd.DataFrame()
    m = performance_metrics.calculate_trade_metrics(df)
    assert m["total_trades"] == 0
    assert m["winrate"] == 0.0

def test_calculate_trade_metrics_basic():
    df = pd.DataFrame({
        "status": ["CLOSED", "CLOSED", "CLOSED"],
        "net_pnl": [10.0, -5.0, 15.0],
        "opened_at": ["2026-05-01 10:00", "2026-05-01 11:00", "2026-05-01 12:00"],
        "closed_at": ["2026-05-01 12:00", "2026-05-01 13:00", "2026-05-01 15:00"]
    })
    m = performance_metrics.calculate_trade_metrics(df)
    assert m["total_trades"] == 3
    assert m["winning_trades"] == 2
    assert m["losing_trades"] == 1
    assert m["winrate"] == pytest.approx(66.67, 0.1)
    assert m["total_pnl"] == 20.0
    assert m["profit_factor"] == 5.0 # (10+15)/5
    assert m["expectancy"] == pytest.approx(6.6667, abs=1e-3)

def test_calculate_strategy_comparison():
    sig = pd.DataFrame({
        "strategy_profile": ["conservative", "aggressive", None],
        "decision": ["ENTER", "ENTER", "ENTER"],
        "score": [8, 9, 7]
    })
    trd = pd.DataFrame({
        "strategy_profile": ["conservative", "aggressive", "conservative"],
        "status": ["CLOSED", "CLOSED", "CLOSED"],
        "net_pnl": [10, 20, -5]
    })
    comp = performance_metrics.calculate_strategy_comparison(sig, trd)
    assert len(comp) == 3 # conservative, aggressive, legacy
    
    cons = comp[comp["strategy_profile"] == "conservative"].iloc[0]
    assert cons["total_signals"] == 1
    assert cons["total_trades"] == 2
    assert cons["total_pnl"] == 5.0
    
    agg = comp[comp["strategy_profile"] == "aggressive"].iloc[0]
    assert agg["total_pnl"] == 20.0

def test_calculate_equity_curve():
    trd = pd.DataFrame({
        "strategy_profile": ["balanced", "balanced"],
        "status": ["CLOSED", "CLOSED"],
        "net_pnl": [10, 15],
        "closed_at": ["2026-05-01 10:00", "2026-05-01 12:00"]
    })
    curve = performance_metrics.calculate_equity_curve(trd)
    assert len(curve) == 2
    assert curve["equity"].iloc[0] == 10
    assert curve["equity"].iloc[1] == 25

if __name__ == "__main__":
    pytest.main([__file__])
