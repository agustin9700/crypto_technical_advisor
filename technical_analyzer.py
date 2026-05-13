import pandas as pd
import numpy as np
from datetime import datetime, timezone

import config
import data_provider
import indicators
import support_resistance as sr_module
import utils


BACKTEST_NO_CONFIRM_WARNING = "Backtest no confirma la entrada en este timeframe."
VOLUME_CONFIRMATION_THRESHOLD = 1.2
VOLUME_VERY_LOW_THRESHOLD = 0.8


def _fmt_volume_ratio(vol_ratio) -> str:
    if pd.notna(vol_ratio):
        return f"{vol_ratio:.2f}x"
    return "N/A"


def _volume_confirmation_text(vol_ratio) -> str:
    vol_text = _fmt_volume_ratio(vol_ratio)
    min_text = f"{VOLUME_CONFIRMATION_THRESHOLD:.2f}x"

    if pd.isna(vol_ratio):
        return f"Volumen insuficiente para confirmar: {vol_text} / {min_text}"
    if vol_ratio < VOLUME_VERY_LOW_THRESHOLD:
        return f"Volumen muy bajo: {vol_text} / {min_text}"
    if vol_ratio < VOLUME_CONFIRMATION_THRESHOLD:
        return f"Volumen insuficiente para confirmar: {vol_text} / {min_text}"
    return f"Volumen confirma: {vol_text} / {min_text}"


# ─── Scoring ────────────────────────────────────────────────────────────────

def _compute_score(row: pd.Series, prev_row: pd.Series = None) -> tuple:
    """Return (score, score_max, reasons, missing, warnings)."""
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

    # +2 precio > EMA200
    if price > ema200:
        score += 2
        reasons.append("Precio sobre EMA200 (+2)")
    else:
        missing.append("Precio bajo EMA200")

    # +1 EMA20 > EMA50
    if ema20 > ema50:
        score += 1
        reasons.append("EMA20 > EMA50 (+1)")
    else:
        missing.append("EMA20 no supera EMA50")

    # +1 precio > EMA50
    if price > ema50:
        score += 1
        reasons.append("Precio sobre EMA50 (+1)")
    else:
        missing.append("Precio bajo EMA50")

    # +2 RSI entre 50 y 70
    if 50 <= rsi_val <= 70:
        score += 2
        reasons.append(f"RSI {rsi_val:.1f} en zona alcista 50-70 (+2)")
    elif 45 <= rsi_val < 50:
        # +1 si está subiendo
        if prev_row is not None and rsi_val > prev_row["rsi"]:
            score += 1
            reasons.append(f"RSI {rsi_val:.1f} subiendo hacia 50 (+1)")
        else:
            missing.append(f"RSI {rsi_val:.1f} cerca de 50 pero sin confirmar subida")
    else:
        missing.append(f"RSI {rsi_val:.1f} fuera de zona ideal (50-70)")

    # +1 MACD > signal
    if macd_val > macd_sig:
        score += 1
        reasons.append("MACD sobre signal (+1)")
    else:
        missing.append("MACD bajo signal")

    # +1 vol_ratio >= 1.2
    if pd.notna(vol_ratio) and vol_ratio >= VOLUME_CONFIRMATION_THRESHOLD:
        score += 1
        reasons.append(f"{_volume_confirmation_text(vol_ratio)} (+1)")
    else:
        missing.append(_volume_confirmation_text(vol_ratio))

    # Penalizaciones
    if pd.notna(vol_ratio) and vol_ratio < VOLUME_VERY_LOW_THRESHOLD:
        score -= 1
        warnings.append(f"{_volume_confirmation_text(vol_ratio)} (-1)")

    if rsi_val < 40:
        score -= 2
        warnings.append(f"RSI muy bajo: {rsi_val:.1f} (-2)")

    if price < ema200 and rsi_val < 50:
        score -= 2
        warnings.append("Precio bajo EMA200 con RSI < 50 (-2)")

    score = max(0, min(score, score_max))
    return score, score_max, reasons, missing, warnings


def _compute_rr(price: float, atr_val: float) -> tuple:
    entry = price
    sl = entry - config.ATR_SL_MULT * atr_val
    tp = entry + config.ATR_TP_MULT * atr_val

    risk_pct = (entry - sl) / entry * 100
    reward_pct = (tp - entry) / entry * 100
    rr_ratio = reward_pct / risk_pct if risk_pct > 0 else 0

    return entry, sl, tp, risk_pct, reward_pct, rr_ratio


