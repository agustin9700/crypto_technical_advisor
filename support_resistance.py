import pandas as pd
import numpy as np


def find_support_resistance(df: pd.DataFrame, lookback: int = 120) -> tuple:
    """
    Find support and resistance levels from recent price history.
    Uses local minima and maxima from a rolling window.
    No lookahead: only uses data up to the last available candle.
    """
    data = df.tail(lookback).copy().reset_index(drop=True)

    window = 5
    supports = []
    resistances = []

    highs = data["high"].values
    lows = data["low"].values
    closes = data["close"].values

    for i in range(window, len(data) - window):
        # Local minimum (support)
        if lows[i] == min(lows[i - window:i + window + 1]):
            supports.append(lows[i])
        # Local maximum (resistance)
        if highs[i] == max(highs[i - window:i + window + 1]):
            resistances.append(highs[i])

    supports = _cluster_levels(supports)
    resistances = _cluster_levels(resistances)

    return supports, resistances


def _cluster_levels(levels: list, tolerance_pct: float = 0.015) -> list:
    """Merge levels that are within tolerance_pct of each other."""
    if not levels:
        return []

    levels = sorted(levels)
    clustered = []
    group = [levels[0]]

    for level in levels[1:]:
        if (level - group[0]) / group[0] <= tolerance_pct:
            group.append(level)
        else:
            clustered.append(np.mean(group))
            group = [level]

    clustered.append(np.mean(group))
    return clustered


def nearest_level(price: float, levels: list) -> float:
    """Return the level closest to price."""
    if not levels:
        return None
    return min(levels, key=lambda x: abs(x - price))


def nearest_support_below(price: float, supports: list) -> float:
    """Devuelve el soporte más cercano menor que price."""
    valid_supports = [s for s in supports if s < price]
    if not valid_supports:
        return None
    return max(valid_supports)


def nearest_resistance_above(price: float, resistances: list) -> float:
    """Devuelve la resistencia más cercana mayor que price."""
    valid_resistances = [r for r in resistances if r > price]
    if not valid_resistances:
        return None
    return min(valid_resistances)


def distance_pct(price: float, level: float) -> float:
    """Return signed distance from price to level as percentage."""
    if level is None or price == 0:
        return None
    return (level - price) / price * 100
