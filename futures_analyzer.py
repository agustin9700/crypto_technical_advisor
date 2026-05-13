import math

import pandas as pd

import config
import data_provider
import indicators
import support_resistance
import utils


FUTURES_TIMEFRAMES = ["15m", "30m", "1h", "2h", "4h"]
LEVERAGE_WARNING = (
    "El apalancamiento aumenta mucho el riesgo de liquidación. "
    "Esto es solo análisis técnico, no consejo financiero."
)


def _round_value(value, decimals: int = 6):
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    return round(value, decimals)


def _safe_float(value, default: float = 0.0) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(value):
        return default
    return value


def _copy_from_cache(data_cache: dict, cache_key):
    if data_cache is None or cache_key not in data_cache:
        return None
    return data_provider.copy_df_with_attrs(data_cache[cache_key])


def _fetch_ohlcv_cached(
    symbol: str,
    timeframe: str,
    exchange_id=None,
    exchange_mode: str = "manual",
    ohlcv_limit: int = None,
    data_cache: dict = None,
) -> pd.DataFrame:
    symbol = data_provider.normalize_symbol(symbol)
    cache_limit = ohlcv_limit if ohlcv_limit is not None else "days:400"
    cache_key = ("FUTURES", symbol, timeframe, cache_limit, exchange_id or config.DEFAULT_EXCHANGE, exchange_mode)
    cached = _copy_from_cache(data_cache, cache_key)
    if cached is not None:
        return cached

    df = data_provider.fetch_ohlcv_with_fallback(
        symbol,
        timeframe,
        days=400,
        ohlcv_limit=ohlcv_limit,
        exchange_id=exchange_id,
        exchange_mode=exchange_mode,
    )
    df = data_provider.copy_df_with_attrs(df)
    if data_cache is not None:
        data_cache[cache_key] = data_provider.copy_df_with_attrs(df)
    return df


def _source_meta_from_df(df: pd.DataFrame) -> dict:
    attrs = getattr(df, "attrs", {}) or {}
    return {
        "data_source_exchange": attrs.get("exchange_id") or attrs.get("data_source_exchange"),
        "exchange_mode": attrs.get("exchange_mode"),
        "fallback_used": attrs.get("fallback_used", False),
        "data_source_error": attrs.get("data_source_error"),
    }


def _data_unavailable_result(symbol: str, timeframe: str, error: str, exchange_id=None, exchange_mode="manual") -> dict:
    return {
        "mode": "FUTURES",
        "symbol": data_provider.normalize_symbol(symbol),
        "timeframe": timeframe,
        "recommended_timeframe": timeframe,
        "decision": "DATA_UNAVAILABLE",
        "status": "DATA_UNAVAILABLE",
        "direction": "NEUTRAL",
        "entry_now": False,
        "entry_price": None,
        "stop_loss": None,
        "take_profit_1": None,
        "take_profit_2": None,
        "rr_ratio": None,
        "risk_pct_to_stop": None,
        "long_score": 0,
        "short_score": 0,
        "confidence": 0,
        "main_reason": "No se pudieron obtener datos de mercado.",
        "action_summary": "No tomaría decisión futures sin datos suficientes.",
        "missing_conditions": ["obtener datos OHLCV desde un exchange disponible"],
        "warnings": [str(error)],
        "invalidation": "No aplica: sin datos",
        "suggested_leverage_label": "N/A",
        "suggested_leverage_max": None,
        "leverage_warning": LEVERAGE_WARNING,
        "data_source_exchange": exchange_id,
        "exchange_mode": exchange_mode,
        "fallback_used": False,
        "data_source_error": str(error),
        "no_clear_setup": True,
    }


def _latest_levels(df: pd.DataFrame, price: float) -> tuple:
    levels_df = df.iloc[:-1] if len(df) > 20 else df
    supports, resistances = support_resistance.find_support_resistance(levels_df, lookback=120)
    nearest_support = support_resistance.nearest_support_below(price, supports)
    nearest_resistance = support_resistance.nearest_resistance_above(price, resistances)
    broken_resistance = max([level for level in resistances if level <= price], default=None)
    lost_support = min([level for level in supports if level >= price], default=None)
    return supports, resistances, nearest_support, nearest_resistance, broken_resistance, lost_support


def _structure_flags(df: pd.DataFrame) -> tuple:
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