def _decide(score: int, regime_ok: bool, rr_ratio: float,
            dist_to_resistance_pct: float, vol_ratio: float,
            rsi_val: float) -> str:
    near_resistance = dist_to_resistance_pct is not None and 0 < dist_to_resistance_pct < 1.5

    if (score >= 7 and regime_ok and rr_ratio >= config.MIN_RR_RATIO
            and not near_resistance and (pd.isna(vol_ratio) or vol_ratio >= VOLUME_VERY_LOW_THRESHOLD)):
        return "ENTER_NOW_CANDIDATE"

    if score < 5 or not regime_ok or rsi_val < 40:
        return "AVOID"

    if near_resistance and rr_ratio < config.MIN_RR_RATIO:
        return "AVOID"

    return "WAIT"


# ─── Main analyzer ──────────────────────────────────────────────────────────

ACTION_PLAN_FIELDS = (
    "action_summary",
    "entry_now_text",
    "entry_trigger",
    "invalidation_level",
    "main_reason",
    "what_needs_to_happen",
    "human_verdict",
)

PRIMARY_AUTO_TIMEFRAMES = ["1h", "2h", "4h"]
SECONDARY_AUTO_TIMEFRAMES = ["30m", "1d"]
MICRO_TIMEFRAMES = ["15m"]
NO_CLEAR_SETUP = "NO_CLEAR_SETUP"

TIMEFRAME_SECONDS = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "1d": 86400,
}


def _fmt_level(value) -> str:
    return utils.format_price(value)


def _round_market_value(value):
    if value is None:
        return None
    value = float(value)
    abs_value = abs(value)
    if abs_value < 0.0001:
        return round(value, 12)
    if abs_value < 0.01:
        return round(value, 8)
    if abs_value < 1:
        return round(value, 6)
    return round(value, 6)


def _display_timeframe(timeframe: str) -> str:
    if not timeframe:
        return "?"
    if timeframe.endswith(("h", "d")):
        return timeframe.upper()
    return timeframe


def _is_near_resistance(result: dict) -> bool:
    dist = result.get("distance_to_resistance_pct")
    return dist is not None and 0 < dist < 1.5


def _is_incomplete_candle(row: pd.Series, timeframe: str) -> bool:
    seconds = TIMEFRAME_SECONDS.get(timeframe)
    if not seconds or "datetime" not in row:
        return False

    candle_time = row["datetime"]
    if pd.isna(candle_time):
        return False
    if getattr(candle_time, "tzinfo", None) is None:
        candle_time = candle_time.tz_localize("UTC")

    candle_close = candle_time + pd.Timedelta(seconds=seconds)
    now = pd.Timestamp.now(tz="UTC")
    return now < candle_close


def _adjust_intracandle_volume(row: pd.Series, timeframe: str):
    seconds = TIMEFRAME_SECONDS.get(timeframe)
    raw_ratio = row.get("vol_ratio")
    if not seconds or pd.isna(raw_ratio) or "datetime" not in row:
        return round(float(raw_ratio), 3) if pd.notna(raw_ratio) else None

    candle_time = row["datetime"]
    if pd.isna(candle_time):
        return round(float(raw_ratio), 3)
    if getattr(candle_time, "tzinfo", None) is None:
        candle_time = candle_time.tz_localize("UTC")

    elapsed = (pd.Timestamp.now(tz="UTC") - candle_time).total_seconds()
    progress = max(min(elapsed / seconds, 1.0), 0.05)
    return round(float(raw_ratio) / progress, 3)


def _get_volume_for_scoring(row: pd.Series, prev_row: pd.Series, timeframe: str,
                            use_intracandle: bool) -> dict:
    raw_intracandle_ratio = row.get("vol_ratio")
    closed_ratio = row.get("vol_ratio")
    volume_warning = None
    incomplete = bool(use_intracandle and _is_incomplete_candle(row, timeframe))

    if incomplete:
        closed_ratio = prev_row.get("vol_ratio")
        volume_warning = "Volumen intravela incompleto; scoring usa volumen de la última vela cerrada"

    scoring_ratio = closed_ratio
    return {
        "scoring_vol_ratio": scoring_ratio,
        "closed_candle_vol_ratio": round(float(closed_ratio), 3) if pd.notna(closed_ratio) else None,
        "intracandle_vol_ratio": round(float(raw_intracandle_ratio), 3) if pd.notna(raw_intracandle_ratio) else None,
        "adjusted_intracandle_vol_ratio": (
            _adjust_intracandle_volume(row, timeframe) if incomplete else None
        ),
        "incomplete_candle_volume": incomplete,
        "volume_warning": volume_warning,
    }


