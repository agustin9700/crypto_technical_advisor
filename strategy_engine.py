from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

import config
import indicators
import support_resistance as sr_module


VOLUME_CONFIRMATION_THRESHOLD = 1.2
VOLUME_VERY_LOW_THRESHOLD = 0.8
LEVERAGE_WARNING = (
    "El apalancamiento aumenta mucho el riesgo de liquidación. "
    "Esto es solo análisis técnico, no consejo financiero."
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _volume_confirmation_text(vol_ratio) -> str:
    vol_text = f"{vol_ratio:.2f}x" if pd.notna(vol_ratio) else "N/A"
    min_text = f"{VOLUME_CONFIRMATION_THRESHOLD:.2f}x"
    if pd.isna(vol_ratio):
        return f"Volumen insuficiente para confirmar: {vol_text} / {min_text}"
    if vol_ratio < VOLUME_VERY_LOW_THRESHOLD:
        return f"Volumen muy bajo: {vol_text} / {min_text}"
    if vol_ratio < VOLUME_CONFIRMATION_THRESHOLD:
        return f"Volumen insuficiente para confirmar: {vol_text} / {min_text}"
    return f"Volumen confirma: {vol_text} / {min_text}"


def compute_spot_score(row: pd.Series, prev_row: pd.Series = None) -> tuple:
    score = 0
    score_max = 10
    reasons = []
    missing = []
    warnings = []

    price = row["close"]
    rsi_val = row["rsi"]
    ema20 = row["ema20"]
    ema50 = row["ema50"]
    ema200 = row["ema200"]
    macd_val = row["macd"]
    macd_sig = row["macd_signal"]
    vol_ratio = row["vol_ratio"]

    if price > ema200:
        score += 2
        reasons.append("Precio sobre EMA200 (+2)")
    else:
        missing.append("Precio bajo EMA200")

    if ema20 > ema50:
        score += 1
        reasons.append("EMA20 > EMA50 (+1)")
    else:
        missing.append("EMA20 no supera EMA50")

    if price > ema50:
        score += 1
        reasons.append("Precio sobre EMA50 (+1)")
    else:
        missing.append("Precio bajo EMA50")

    if 50 <= rsi_val <= 70:
        score += 2
        reasons.append(f"RSI {rsi_val:.1f} en zona alcista 50-70 (+2)")
    elif 45 <= rsi_val < 50:
        if prev_row is not None and rsi_val > prev_row["rsi"]:
            score += 1
            reasons.append(f"RSI {rsi_val:.1f} subiendo hacia 50 (+1)")
        else:
            missing.append(f"RSI {rsi_val:.1f} cerca de 50 pero sin confirmar subida")
    else:
        missing.append(f"RSI {rsi_val:.1f} fuera de zona ideal (50-70)")

    if macd_val > macd_sig:
        score += 1
        reasons.append("MACD sobre signal (+1)")
    else:
        missing.append("MACD bajo signal")

    if pd.notna(vol_ratio) and vol_ratio >= VOLUME_CONFIRMATION_THRESHOLD:
        score += 1
        reasons.append(f"{_volume_confirmation_text(vol_ratio)} (+1)")
    else:
        missing.append(_volume_confirmation_text(vol_ratio))

    if pd.notna(vol_ratio) and vol_ratio < VOLUME_VERY_LOW_THRESHOLD:
        score -= 1
        warnings.append(f"{_volume_confirmation_text(vol_ratio)} (-1)")
    if rsi_val < 40:
        score -= 2
        warnings.append(f"RSI muy bajo: {rsi_val:.1f} (-2)")
    if price < ema200 and rsi_val < 50:
        score -= 2
        warnings.append("Precio bajo EMA200 con RSI < 50 (-2)")

    return max(0, min(score, score_max)), score_max, reasons, missing, warnings


def dynamic_sl_tp_mult(atr_pct: float) -> tuple[float, float]:
    try:
        atr_pct = float(atr_pct)
    except (TypeError, ValueError):
        atr_pct = 3.0
    if atr_pct >= 5.0:
        sl_mult, tp_mult = 1.5, 2.5
    elif atr_pct >= 3.0:
        sl_mult, tp_mult = 2.0, 3.0
    elif atr_pct >= 1.5:
        sl_mult, tp_mult = 2.5, 3.5
    else:
        sl_mult, tp_mult = 3.0, 4.0
    if sl_mult > 0 and tp_mult / sl_mult < config.MIN_RR_RATIO:
        tp_mult = sl_mult * config.MIN_RR_RATIO
    return sl_mult, tp_mult


def compute_long_rr(price: float, atr_val: float) -> tuple:
    entry = price
    atr_pct = atr_val / entry * 100 if entry > 0 else 3.0
    sl_mult, tp_mult = dynamic_sl_tp_mult(atr_pct)
    sl = entry - sl_mult * atr_val
    tp = entry + tp_mult * atr_val
    risk_pct = (entry - sl) / entry * 100 if entry else 0
    reward_pct = (tp - entry) / entry * 100 if entry else 0
    rr_ratio = reward_pct / risk_pct if risk_pct > 0 else 0
    return entry, sl, tp, risk_pct, reward_pct, rr_ratio


def compute_short_rr(price: float, atr_val: float) -> tuple:
    entry = price
    atr_pct = atr_val / entry * 100 if entry > 0 else 3.0
    sl_mult, tp_mult = dynamic_sl_tp_mult(atr_pct)
    sl = entry + sl_mult * atr_val
    tp = entry - tp_mult * atr_val
    risk_pct = (sl - entry) / entry * 100 if entry else 0
    reward_pct = (entry - tp) / entry * 100 if entry else 0
    rr_ratio = reward_pct / risk_pct if risk_pct > 0 else 0
    return entry, sl, tp, risk_pct, reward_pct, rr_ratio


def decide_spot(score: int, regime_ok: bool, rr_ratio: float, dist_to_resistance_pct: float,
                vol_ratio: float, rsi_val: float, btc_regime: str = "NEUTRAL",
                warnings: list = None) -> str:
    near_resistance = dist_to_resistance_pct is not None and 0 < dist_to_resistance_pct < 1.5
    if (
        score >= 7
        and regime_ok
        and rr_ratio + 1e-9 >= config.MIN_RR_RATIO
        and not near_resistance
        and (pd.isna(vol_ratio) or vol_ratio >= VOLUME_VERY_LOW_THRESHOLD)
    ):
        if btc_regime == "BEAR":
            warning = "Regimen BTC bajista: señal degradada"
            if warnings is not None and warning not in warnings:
                warnings.append(warning)
            return "WAIT"
        return "ENTER_NOW_CANDIDATE"
    if score < 5 or not regime_ok or rsi_val < 40:
        return "AVOID"
    if near_resistance and rr_ratio < config.MIN_RR_RATIO:
        return "AVOID"
    return "WAIT"


def _ensure_indicator_frame(df: pd.DataFrame) -> pd.DataFrame:
    required = {"ema20", "ema50", "ema200", "rsi", "atr", "macd", "macd_signal", "vol_ratio"}
    if required.issubset(df.columns):
        return df.copy()
    return indicators.add_indicators(df.copy())


def _normal_market_type(market_type: str) -> str:
    value = (market_type or "spot").strip().lower()
    if value in {"future", "swap", "perp", "perpetual"}:
        return "futures"
    return value


def _source_value(df: pd.DataFrame, key: str, default=None):
    return (getattr(df, "attrs", {}) or {}).get(key, default)


def evaluate_signal(
    df,
    symbol: str,
    mode: str,
    timeframe: str,
    exchange_id: str | None = None,
    market_type: str = "spot",
    config: dict | None = None,
) -> dict:
    frame = _ensure_indicator_frame(df)
    frame = frame.dropna(subset=["ema20", "ema50", "ema200", "rsi", "atr", "macd", "macd_signal"]).reset_index(drop=True)
    market_type = _normal_market_type(market_type)
    mode_value = (mode or market_type or "spot").strip().lower()

    if len(frame) < 2:
        return {
            "decision": "WAIT",
            "score": 0.0,
            "reasons": [],
            "warnings": ["Not enough data after indicators"],
            "entry": None,
            "stop_loss": None,
            "take_profit": None,
            "risk_reward": None,
            "symbol": symbol,
            "timeframe": timeframe,
            "exchange": exchange_id or _source_value(df, "data_source_exchange"),
            "market_type": market_type,
            "raw": {},
        }

    row = frame.iloc[-1]
    prev_row = frame.iloc[-2]
    if mode_value == "futures" or market_type == "futures":
        return _evaluate_futures_frame(
            frame,
            symbol,
            timeframe,
            exchange_id or _source_value(df, "data_source_exchange"),
            market_type,
            source_warnings=(config or {}).get("source_warnings") or _source_value(df, "data_warnings", []),
        )

    price = _safe_float(row.get("close"))
    atr = _safe_float(row.get("atr"))
    supports, resistances = sr_module.find_support_resistance(frame, lookback=120)
    nearest_sup = sr_module.nearest_support_below(price, supports)
    nearest_res = sr_module.nearest_resistance_above(price, resistances)
    dist_res = sr_module.distance_pct(price, nearest_res)
    score, score_max, reasons, missing, warnings = compute_spot_score(row, prev_row)
    entry, sl, tp, risk_pct, reward_pct, rr_ratio = compute_long_rr(price, atr)
    regime_ok = price > _safe_float(row.get("ema200")) and _safe_float(row.get("rsi")) >= 50
    decision = decide_spot(
        score,
        regime_ok,
        rr_ratio,
        dist_res,
        row.get("vol_ratio"),
        _safe_float(row.get("rsi")),
        btc_regime=(config or {}).get("btc_regime", "NEUTRAL"),
        warnings=warnings,
    )
    return {
        "decision": decision,
        "score": float(score),
        "reasons": reasons,
        "warnings": warnings,
        "entry": float(entry),
        "stop_loss": float(sl),
        "take_profit": float(tp),
        "risk_reward": float(rr_ratio),
        "symbol": symbol,
        "timeframe": timeframe,
        "exchange": exchange_id or _source_value(df, "data_source_exchange"),
        "market_type": market_type,
        "raw": {
            "score_max": score_max,
            "missing_conditions": missing,
            "risk_pct": risk_pct,
            "reward_pct": reward_pct,
            "nearest_support": nearest_sup,
            "nearest_resistance": nearest_res,
            "price": price,
            "analysis_time": datetime.now(timezone.utc).isoformat(),
        },
    }


def _round_value(value, decimals: int = 6):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(value):
        return None
    return round(value, decimals)


def _latest_futures_levels(df: pd.DataFrame, price: float) -> tuple:
    levels_df = df.iloc[:-1] if len(df) > 20 else df
    supports, resistances = sr_module.find_support_resistance(levels_df, lookback=120)
    nearest_support = sr_module.nearest_support_below(price, supports)
    nearest_resistance = sr_module.nearest_resistance_above(price, resistances)
    broken_resistance = max([level for level in resistances if level <= price], default=None)
    lost_support = min([level for level in supports if level >= price], default=None)
    return supports, resistances, nearest_support, nearest_resistance, broken_resistance, lost_support


def _futures_structure_flags(df: pd.DataFrame) -> tuple:
    if len(df) < 12:
        return False, False
    recent = df.tail(6)
    previous = df.iloc[-12:-6]
    bullish = recent["high"].max() > previous["high"].max() and recent["low"].min() > previous["low"].min()
    bearish = recent["high"].max() < previous["high"].max() and recent["low"].min() < previous["low"].min()
    return bool(bullish), bool(bearish)


def _distance_pct(price: float, level: float) -> float:
    if level is None or price <= 0:
        return None
    return abs(price - level) / price * 100


def score_futures_direction(
    row,
    price: float,
    nearest_support,
    nearest_resistance,
    broken_resistance,
    lost_support,
    bullish_structure,
    bearish_structure,
) -> dict:
    ema20 = _safe_float(row.get("ema20"))
    ema50 = _safe_float(row.get("ema50"))
    ema200 = _safe_float(row.get("ema200"))
    rsi = _safe_float(row.get("rsi"))
    macd = _safe_float(row.get("macd"))
    macd_signal = _safe_float(row.get("macd_signal"))
    vol_ratio = _safe_float(row.get("vol_ratio"))
    volume_confirms = vol_ratio >= VOLUME_CONFIRMATION_THRESHOLD

    long_score = 0
    short_score = 0
    long_reasons = []
    short_reasons = []
    penalties = []
    missing = []

    if price > ema200:
        long_score += 2
        long_reasons.append("precio sobre EMA200")
    if price < ema200:
        short_score += 2
        short_reasons.append("precio bajo EMA200")
    if ema20 > ema50:
        long_score += 1
        long_reasons.append("EMA20 sobre EMA50")
    if ema20 < ema50:
        short_score += 1
        short_reasons.append("EMA20 bajo EMA50")
    if price > ema50:
        long_score += 1
        long_reasons.append("precio sobre EMA50")
    if price < ema50:
        short_score += 1
        short_reasons.append("precio bajo EMA50")
    if 50 <= rsi <= 70:
        long_score += 2
        long_reasons.append("RSI favorable para long")
    if 30 <= rsi <= 50:
        short_score += 2
        short_reasons.append("RSI favorable para short")
    if macd > macd_signal:
        long_score += 1
        long_reasons.append("MACD sobre señal")
    if macd < macd_signal:
        short_score += 1
        short_reasons.append("MACD bajo señal")
    if volume_confirms:
        long_score += 1
        short_score += 1
        long_reasons.append("volumen relativo confirma")
        short_reasons.append("volumen relativo confirma")
    if broken_resistance is not None and volume_confirms:
        long_score += 1
        long_reasons.append("ruptura de resistencia con volumen")
    if bullish_structure:
        long_score += 1
        long_reasons.append("estructura alcista simple")
    if lost_support is not None and volume_confirms:
        short_score += 1
        short_reasons.append("pérdida de soporte con volumen")
    if bearish_structure:
        short_score += 1
        short_reasons.append("estructura bajista simple")

    near_resistance = nearest_resistance is not None and (_distance_pct(price, nearest_resistance) or 999) <= 1.0
    near_support = nearest_support is not None and (_distance_pct(price, nearest_support) or 999) <= 1.0
    if near_resistance and broken_resistance is None:
        long_score -= 2
        penalties.append("long penalizado: precio cerca de resistencia sin ruptura")
    if rsi > 75:
        long_score -= 1
        penalties.append("long penalizado: RSI sobrecomprado")
    if vol_ratio < VOLUME_VERY_LOW_THRESHOLD:
        long_score -= 1
        short_score -= 1
        penalties.append("volumen bajo")
    if price < ema200 and price < ema50:
        long_score -= 2
        penalties.append("long penalizado: precio bajo EMA200 y EMA50")

    if near_support and lost_support is None:
        short_score -= 2
        penalties.append("short penalizado: precio cerca de soporte sin ruptura")
    if rsi < 25:
        short_score -= 1
        penalties.append("short penalizado: RSI sobrevendido")
    if price > ema200 and price > ema50:
        short_score -= 2
        penalties.append("short penalizado: precio sobre EMA200 y EMA50")

    if not volume_confirms:
        missing.append("confirmar volumen relativo >= 1.20")
    if broken_resistance is None:
        missing.append("ruptura de resistencia para long")
    if lost_support is None:
        missing.append("pérdida de soporte para short")

    return {
        "long_score": int(max(0, min(10, long_score))),
        "short_score": int(max(0, min(10, short_score))),
        "long_reasons": long_reasons,
        "short_reasons": short_reasons,
        "penalties": penalties,
        "missing_conditions": missing,
        "volume_confirms": volume_confirms,
        "near_support": near_support,
        "near_resistance": near_resistance,
    }


def futures_trade_plan(direction: str, price: float, atr: float, nearest_support, nearest_resistance) -> dict:
    atr_stop = max(atr * 1.5, price * 0.005)
    if direction == "LONG":
        stop_loss = nearest_support if nearest_support and nearest_support < price else price - atr_stop
        risk = max(price - stop_loss, atr_stop)
        take_profit_1 = price + risk * 1.5
        take_profit_2 = price + risk * 2.5
        invalidation = "pérdida de soporte / cierre bajo EMA50 / cierre bajo EMA200"
    elif direction == "SHORT":
        stop_loss = nearest_resistance if nearest_resistance and nearest_resistance > price else price + atr_stop
        risk = max(stop_loss - price, atr_stop)
        take_profit_1 = price - risk * 1.5
        take_profit_2 = price - risk * 2.5
        invalidation = "ruptura de resistencia / cierre sobre EMA50 / cierre sobre EMA200"
    else:
        return {
            "entry_price": price,
            "stop_loss": None,
            "take_profit_1": None,
            "take_profit_2": None,
            "rr_ratio": None,
            "risk_pct_to_stop": None,
            "invalidation": "No aplica: sin dirección clara",
        }

    risk_pct = risk / price * 100 if price else None
    reward = abs(take_profit_2 - price)
    rr_ratio = reward / risk if risk else None
    return {
        "entry_price": _round_value(price),
        "stop_loss": _round_value(stop_loss),
        "take_profit_1": _round_value(take_profit_1),
        "take_profit_2": _round_value(take_profit_2),
        "rr_ratio": round(rr_ratio, 3) if rr_ratio is not None else None,
        "risk_pct_to_stop": round(risk_pct, 3) if risk_pct is not None else None,
        "invalidation": invalidation,
    }


def futures_decision_from_scores(long_score: int, short_score: int, volume_confirms: bool) -> tuple:
    if long_score >= 7 and long_score >= short_score + 2:
        return "LONG", "LONG", bool(volume_confirms)
    if short_score >= 7 and short_score >= long_score + 2:
        return "SHORT", "SHORT", bool(volume_confirms)
    if max(long_score, short_score) >= 5:
        direction = "LONG" if long_score > short_score else "SHORT" if short_score > long_score else "NEUTRAL"
        return "WAIT", direction, False
    return "AVOID", "NEUTRAL", False


def futures_leverage_fields(risk_pct_to_stop, atr_pct) -> dict:
    risk = _safe_float(risk_pct_to_stop, 999)
    atr_pct = _safe_float(atr_pct)
    if atr_pct >= 5:
        max_leverage = 1
        label = "1x-2x máximo por volatilidad alta"
    elif risk <= 1:
        max_leverage = 2
        label = "máximo 2x"
    elif risk <= 2.5:
        max_leverage = 3
        label = "máximo 3x"
    else:
        max_leverage = 2
        label = "bajo, máximo 2x"
    return {
        "suggested_leverage_label": label,
        "suggested_leverage_max": max_leverage,
        "leverage_warning": LEVERAGE_WARNING,
    }


def _futures_texts(decision: str, entry_now: bool) -> tuple[str, str]:
    if decision == "LONG":
        if entry_now:
            return (
                "Setup futures LONG con score dominante y volumen confirmado.",
                "LONG técnico con entrada posible ahora si se respeta el stop.",
            )
        return (
            "Setup futures LONG por score, pero falta confirmación de volumen para entrada inmediata.",
            "Sesgo LONG; esperar confirmación antes de entrar.",
        )
    if decision == "SHORT":
        if entry_now:
            return (
                "Setup futures SHORT con score dominante y volumen confirmado.",
                "SHORT técnico con entrada posible ahora si se respeta el stop.",
            )
        return (
            "Setup futures SHORT por score, pero falta confirmación de volumen para entrada inmediata.",
            "Sesgo SHORT; esperar confirmación antes de entrar.",
        )
    if decision == "WAIT":
        return (
            "Hay sesgo técnico, pero falta confirmación suficiente para entrada futures inmediata.",
            "Esperar confirmación de volumen/ruptura antes de operar futures.",
        )
    return (
        "No hay ventaja técnica futures clara.",
        "Evitar operación futures hasta que aparezca dirección clara.",
    )


def _evaluate_futures_frame(
    frame: pd.DataFrame,
    symbol: str,
    timeframe: str,
    exchange_id: str | None,
    market_type: str,
    source_warnings: list | None = None,
) -> dict:
    row = frame.iloc[-1]
    price = _safe_float(row.get("close"))
    atr = _safe_float(row.get("atr"))
    _, _, nearest_support, nearest_resistance, broken_resistance, lost_support = _latest_futures_levels(frame, price)
    bullish_structure, bearish_structure = _futures_structure_flags(frame)
    score_meta = score_futures_direction(
        row,
        price,
        nearest_support,
        nearest_resistance,
        broken_resistance,
        lost_support,
        bullish_structure,
        bearish_structure,
    )
    long_score = score_meta["long_score"]
    short_score = score_meta["short_score"]
    decision, direction, entry_now = futures_decision_from_scores(
        long_score,
        short_score,
        score_meta["volume_confirms"],
    )
    plan_direction = direction if decision in ("LONG", "SHORT", "WAIT") and direction != "NEUTRAL" else "NEUTRAL"
    trade_plan = futures_trade_plan(plan_direction, price, atr, nearest_support, nearest_resistance)
    leverage = futures_leverage_fields(trade_plan.get("risk_pct_to_stop"), row.get("atr_pct"))
    confidence = int(max(long_score, short_score) * 10)
    main_reason, action_summary = _futures_texts(decision, entry_now)
    reasons = score_meta["long_reasons"] if direction == "LONG" else score_meta["short_reasons"] if direction == "SHORT" else []
    warnings = list(score_meta["penalties"])
    warnings.extend(source_warnings or [])
    warnings.append(LEVERAGE_WARNING)
    take_profit = trade_plan.get("take_profit_1") or trade_plan.get("take_profit_2")

    return {
        "decision": decision,
        "score": float(max(long_score, short_score)),
        "reasons": reasons,
        "warnings": warnings,
        "entry": trade_plan.get("entry_price"),
        "stop_loss": trade_plan.get("stop_loss"),
        "take_profit": take_profit,
        "risk_reward": trade_plan.get("rr_ratio"),
        "symbol": symbol,
        "timeframe": timeframe,
        "exchange": exchange_id,
        "market_type": market_type,
        "raw": {
            "long_score": long_score,
            "short_score": short_score,
            "confidence": confidence,
            "direction": direction,
            "entry_now": bool(entry_now),
            **trade_plan,
            **leverage,
            "main_reason": main_reason,
            "action_summary": action_summary,
            "missing_conditions": score_meta["missing_conditions"],
            "volume_confirms": score_meta["volume_confirms"],
            "nearest_support": nearest_support,
            "nearest_resistance": nearest_resistance,
            "broken_resistance": broken_resistance,
            "lost_support": lost_support,
            "price": price,
            "rsi": _safe_float(row.get("rsi")),
            "ema20": _safe_float(row.get("ema20")),
            "ema50": _safe_float(row.get("ema50")),
            "ema200": _safe_float(row.get("ema200")),
            "macd": _safe_float(row.get("macd")),
            "macd_signal": _safe_float(row.get("macd_signal")),
            "atr": _safe_float(row.get("atr")),
            "atr_pct": _safe_float(row.get("atr_pct")),
            "bb_upper": _safe_float(row.get("bb_upper")),
            "bb_mid": _safe_float(row.get("bb_mid")),
            "bb_lower": _safe_float(row.get("bb_lower")),
            "vol_ratio": _safe_float(row.get("vol_ratio")),
            "no_clear_setup": decision in ("WAIT", "AVOID"),
            "analysis_time": datetime.now(timezone.utc).isoformat(),
        },
    }


def _legacy_evaluate_futures_row(row: pd.Series, symbol: str, timeframe: str, exchange_id: str | None, market_type: str) -> dict:
    price = _safe_float(row.get("close"))
    ema20 = _safe_float(row.get("ema20"))
    ema50 = _safe_float(row.get("ema50"))
    ema200 = _safe_float(row.get("ema200"))
    rsi = _safe_float(row.get("rsi"))
    macd = _safe_float(row.get("macd"))
    macd_signal = _safe_float(row.get("macd_signal"))
    vol_ratio = _safe_float(row.get("vol_ratio"))
    atr = _safe_float(row.get("atr"))

    long_score = 0
    short_score = 0
    long_reasons = []
    short_reasons = []
    warnings = []

    if price > ema200:
        long_score += 2
        long_reasons.append("precio sobre EMA200")
    else:
        short_score += 2
        short_reasons.append("precio bajo EMA200")
    if ema20 > ema50:
        long_score += 1
        long_reasons.append("EMA20 sobre EMA50")
    elif ema20 < ema50:
        short_score += 1
        short_reasons.append("EMA20 bajo EMA50")
    if price > ema50:
        long_score += 1
        long_reasons.append("precio sobre EMA50")
    elif price < ema50:
        short_score += 1
        short_reasons.append("precio bajo EMA50")
    if 50 <= rsi <= 70:
        long_score += 2
        long_reasons.append("RSI favorable para long")
    if 30 <= rsi <= 50:
        short_score += 2
        short_reasons.append("RSI favorable para short")
    if macd > macd_signal:
        long_score += 1
        long_reasons.append("MACD sobre señal")
    elif macd < macd_signal:
        short_score += 1
        short_reasons.append("MACD bajo señal")
    if vol_ratio >= VOLUME_CONFIRMATION_THRESHOLD:
        long_score += 1
        short_score += 1
    elif vol_ratio < VOLUME_VERY_LOW_THRESHOLD:
        warnings.append("volumen bajo")

    long_score = int(max(0, min(10, long_score)))
    short_score = int(max(0, min(10, short_score)))
    if long_score >= 7 and long_score >= short_score + 2:
        decision = "LONG"
        reasons = long_reasons
        entry, sl, tp, _, _, rr_ratio = compute_long_rr(price, atr)
    elif short_score >= 7 and short_score >= long_score + 2:
        decision = "SHORT"
        reasons = short_reasons
        entry, sl, tp, _, _, rr_ratio = compute_short_rr(price, atr)
    else:
        decision = "WAIT" if max(long_score, short_score) >= 5 else "AVOID"
        reasons = long_reasons if long_score >= short_score else short_reasons
        entry, sl, tp, rr_ratio = price, None, None, None

    return {
        "decision": decision,
        "score": float(max(long_score, short_score)),
        "reasons": reasons,
        "warnings": warnings,
        "entry": float(entry) if entry is not None else None,
        "stop_loss": float(sl) if sl is not None else None,
        "take_profit": float(tp) if tp is not None else None,
        "risk_reward": float(rr_ratio) if rr_ratio is not None else None,
        "symbol": symbol,
        "timeframe": timeframe,
        "exchange": exchange_id,
        "market_type": market_type,
        "raw": {
            "long_score": long_score,
            "short_score": short_score,
            "price": price,
            "analysis_time": datetime.now(timezone.utc).isoformat(),
        },
    }


def normalize_analysis_result(result: dict, mode: str = "spot", market_type: str = "spot") -> dict:
    best = result.get("best_setup") or result
    return {
        "decision": result.get("decision") or best.get("decision") or "WAIT",
        "score": float(best.get("score") or best.get("long_score") or best.get("short_score") or 0),
        "reasons": list(best.get("reasons") or []),
        "warnings": list(best.get("warnings") or result.get("warnings") or []),
        "entry": best.get("estimated_entry") or best.get("entry_price"),
        "stop_loss": best.get("estimated_stop_loss") or best.get("stop_loss"),
        "take_profit": best.get("estimated_take_profit") or best.get("take_profit_1"),
        "risk_reward": best.get("rr_ratio"),
        "symbol": result.get("symbol") or best.get("symbol"),
        "timeframe": result.get("recommended_timeframe") or best.get("timeframe"),
        "exchange": result.get("data_source_exchange") or best.get("data_source_exchange"),
        "market_type": result.get("market_type") or best.get("market_type") or market_type,
        "raw": {"mode": mode, **dict(result)},
    }