def _score_direction(row, price: float, nearest_support, nearest_resistance, broken_resistance, lost_support, bullish_structure, bearish_structure) -> tuple:
    ema20 = _safe_float(row.get("ema20"))
    ema50 = _safe_float(row.get("ema50"))
    ema200 = _safe_float(row.get("ema200"))
    rsi = _safe_float(row.get("rsi"))
    macd = _safe_float(row.get("macd"))
    macd_signal = _safe_float(row.get("macd_signal"))
    vol_ratio = _safe_float(row.get("vol_ratio"))
    volume_confirms = vol_ratio >= 1.20

    long_score = 0
    short_score = 0
    long_reasons = []
    short_reasons = []
    penalties = []
    missing = []

    if price > ema200:
        long_score += 2
        long_reasons.append("precio sobre EMA200")
    if ema20 > ema50:
        long_score += 1
        long_reasons.append("EMA20 sobre EMA50")
    if price > ema50:
        long_score += 1
        long_reasons.append("precio sobre EMA50")
    if 50 <= rsi <= 70:
        long_score += 2
        long_reasons.append("RSI favorable para long")
    if macd > macd_signal:
        long_score += 1
        long_reasons.append("MACD sobre señal")
    if volume_confirms:
        long_score += 1
        long_reasons.append("volumen relativo confirma")
    if broken_resistance is not None and volume_confirms:
        long_score += 1
        long_reasons.append("ruptura de resistencia con volumen")
    if bullish_structure:
        long_score += 1
        long_reasons.append("estructura alcista simple")

    if price < ema200:
        short_score += 2
        short_reasons.append("precio bajo EMA200")
    if ema20 < ema50:
        short_score += 1
        short_reasons.append("EMA20 bajo EMA50")
    if price < ema50:
        short_score += 1
        short_reasons.append("precio bajo EMA50")
    if 30 <= rsi <= 50:
        short_score += 2
        short_reasons.append("RSI favorable para short")
    if macd < macd_signal:
        short_score += 1
        short_reasons.append("MACD bajo señal")
    if volume_confirms:
        short_score += 1
        short_reasons.append("volumen relativo confirma")
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
    if vol_ratio < 0.80:
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


def _trade_plan(direction: str, price: float, atr: float, nearest_support, nearest_resistance) -> dict:
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


def _leverage_fields(risk_pct_to_stop, atr_pct) -> dict:
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


def _decision_from_scores(long_score: int, short_score: int, volume_confirms: bool) -> tuple:
    if long_score >= 7 and long_score >= short_score + 2:
        return "LONG", "LONG", bool(volume_confirms)
    if short_score >= 7 and short_score >= long_score + 2:
        return "SHORT", "SHORT", bool(volume_confirms)
    if max(long_score, short_score) >= 5:
        direction = "LONG" if long_score > short_score else "SHORT" if short_score > long_score else "NEUTRAL"
        return "WAIT", direction, False
    return "AVOID", "NEUTRAL", False