def _main_reason(result: dict) -> str:
    decision = result.get("decision")
    if decision == "DATA_UNAVAILABLE":
        return "No se pudieron obtener datos desde los exchanges configurados."
    if result.get("no_clear_setup"):
        return "No hay temporalidad con setup claro ahora"
    if result.get("backtest_verdict") == "BACKTEST_BAD":
        return BACKTEST_NO_CONFIRM_WARNING
    if decision == "NO_DATA":
        return result.get("error") or "No hay datos suficientes"

    score = result.get("score", 0) or 0
    rr = result.get("rr_ratio", 0) or 0
    vol_ratio = result.get("closed_candle_vol_ratio", result.get("vol_ratio"))
    close_above_ema200 = result.get("close_above_ema200")

    if vol_ratio is not None and vol_ratio < VOLUME_VERY_LOW_THRESHOLD:
        return _volume_confirmation_text(vol_ratio)
    if close_above_ema200 is False:
        return "Precio bajo EMA200"
    if _is_near_resistance(result):
        return "Cerca de resistencia"
    if rr < config.MIN_RR_RATIO:
        return "RR menor a 1.5"
    if score < 7:
        return "Setup alcista incompleto"
    if result.get("no_clear_setup"):
        return "No entraría ahora en ningún timeframe principal."
    if decision == "ENTER_NOW_CANDIDATE":
        return "Setup alcista confirmado"
    return "Setup alcista incompleto"


def _what_needs_to_happen(result: dict) -> list:
    if result.get("decision") == "DATA_UNAVAILABLE":
        return ["obtener datos desde un exchange disponible"]
    if result.get("no_clear_setup"):
        return [
            "aparecer setup claro en 1h, 2h o 4h",
            "score >= 7",
            "volumen confirma >= 1.20x",
            "régimen sobre EMA200 con RSI >= 50",
        ]
    if result.get("decision") == "NO_DATA":
        return ["obtener datos suficientes"]

    needs = []
    if result.get("backtest_verdict") in ("BACKTEST_WEAK", "BACKTEST_BAD"):
        needs.append("backtest del timeframe recomendado debe confirmar mejor")
    score = result.get("score", 0) or 0
    rsi_val = result.get("rsi")
    rr = result.get("rr_ratio", 0) or 0
    vol_ratio = result.get("closed_candle_vol_ratio", result.get("vol_ratio"))

    if score < 7:
        needs.append("score >= 7")
    if vol_ratio is None or vol_ratio < VOLUME_CONFIRMATION_THRESHOLD:
        needs.append("volumen confirma >= 1.20x")
    if rsi_val is None or rsi_val < 50:
        needs.append("mantener RSI >= 50")
    if result.get("close_above_ema200") is False:
        needs.append("cerrar sobre EMA200")
    if _is_near_resistance(result):
        needs.append("romper resistencia cercana")
    if rr < config.MIN_RR_RATIO:
        needs.append(f"RR >= {config.MIN_RR_RATIO}")

    return needs


def _entry_now_text(result: dict) -> str:
    if result.get("decision") == "DATA_UNAVAILABLE":
        return "Entrada ahora: no recomendable"
    if result.get("no_clear_setup"):
        return "Entrada ahora: no recomendable"

    decision = result.get("decision")
    if (
        decision == "WAIT"
        and result.get("backtest_verdict") in ("BACKTEST_WEAK", "BACKTEST_BAD")
    ):
        return "Entrada ahora: no recomendable; esperar gatillo confirmado."

    score = result.get("score", 0) or 0
    rr = result.get("rr_ratio", 0) or 0
    vol_ratio = result.get("closed_candle_vol_ratio", result.get("vol_ratio"))
    regime_ok = bool(result.get("regime_filter_passed"))
    volume_ok = vol_ratio is None or vol_ratio >= VOLUME_VERY_LOW_THRESHOLD

    if decision == "ENTER_NOW_CANDIDATE":
        return "Entrada ahora: recomendable"
    if (
        decision == "WAIT"
        and score >= 6
        and regime_ok
        and rr >= config.MIN_RR_RATIO
        and volume_ok
        and not _is_near_resistance(result)
    ):
        return "Entrada ahora: posible, pero agresiva"
    return "Entrada ahora: no recomendable"


def _entry_trigger(result: dict) -> str:
    if result.get("decision") == "DATA_UNAVAILABLE":
        return "No se pudieron obtener datos desde los exchanges configurados."
    if result.get("no_clear_setup"):
        return "Esperar setup claro en 1h, 2h o 4h"
    if result.get("decision") == "NO_DATA":
        return "Esperar datos suficientes para validar el setup"

    ema200 = result.get("ema200")
    resistance = result.get("nearest_resistance")
    score = result.get("score", 0) or 0
    vol_ratio = result.get("closed_candle_vol_ratio", result.get("vol_ratio"))

    if result.get("close_above_ema200") is False:
        return f"Cerrar sobre EMA200 ({_fmt_level(ema200)}) con RSI >= 50"
    if resistance is not None and (_is_near_resistance(result) or score < 7):
        return f"Romper resistencia {_fmt_level(resistance)} con volumen confirma >= 1.20x"
    if resistance is None and score < 7:
        return "Esperar continuación con volumen y cierre sobre zona actual"
    if score < 7:
        return "Esperar score >= 7/10"
    if vol_ratio is None or vol_ratio < VOLUME_CONFIRMATION_THRESHOLD:
        return "Esperar volumen confirma >= 1.20x"
    return "Mantener score >= 7/10, RR >= 1.5 y volumen confirma >= 1.20x"


