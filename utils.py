from datetime import datetime, timezone


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def format_price(value, decimals: int = None) -> str:
    if value is None:
        return "N/A"
    try:
        value = float(value)
    except (TypeError, ValueError):
        return str(value)

    if decimals is not None:
        return f"{value:.{decimals}f}"

    abs_value = abs(value)
    if abs_value == 0:
        return "0"
    if abs_value >= 100:
        return f"{value:.2f}"
    if abs_value >= 1:
        return f"{value:.4f}"
    if abs_value >= 0.01:
        return f"{value:.5f}"
    if abs_value >= 0.0001:
        return f"{value:.8f}"
    return f"{value:.12f}"


def decision_color(decision: str) -> str:
    """Return a color name for a decision string."""
    mapping = {
        "ENTER_NOW_CANDIDATE": "green",
        "WAIT": "orange",
        "AVOID": "red",
        "NO_DATA": "gray",
    }
    return mapping.get(decision, "gray")


def decision_emoji(decision: str) -> str:
    mapping = {
        "ENTER_NOW_CANDIDATE": "✅",
        "WAIT": "⏳",
        "AVOID": "🚫",
        "NO_DATA": "❓",
    }
    return mapping.get(decision, "❓")


def verdict_emoji(verdict: str) -> str:
    mapping = {
        "BACKTEST_OK": "✅",
        "BACKTEST_WEAK": "⚠️",
        "BACKTEST_BAD": "❌",
        "NOT_ENOUGH_TRADES": "📉",
        "NO_DATA": "❓",
    }
    return mapping.get(verdict, "❓")