def analyze_futures_symbol_timeframe(
    symbol: str,
    timeframe: str,
    exchange_id: str | None = None,
    exchange_mode: str = "manual",
    ohlcv_limit: int | None = None,
    data_cache: dict | None = None,
) -> dict:
    symbol = data_provider.normalize_symbol(symbol)
    timeframe = timeframe or "1h"
    try:
        df_raw = _fetch_ohlcv_cached(
            symbol,
            timeframe,
            exchange_id=exchange_id,
            exchange_mode=exchange_mode,
            ohlcv_limit=ohlcv_limit,
            data_cache=data_cache,
        )
    except Exception as exc:
        return _data_unavailable_result(symbol, timeframe, exc, exchange_id=exchange_id, exchange_mode=exchange_mode)

    source_meta = _source_meta_from_df(df_raw)
    if df_raw is None or len(df_raw) < 220:
        return _data_unavailable_result(
            symbol,
            timeframe,
            "No hay suficientes velas para calcular EMA200 e indicadores futures.",
            exchange_id=source_meta.get("data_source_exchange") or exchange_id,
            exchange_mode=source_meta.get("exchange_mode") or exchange_mode,
        )

    df = indicators.add_indicators(df_raw)
    df = df.dropna(subset=["ema20", "ema50", "ema200", "rsi", "atr", "macd", "macd_signal", "vol_ratio"]).reset_index(drop=True)
    if len(df) < 2:
        return _data_unavailable_result(
            symbol,
            timeframe,
            "No hay suficientes velas válidas luego de indicadores.",
            exchange_id=source_meta.get("data_source_exchange") or exchange_id,
            exchange_mode=source_meta.get("exchange_mode") or exchange_mode,
        )

    row = df.iloc[-1]
    price = _safe_float(row.get("close"))
    atr = _safe_float(row.get("atr"))
    supports, resistances, nearest_support, nearest_resistance, broken_resistance, lost_support = _latest_levels(df, price)
    bullish_structure, bearish_structure = _structure_flags(df)
    score_meta = _score_direction(
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
    decision, direction, entry_now = _decision_from_scores(long_score, short_score, score_meta["volume_confirms"])

    plan_direction = direction if decision in ("LONG", "SHORT", "WAIT") and direction != "NEUTRAL" else "NEUTRAL"
    trade_plan = _trade_plan(plan_direction, price, atr, nearest_support, nearest_resistance)
    leverage = _leverage_fields(trade_plan.get("risk_pct_to_stop"), row.get("atr_pct"))
    confidence = int(max(long_score, short_score) * 10)

    if decision == "LONG":
        if entry_now:
            main_reason = "Setup futures LONG con score dominante y volumen confirmado."
            action_summary = "LONG técnico con entrada posible ahora si se respeta el stop."
        else:
            main_reason = "Setup futures LONG por score, pero falta confirmación de volumen para entrada inmediata."
            action_summary = "Sesgo LONG; esperar confirmación antes de entrar."
    elif decision == "SHORT":
        if entry_now:
            main_reason = "Setup futures SHORT con score dominante y volumen confirmado."
            action_summary = "SHORT técnico con entrada posible ahora si se respeta el stop."
        else:
            main_reason = "Setup futures SHORT por score, pero falta confirmación de volumen para entrada inmediata."
            action_summary = "Sesgo SHORT; esperar confirmación antes de entrar."
    elif decision == "WAIT":
        main_reason = "Hay sesgo técnico, pero falta confirmación suficiente para entrada futures inmediata."
        action_summary = "Esperar confirmación de volumen/ruptura antes de operar futures."
    else:
        main_reason = "No hay ventaja técnica futures clara."
        action_summary = "Evitar operación futures hasta que aparezca dirección clara."

    reasons = score_meta["long_reasons"] if direction == "LONG" else score_meta["short_reasons"] if direction == "SHORT" else []
    warnings = list(score_meta["penalties"])
    warnings.append(LEVERAGE_WARNING)

    return {
        "mode": "FUTURES",
        "symbol": symbol,
        "timeframe": timeframe,
        "recommended_timeframe": timeframe,
        "decision": decision,
        "direction": direction,
        "entry_now": bool(entry_now),
        **trade_plan,
        "long_score": long_score,
        "short_score": short_score,
        "confidence": confidence,
        "main_reason": main_reason,
        "action_summary": action_summary,
        "missing_conditions": score_meta["missing_conditions"],
        "warnings": warnings,
        **leverage,
        "price": _round_value(price),
        "rsi": round(_safe_float(row.get("rsi")), 2),
        "ema20": _round_value(row.get("ema20")),
        "ema50": _round_value(row.get("ema50")),
        "ema200": _round_value(row.get("ema200")),
        "macd": _round_value(row.get("macd")),
        "macd_signal": _round_value(row.get("macd_signal")),
        "atr": _round_value(row.get("atr")),
        "atr_pct": round(_safe_float(row.get("atr_pct")), 3),
        "bb_upper": _round_value(row.get("bb_upper")),
        "bb_mid": _round_value(row.get("bb_mid")),
        "bb_lower": _round_value(row.get("bb_lower")),
        "vol_ratio": round(_safe_float(row.get("vol_ratio")), 3),
        "volume_confirms": score_meta["volume_confirms"],
        "nearest_support": _round_value(nearest_support),
        "nearest_resistance": _round_value(nearest_resistance),
        "broken_resistance": _round_value(broken_resistance),
        "lost_support": _round_value(lost_support),
        "data_source_exchange": source_meta.get("data_source_exchange"),
        "exchange_mode": source_meta.get("exchange_mode") or exchange_mode,
        "fallback_used": source_meta.get("fallback_used", False),
        "data_source_error": source_meta.get("data_source_error"),
        "no_clear_setup": decision in ("WAIT", "AVOID"),
        "reasons": reasons,
    }


def _auto_rank(result: dict) -> tuple:
    decision_priority = 0 if result.get("decision") in ("LONG", "SHORT") else 1
    best_score = max(_safe_float(result.get("long_score")), _safe_float(result.get("short_score")))
    score_diff = abs(_safe_float(result.get("long_score")) - _safe_float(result.get("short_score")))
    confidence = _safe_float(result.get("confidence"))
    rr = _safe_float(result.get("rr_ratio"))
    tf_pref = {"1h": 0, "2h": 0, "4h": 0, "30m": 1, "15m": 2}.get(result.get("timeframe"), 3)
    return (decision_priority, -best_score, -score_diff, -confidence, -rr, tf_pref)


def analyze_futures_symbol_auto(
    symbol: str,
    timeframes: list[str] | None = None,
    exchange_id: str | None = None,
    exchange_mode: str = "manual",
    ohlcv_limit: int | None = None,
    data_cache: dict | None = None,
) -> dict:
    selected_timeframes = list(timeframes or FUTURES_TIMEFRAMES)
    cache = data_cache if data_cache is not None else {}
    timeframe_results = {}
    for timeframe in selected_timeframes:
        if timeframe not in FUTURES_TIMEFRAMES:
            continue
        timeframe_results[timeframe] = analyze_futures_symbol_timeframe(
            symbol,
            timeframe,
            exchange_id=exchange_id,
            exchange_mode=exchange_mode,
            ohlcv_limit=ohlcv_limit,
            data_cache=cache,
        )

    clear_candidates = []
    for result in timeframe_results.values():
        if result.get("decision") not in ("LONG", "SHORT"):
            continue
        best_score = max(result.get("long_score", 0), result.get("short_score", 0))
        score_diff = abs(result.get("long_score", 0) - result.get("short_score", 0))
        if result.get("timeframe") == "15m" and not (
            best_score >= 8 and result.get("volume_confirms") and score_diff >= 3
        ):
            continue
        clear_candidates.append(result)

    if not clear_candidates:
        data_error = None
        source_exchange = None
        fallback_used = False
        for result in timeframe_results.values():
            data_error = data_error or result.get("data_source_error")
            source_exchange = source_exchange or result.get("data_source_exchange")
            fallback_used = fallback_used or bool(result.get("fallback_used"))
        all_data_unavailable = bool(timeframe_results) and all(
            result.get("decision") == "DATA_UNAVAILABLE"
            for result in timeframe_results.values()
        )
        if all_data_unavailable:
            return {
                "mode": "FUTURES",
                "symbol": data_provider.normalize_symbol(symbol),
                "timeframe": None,
                "recommended_timeframe": None,
                "decision": "DATA_UNAVAILABLE",
                "status": "DATA_UNAVAILABLE",
                "direction": "NEUTRAL",
                "entry_now": False,
                "entry_price": None,
                "stop_loss": None,
                "take_profit_1": None,
                "take_profit_2": None,
                "rr_ratio": None,
                "risk_pct_to_stop": None,
                "long_score": 0,
                "short_score": 0,
                "confidence": 0,
                "main_reason": "No se pudieron obtener datos de mercado para futures.",
                "action_summary": "No tomaría decisión futures sin datos disponibles.",
                "missing_conditions": ["obtener datos OHLCV desde un exchange disponible"],
                "warnings": [data_error or "DATA_UNAVAILABLE", LEVERAGE_WARNING],
                "invalidation": "No aplica: sin datos",
                "suggested_leverage_label": "N/A",
                "suggested_leverage_max": None,
                "leverage_warning": LEVERAGE_WARNING,
                "data_source_exchange": source_exchange or exchange_id,
                "exchange_mode": exchange_mode,
                "fallback_used": fallback_used,
                "data_source_error": data_error,
                "timeframe_results": timeframe_results,
                "no_clear_setup": True,
            }
        return {
            "mode": "FUTURES",
            "symbol": data_provider.normalize_symbol(symbol),
            "timeframe": None,
            "recommended_timeframe": None,
            "decision": "AVOID",
            "direction": "NEUTRAL",
            "entry_now": False,
            "entry_price": None,
            "stop_loss": None,
            "take_profit_1": None,
            "take_profit_2": None,
            "rr_ratio": None,
            "risk_pct_to_stop": None,
            "long_score": 0,
            "short_score": 0,
            "confidence": 0,
            "main_reason": "No hay temporalidad futures con setup LONG/SHORT claro.",
            "action_summary": "Evitar futures hasta que una temporalidad confirme dirección y volumen.",
            "missing_conditions": ["setup claro LONG o SHORT", "volumen confirmado", "diferencia suficiente entre scores"],
            "warnings": [LEVERAGE_WARNING],
            "invalidation": "No aplica: sin setup recomendado",
            "suggested_leverage_label": "N/A",
            "suggested_leverage_max": None,
            "leverage_warning": LEVERAGE_WARNING,
            "data_source_exchange": source_exchange,
            "exchange_mode": exchange_mode,
            "fallback_used": fallback_used,
            "data_source_error": data_error,
            "timeframe_results": timeframe_results,
            "no_clear_setup": True,
        }

    best = sorted(clear_candidates, key=_auto_rank)[0]
    auto_result = dict(best)
    auto_result["timeframe_results"] = timeframe_results
    auto_result["recommended_timeframe"] = best.get("timeframe")
    auto_result["best_setup"] = best
    auto_result["no_clear_setup"] = False
    return auto_result