def _invalidation_level(result: dict) -> str:
    if result.get("no_clear_setup"):
        return "No aplica: no hay setup recomendado"
    if result.get("decision") in ("NO_DATA", "DATA_UNAVAILABLE"):
        return "N/A"

    support = result.get("nearest_support")
    if support is None:
        return "Rompe bajo EMA200 o stop técnico por ATR"
    return f"Pierde {_fmt_level(support)} o rompe bajo EMA200"


def _action_summary(result: dict, timeframe: str) -> str:
    decision = result.get("decision")
    tf = _display_timeframe(timeframe)

    if decision == "DATA_UNAVAILABLE":
        return f"DATA_UNAVAILABLE en {tf}. No entrar ahora."
    if result.get("no_clear_setup"):
        return "SIN SETUP claro en timeframes principales. No entrar ahora."
    if decision == "ENTER_NOW_CANDIDATE":
        return f"ENTRADA candidata en {tf}. Validar riesgo antes de entrar."
    if decision == "WAIT":
        return f"ESPERAR confirmación en {tf}. No entrar ahora."
    if decision == "AVOID":
        return f"EVITAR en {tf}. No entrar ahora."
    return f"SIN DATOS suficientes en {tf}. No entrar ahora."


def _human_verdict(result: dict) -> str:
    decision = result.get("decision")
    entry_text = result.get("entry_now_text", "")
    if decision == "DATA_UNAVAILABLE":
        return "No tomaría decisión sin datos de mercado disponibles."
    if result.get("no_clear_setup"):
        return "No entraría ahora en ningún timeframe principal."

    if decision == "ENTER_NOW_CANDIDATE":
        return "Entraría ahora solo respetando stop y tamaño de posición."
    if (
        decision == "WAIT"
        and result.get("backtest_verdict") in ("BACKTEST_WEAK", "BACKTEST_BAD")
    ):
        return "No entraría ahora. Esperaría ruptura/confirmación con volumen."
    if "posible, pero agresiva" in entry_text:
        return "No entraría ahora salvo entrada agresiva con gatillo confirmado."
    if decision == "WAIT":
        return "No entraría ahora. Esperaría confirmación."
    if decision == "AVOID":
        return "No entraría ahora. Evitaría el setup hasta que mejore la estructura."
    return "No tomaría decisión sin datos suficientes."


def _add_action_plan(result: dict, timeframe: str = None) -> dict:
    result = dict(result)
    tf = timeframe or result.get("recommended_timeframe") or result.get("timeframe")

    result["entry_now_text"] = _entry_now_text(result)
    result["entry_trigger"] = _entry_trigger(result)
    result["invalidation_level"] = _invalidation_level(result)
    result["main_reason"] = _main_reason(result)
    result["what_needs_to_happen"] = _what_needs_to_happen(result)
    result["action_summary"] = _action_summary(result, tf)
    result["human_verdict"] = _human_verdict(result)
    return result


def _volume_regime_not_bad(result: dict) -> bool:
    vol_ratio = result.get("closed_candle_vol_ratio", result.get("vol_ratio"))
    volume_ok = vol_ratio is None or vol_ratio >= VOLUME_VERY_LOW_THRESHOLD
    return bool(result.get("regime_filter_passed")) and volume_ok


def _auto_candidate_rank(item: tuple) -> tuple:
    tf, result = item
    decision_rank = {
        "ENTER_NOW_CANDIDATE": 2,
        "WAIT": 1,
        "AVOID": 0,
        "NO_DATA": -1,
        "DATA_UNAVAILABLE": -2,
    }.get(result.get("decision"), 0)
    preferred_rank = {
        "1h": 3,
        "2h": 3,
        "4h": 3,
        "30m": 2,
        "1d": 1,
        "15m": 0,
    }.get(tf, 0)
    return (
        decision_rank,
        result.get("score", 0) or 0,
        preferred_rank,
        result.get("confidence", 0) or 0,
        result.get("rr_ratio", 0) or 0,
    )


def _is_auto_candidate_acceptable(result: dict) -> bool:
    return (
        result.get("decision") in ("ENTER_NOW_CANDIDATE", "WAIT")
        and (result.get("score", 0) or 0) >= 5
        and result.get("decision") != "NO_DATA"
    )


def _is_15m_candidate_recommendable(result: dict, backtest: dict = None) -> bool:
    if backtest and backtest.get("verdict") == "BACKTEST_BAD":
        return False
    return (
        result.get("decision") == "ENTER_NOW_CANDIDATE"
        and (result.get("score", 0) or 0) >= 8
        and _volume_regime_not_bad(result)
    )


def _best_observation(timeframe_results: dict):
    valid = [
        (tf, result)
        for tf, result in timeframe_results.items()
        if result.get("decision") not in ("NO_DATA", "DATA_UNAVAILABLE")
    ]
    if not valid:
        return None, None
    return max(valid, key=_auto_candidate_rank)


def _observation_summary(timeframe_results: dict) -> str:
    rows = []
    for tf in PRIMARY_AUTO_TIMEFRAMES + MICRO_TIMEFRAMES:
        result = timeframe_results.get(tf)
        if result and result.get("decision") not in ("NO_DATA", "DATA_UNAVAILABLE"):
            rows.append(f"{tf} {result.get('decision')} {result.get('score', 0)}/10")
    return " / ".join(rows) if rows else "sin datos suficientes"


def _pick_auto_timeframe(timeframe_results: dict):
    warnings = []
    primary = [
        (tf, timeframe_results.get(tf, {}))
        for tf in PRIMARY_AUTO_TIMEFRAMES
        if _is_auto_candidate_acceptable(timeframe_results.get(tf, {}))
    ]
    if primary:
        return max(primary, key=_auto_candidate_rank), warnings

    secondary = [
        (tf, timeframe_results.get(tf, {}))
        for tf in SECONDARY_AUTO_TIMEFRAMES
        if _is_auto_candidate_acceptable(timeframe_results.get(tf, {}))
    ]
    if secondary:
        return max(secondary, key=_auto_candidate_rank), warnings

    fifteen = timeframe_results.get("15m", {})
    if _is_15m_candidate_recommendable(fifteen):
        return ("15m", fifteen), warnings

    best_tf, best = _best_observation(timeframe_results)
    if best_tf == "15m" and best:
        warnings.append(
            "15m tuvo el mejor score, pero no cumple condiciones para recomendación principal"
        )
    return (None, best), warnings


def _build_no_clear_auto_result(symbol: str, timeframe_results: dict, warnings: list) -> dict:
    best_tf, best = _best_observation(timeframe_results)
    any_data_unavailable = any(
        result.get("decision") == "DATA_UNAVAILABLE"
        for result in (timeframe_results or {}).values()
    )
    final_decision = (
        "DATA_UNAVAILABLE"
        if any_data_unavailable and not best
        else "WAIT"
        if best and best.get("decision") in ("WAIT", "ENTER_NOW_CANDIDATE")
        else "AVOID"
    )
    best_setup = dict(best or {})
    if best_setup:
        best_setup = _add_action_plan(best_setup, best_tf)

    result = {
        "symbol": symbol,
        "recommended_timeframe": None,
        "decision": final_decision,
        "analysis_time": (
            best_setup.get("analysis_time")
            if best_setup
            else datetime.now(timezone.utc).isoformat()
        ),
        "summary": "No hay temporalidad con setup claro ahora",
        "timeframe_results": timeframe_results,
        "best_setup": best_setup,
        "warnings": warnings,
        "no_clear_setup": True,
        "auto_observation": f"Mejor observación: {_observation_summary(timeframe_results)}",
        **_source_meta_from_results(timeframe_results),
    }
    return _add_action_plan(result, None)


def apply_backtest_to_analysis(analysis: dict, backtest: dict = None) -> dict:
    if not backtest:
        return analysis

    result = dict(analysis or {})
    verdict = backtest.get("verdict")
    if verdict not in ("BACKTEST_BAD", "BACKTEST_WEAK"):
        return result

    warnings = list(result.get("warnings", []))
    warning = BACKTEST_NO_CONFIRM_WARNING
    if warning not in warnings:
        warnings.append(warning)
    result["warnings"] = warnings
    result["backtest_verdict"] = verdict

    best = dict(result.get("best_setup") or result)
    best["backtest_verdict"] = verdict
    best_warnings = list(best.get("warnings", []))
    if warning not in best_warnings:
        best_warnings.append(warning)
    best["warnings"] = best_warnings

    if verdict == "BACKTEST_BAD":
        if result.get("decision") == "ENTER_NOW_CANDIDATE":
            result["decision"] = "WAIT"
        if best.get("decision") == "ENTER_NOW_CANDIDATE":
            best["decision"] = "WAIT"
        result["entry_now_text"] = "Entrada ahora: no recomendable; esperar gatillo confirmado."
        best["entry_now_text"] = "Entrada ahora: no recomendable; esperar gatillo confirmado."
        result["main_reason"] = BACKTEST_NO_CONFIRM_WARNING
        best["main_reason"] = BACKTEST_NO_CONFIRM_WARNING

        if result.get("recommended_timeframe") == "15m" and "timeframe_results" in result:
            result["no_clear_setup"] = True
            result["recommended_timeframe"] = None
            result["summary"] = "No hay temporalidad con setup claro ahora"
            result["auto_observation"] = (
                "Mejor score en 15m, pero backtest malo; queda como observación"
            )

    best = _add_action_plan(best, best.get("timeframe"))
    result["best_setup"] = best
    for field in ACTION_PLAN_FIELDS:
        result[field] = best.get(field)
    if result.get("no_clear_setup"):
        result = _add_action_plan(result, None)
    return result


def _fetch_ohlcv_cached(
    symbol: str,
    timeframe: str,
    days: int = 400,
    ohlcv_limit: int = None,
    data_cache: dict = None,
) -> pd.DataFrame:
    symbol = data_provider.normalize_symbol(symbol)
    cache_limit = ohlcv_limit if ohlcv_limit is not None else f"days:{days}"
    cache_key = (symbol, timeframe, cache_limit)

    if data_cache is not None and cache_key in data_cache:
        return data_cache[cache_key].copy()

    df = data_provider.fetch_ohlcv_with_fallback(
        symbol,
        timeframe,
        days=days,
        ohlcv_limit=ohlcv_limit,
    )
    if data_cache is not None:
        data_cache[cache_key] = df.copy()
    return df


def _source_meta_from_df(df: pd.DataFrame) -> dict:
    attrs = getattr(df, "attrs", {}) or {}
    return {
        "data_source_exchange": attrs.get("exchange_id"),
        "data_source_status": attrs.get("data_source_status"),
        "data_source_error": attrs.get("data_source_error"),
    }


def _source_meta_from_results(timeframe_results: dict) -> dict:
    for result in (timeframe_results or {}).values():
        if result.get("data_source_exchange"):
            return {
                "data_source_exchange": result.get("data_source_exchange"),
                "data_source_status": result.get("data_source_status"),
                "data_source_error": result.get("data_source_error"),
            }
    return {
        "data_source_exchange": None,
        "data_source_status": None,
        "data_source_error": None,
    }


def analyze_symbol_timeframe(symbol: str, timeframe: str,
                             use_intracandle: bool = True,
                             df_daily: pd.DataFrame = None,
                             ohlcv_limit: int = None,
                             data_cache: dict = None) -> dict:
    symbol = data_provider.normalize_symbol(symbol)

    try:
        df_raw = _fetch_ohlcv_cached(
            symbol,
            timeframe,
            days=400,
            ohlcv_limit=ohlcv_limit,
            data_cache=data_cache,
        )
    except Exception as e:
        error_text = str(e)
        decision = "DATA_UNAVAILABLE" if data_provider.DATA_UNAVAILABLE in error_text else "NO_DATA"
        return _add_action_plan({
            "symbol": symbol,
            "timeframe": timeframe,
            "signal": "NO_DATA",
            "decision": decision,
            "error": error_text,
            "data_source_exchange": None,
            "data_source_status": "DATA_UNAVAILABLE" if decision == "DATA_UNAVAILABLE" else None,
            "data_source_error": error_text,
        }, timeframe)

    source_meta = _source_meta_from_df(df_raw)
    if df_raw is None or len(df_raw) < 210:
        return _add_action_plan({
            "symbol": symbol,
            "timeframe": timeframe,
            "signal": "NO_DATA",
            "decision": "NO_DATA",
            "error": "Not enough candles",
            **source_meta,
        }, timeframe)

    df = indicators.add_indicators(df_raw)
    df = df.dropna(subset=["ema200", "rsi", "atr"]).reset_index(drop=True)

    if len(df) < 2:
        return _add_action_plan({
            "symbol": symbol,
            "timeframe": timeframe,
            "signal": "NO_DATA",
            "decision": "NO_DATA",
            "error": "Not enough data after indicators",
            **source_meta,
        }, timeframe)

    # Use last closed candle (index -1 is current forming candle if live)
    if use_intracandle:
        row = df.iloc[-1]
        prev_row = df.iloc[-2]
    else:
        row = df.iloc[-2]
        prev_row = df.iloc[-3] if len(df) >= 3 else df.iloc[-2]

    volume_meta = _get_volume_for_scoring(row, prev_row, timeframe, use_intracandle)
    scoring_row = row.copy()
    scoring_row["vol_ratio"] = volume_meta["scoring_vol_ratio"]

    price = row["close"]
    rsi_val = row["rsi"]
    ema200_val = row["ema200"]
    atr_val = row["atr"]
    vol_ratio = volume_meta["scoring_vol_ratio"]

    # Support / resistance
    supports, resistances = sr_module.find_support_resistance(df, lookback=120)
    nearest_sup = sr_module.nearest_support_below(price, supports)
    nearest_res = sr_module.nearest_resistance_above(price, resistances)

    if nearest_sup is not None and nearest_sup >= price:
        nearest_sup = None
    if nearest_res is not None and nearest_res <= price:
        nearest_res = None

    dist_sup = sr_module.distance_pct(price, nearest_sup)
    dist_res = sr_module.distance_pct(price, nearest_res)

    # Score
    score, score_max, reasons, missing, warnings = _compute_score(scoring_row, prev_row)
    if volume_meta["volume_warning"]:
        warnings.append(volume_meta["volume_warning"])

    if nearest_sup is None:
        warnings.append("No hay soporte válido por debajo del precio actual.")
    if nearest_res is None:
        warnings.append("No hay resistencia válida por encima del precio actual.")

    # 1D context bonus / penalty
    daily_favorable = None
    if df_daily is not None and len(df_daily) > 0:
        d = df_daily.iloc[-1]
        if d["close"] > d["ema200"] and d["rsi"] >= 50:
            score = min(score + 1, score_max)
            reasons.append("1D contexto favorable (+1)")
            daily_favorable = True
        elif d["close"] < d["ema200"] and d["rsi"] < 45:
            score = max(score - 1, 0)
            warnings.append("1D contexto bajista (-1)")
            daily_favorable = False

    # Resistance penalty
    if nearest_res is not None and dist_res is not None and 0 < dist_res < 1.5:
        score = max(score - 2, 0)
        warnings.append(f"Precio muy cerca de resistencia {nearest_res:.4f} (-2)")

    score = max(0, min(score, score_max))

    # Regime filter
    regime_ok = price > ema200_val and rsi_val >= 50
    close_above_ema200 = price > ema200_val

    # Confidence
    confidence = round(score / score_max * 100, 1)

    # RR
    entry, sl, tp, risk_pct, reward_pct, rr_ratio = _compute_rr(price, atr_val)

    # Decision
    decision = _decide(score, regime_ok, rr_ratio, dist_res, vol_ratio, rsi_val)

    # Signal (alias)
    signal = decision

    candle_time = row["datetime"].isoformat() if hasattr(row["datetime"], "isoformat") else str(row["datetime"])

    result = {
        "symbol": symbol,
        "timeframe": timeframe,
        "analysis_time": datetime.now(timezone.utc).isoformat(),
        "candle_time": candle_time,
        "price": _round_market_value(price),
        "signal": signal,
        "decision": decision,
        "score": score,
        "score_max": score_max,
        "confidence": confidence,
        "regime_filter_passed": regime_ok,
        "close_above_ema200": close_above_ema200,
        "rsi": round(float(rsi_val), 2),
        "ema20": _round_market_value(row["ema20"]),
        "ema50": _round_market_value(row["ema50"]),
        "ema200": _round_market_value(ema200_val),
        "atr": _round_market_value(atr_val),
        "atr_pct": round(float(row["atr_pct"]), 3),
        "vol_ratio": round(float(vol_ratio), 3) if pd.notna(vol_ratio) else None,
        "closed_candle_vol_ratio": volume_meta["closed_candle_vol_ratio"],
        "intracandle_vol_ratio": volume_meta["intracandle_vol_ratio"],
        "adjusted_intracandle_vol_ratio": volume_meta["adjusted_intracandle_vol_ratio"],
        "incomplete_candle_volume": volume_meta["incomplete_candle_volume"],
        "volume_warning": volume_meta["volume_warning"],
        "macd": round(float(row["macd"]), 6),
        "macd_signal": round(float(row["macd_signal"]), 6),
        "nearest_support": _round_market_value(nearest_sup) if nearest_sup is not None else None,
        "nearest_resistance": _round_market_value(nearest_res) if nearest_res is not None else None,
        "distance_to_support_pct": round(float(dist_sup), 3) if dist_sup is not None else None,
        "distance_to_resistance_pct": round(float(dist_res), 3) if dist_res is not None else None,
        "estimated_entry": _round_market_value(entry),
        "estimated_stop_loss": _round_market_value(sl),
        "estimated_take_profit": _round_market_value(tp),
        "risk_pct": round(float(risk_pct), 3),
        "reward_pct": round(float(reward_pct), 3),
        "rr_ratio": round(float(rr_ratio), 3),
        "reasons": reasons,
        "missing_conditions": missing,
        "warnings": warnings,
        "daily_context_favorable": daily_favorable,
        **source_meta,
    }
    return _add_action_plan(result, timeframe)


# ─── Auto timeframe ──────────────────────────────────────────────────────────

def _normalize_auto_timeframes(timeframes=None) -> list:
    if timeframes is None:
        return list(config.TIMEFRAMES)

    allowed = set(config.TIMEFRAMES)
    cleaned = []
    for timeframe in timeframes:
        tf = str(timeframe).strip()
        if not tf:
            continue
        if tf not in allowed:
            raise ValueError(f"Timeframe invalido para auto analysis: {tf}")
        if tf not in cleaned:
            cleaned.append(tf)

    if not cleaned:
        raise ValueError("Auto analysis requiere al menos un timeframe")
    return cleaned


def analyze_symbol_auto(
    symbol: str,
    timeframes=None,
    ohlcv_limit: int = None,
    data_cache: dict = None,
) -> dict:
    symbol = data_provider.normalize_symbol(symbol)
    selected_timeframes = _normalize_auto_timeframes(timeframes)

    # Fetch daily for context
    df_daily = None
    try:
        df_daily_raw = _fetch_ohlcv_cached(
            symbol,
            "1d",
            days=400,
            ohlcv_limit=ohlcv_limit,
            data_cache=data_cache,
        )
        df_daily = indicators.add_indicators(df_daily_raw)
        df_daily = df_daily.dropna(subset=["ema200", "rsi"]).reset_index(drop=True)
    except Exception:
        df_daily = None

    timeframe_results = {}
    for tf in selected_timeframes:
        result = analyze_symbol_timeframe(symbol, tf, use_intracandle=True,
                                         df_daily=df_daily if tf != "1d" else None,
                                         ohlcv_limit=ohlcv_limit,
                                         data_cache=data_cache)
        timeframe_results[tf] = result

    selected, all_warnings = _pick_auto_timeframe(timeframe_results)
    best_tf, best_setup = selected

    # Multi-TF consensus
    primary_decisions = [timeframe_results.get(tf, {}).get("decision") for tf in ["1h", "4h"]]
    # Override confidence based on consensus
    if best_setup:
        h1 = timeframe_results.get("1h", {})
        h4 = timeframe_results.get("4h", {})
        h1_dec = h1.get("decision")
        h4_dec = h4.get("decision")

        if h1_dec == "ENTER_NOW_CANDIDATE" and h4_dec != "ENTER_NOW_CANDIDATE":
            all_warnings.append("1H señal, pero 4H no confirma todavía")
            if best_setup.get("decision") == "ENTER_NOW_CANDIDATE":
                best_setup = dict(best_setup)
                best_setup["decision"] = "WAIT"
                best_setup["warnings"] = best_setup.get("warnings", []) + ["4H no confirma"]

        d1 = timeframe_results.get("1d", {})
        if d1.get("close_above_ema200") is False and d1.get("rsi", 50) < 45:
            all_warnings.append("1D contexto bajista fuerte: reducir confianza")

    if best_tf is None:
        return _build_no_clear_auto_result(symbol, timeframe_results, all_warnings)

    final_decision = best_setup.get("decision", "NO_DATA") if best_setup else "NO_DATA"
    if best_setup:
        best_setup = dict(best_setup)
        best_setup["decision"] = final_decision
        best_setup = _add_action_plan(best_setup, best_tf)

    summary_lines = []
    if best_setup:
        p = best_setup.get("price", 0)
        rsi_v = best_setup.get("rsi", 0)
        rr = best_setup.get("rr_ratio", 0)
        summary_lines.append(f"Temporalidad recomendada: {best_tf}")
        summary_lines.append(f"Decisión: {final_decision}")
        summary_lines.append(f"Precio: {utils.format_price(p)}")
        summary_lines.append(f"RSI: {rsi_v}")
        summary_lines.append(f"RR: {rr}")

    plan_source = best_setup or _add_action_plan({
        "symbol": symbol,
        "timeframe": best_tf,
        "signal": "NO_DATA",
        "decision": "NO_DATA",
    }, best_tf)

    result = {
        "symbol": symbol,
        "recommended_timeframe": best_tf,
        "decision": final_decision,
        "analysis_time": plan_source.get("analysis_time") or datetime.now(timezone.utc).isoformat(),
        "summary": "\n".join(summary_lines),
        "timeframe_results": timeframe_results,
        "best_setup": best_setup,
        "warnings": all_warnings,
        "no_clear_setup": False,
        "auto_observation": f"Mejor observación: {_observation_summary(timeframe_results)}",
        **_source_meta_from_results(timeframe_results),
    }
    for field in ACTION_PLAN_FIELDS:
        result[field] = plan_source.get(field)

    return result


# ─── CLI entry ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import json

    symbol = sys.argv[1] if len(sys.argv) > 1 else config.DEFAULT_SYMBOL
    timeframe = sys.argv[2] if len(sys.argv) > 2 else "1h"

    print(f"Analyzing {symbol} / {timeframe} ...")
    result = analyze_symbol_timeframe(symbol, timeframe)
    print(json.dumps(result, indent=2, default=str))
