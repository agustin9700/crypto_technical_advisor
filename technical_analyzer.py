import pandas as pd
import numpy as np
from datetime import datetime, timezone

import config
import data_provider
import indicators
import support_resistance as sr_module
import strategy_engine
import utils


BACKTEST_NO_CONFIRM_WARNING = "Backtest no confirma la entrada en este timeframe."
VOLUME_CONFIRMATION_THRESHOLD = 1.2
VOLUME_VERY_LOW_THRESHOLD = 0.8


def _fmt_level(value):
    """Format a price level for display in analysis text."""
    try:
        return utils.format_price(value)
    except Exception:
        try:
            return f"{float(value):.8f}".rstrip("0").rstrip(".")
        except Exception:
            return str(value)


def _volume_confirmation_text(vol_ratio):
    """Format volume confirmation message."""
    return utils.volume_confirmation_text(vol_ratio, VOLUME_CONFIRMATION_THRESHOLD, VOLUME_VERY_LOW_THRESHOLD)



# Compatibility proxies: the public analyzer keeps its shape, while the
# strategy rules live in strategy_engine so backtester/scanner can share them.
def _compute_score(row: pd.Series, prev_row: pd.Series = None, strat: dict = None) -> tuple:
    return strategy_engine.compute_spot_score(row, prev_row, strat=strat)


def _dynamic_sl_tp_mult(atr_pct: float, strat: dict = None) -> tuple[float, float]:
    return strategy_engine.dynamic_sl_tp_mult(atr_pct, strat=strat)


def _compute_rr(price: float, atr_val: float, strat: dict = None) -> tuple:
    return strategy_engine.compute_long_rr(price, atr_val, strat=strat)


def _decide(score: float, regime_ok: bool, rr_ratio: float,
            dist_to_resistance_pct: float, vol_ratio: float,
            rsi_val: float, btc_regime: str = "NEUTRAL",
            warnings: list = None, strat: dict = None) -> str:
    return strategy_engine.decide_spot(
        score,
        regime_ok,
        rr_ratio,
        dist_to_resistance_pct,
        vol_ratio,
        rsi_val,
        btc_regime=btc_regime,
        warnings=warnings,
        strat=strat
    )


# ─── Main analyzer ──────────────────────────────────────────────────────────

def get_btc_regime(exchange_id=None, exchange_mode="manual") -> dict:
    """
    Obtiene el régimen macro actual de BTC en temporalidad 4h.

    Parámetros:
        exchange_id: Exchange a consultar. Si es None, usa el default del provider.
        exchange_mode: Modo de exchange, por ejemplo "manual" o "fallback".

    Retorno:
        dict con regime, precio BTC, EMA200 4h, RSI 4h y si BTC está sobre EMA200.
        En caso de error retorna régimen NEUTRAL con btc_price=None.

    Ejemplo:
        regime = get_btc_regime(exchange_id="kucoin", exchange_mode="manual")
    """
    neutral = {
        "regime": "NEUTRAL",
        "btc_price": None,
        "btc_ema200_4h": None,
        "btc_rsi_4h": None,
        "btc_above_ema200": False,
    }

    try:
        df_raw = data_provider.fetch_ohlcv(
            "BTC/USDT",
            "4h",
            days=60,
            exchange_id=exchange_id,
            exchange_mode=exchange_mode,
            market_type="spot",
        )
        if df_raw is None or len(df_raw) == 0:
            return neutral

        df = indicators.add_indicators(df_raw)
        df = df.dropna(subset=["ema200", "rsi"]).reset_index(drop=True)
        if df.empty:
            return neutral

        row = df.iloc[-1]
        btc_price = float(row["close"])
        btc_ema200_4h = float(row["ema200"])
        btc_rsi_4h = float(row["rsi"])
        btc_above_ema200 = btc_price > btc_ema200_4h

        if btc_above_ema200 and btc_rsi_4h >= 50:
            regime = "BULL"
        elif btc_price < btc_ema200_4h and btc_rsi_4h < 50:
            regime = "BEAR"
        else:
            regime = "NEUTRAL"

        return {
            "regime": regime,
            "btc_price": btc_price,
            "btc_ema200_4h": btc_ema200_4h,
            "btc_rsi_4h": btc_rsi_4h,
            "btc_above_ema200": bool(btc_above_ema200),
        }
    except Exception:
        return neutral


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
    tf = utils.display_timeframe(timeframe)

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


def _build_no_clear_auto_result(
    symbol: str,
    timeframe_results: dict,
    warnings: list,
    btc_regime: str = "NEUTRAL",
) -> dict:
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
        "btc_regime": best_setup.get("btc_regime") if best_setup else btc_regime,
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
    exchange_id=None,
    exchange_mode: str = None,
) -> pd.DataFrame:
    symbol = data_provider.normalize_symbol(symbol)
    cache_limit = ohlcv_limit if ohlcv_limit is not None else f"days:{days}"
    exchange_mode = exchange_mode or config.EXCHANGE_MODE
    cache_exchange = exchange_id or config.DEFAULT_EXCHANGE
    cache_key = (symbol, timeframe, cache_limit, cache_exchange, exchange_mode, "spot")

    if data_cache is not None and cache_key in data_cache:
        return data_provider.copy_df_with_attrs(data_cache[cache_key])

    df = data_provider.fetch_ohlcv_with_fallback(
        symbol,
        timeframe,
        days=days,
        ohlcv_limit=ohlcv_limit,
        exchange_id=exchange_id,
        exchange_mode=exchange_mode,
        market_type="spot",
    )
    if data_cache is not None:
        data_cache[cache_key] = data_provider.copy_df_with_attrs(df)
    return data_provider.copy_df_with_attrs(df)


def _source_meta_from_df(df: pd.DataFrame) -> dict:
    attrs = getattr(df, "attrs", {}) or {}
    return {
        "data_source_exchange": attrs.get("exchange_id"),
        "data_source_status": attrs.get("data_source_status"),
        "exchange_mode": attrs.get("exchange_mode"),
        "fallback_used": attrs.get("fallback_used"),
        "data_source_error": attrs.get("data_source_error"),
        "market_type": attrs.get("market_type") or "spot",
        "data_source_market_type": attrs.get("data_source_market_type") or attrs.get("market_type") or "spot",
        "market_symbol": attrs.get("market_symbol"),
        "data_warnings": attrs.get("data_warnings", []),
    }


def _source_meta_from_results(timeframe_results: dict) -> dict:
    for result in (timeframe_results or {}).values():
        if result.get("data_source_exchange"):
            return {
                "data_source_exchange": result.get("data_source_exchange"),
                "data_source_status": result.get("data_source_status"),
                "exchange_mode": result.get("exchange_mode"),
                "fallback_used": result.get("fallback_used"),
                "data_source_error": result.get("data_source_error"),
                "market_type": result.get("market_type") or "spot",
                "data_source_market_type": result.get("data_source_market_type") or result.get("market_type") or "spot",
                "market_symbol": result.get("market_symbol"),
            }
    return {
        "data_source_exchange": None,
        "data_source_status": None,
        "exchange_mode": None,
        "fallback_used": False,
        "data_source_error": None,
        "market_type": "spot",
        "data_source_market_type": "spot",
        "market_symbol": None,
    }


def analyze_symbol_timeframe(symbol: str, timeframe: str,
                             use_intracandle: bool = True,
                             df_daily: pd.DataFrame = None,
                             ohlcv_limit: int = None,
                             data_cache: dict = None,
                             exchange_id=None,
                             exchange_mode: str = None,
                             btc_regime: str = "NEUTRAL",
                             strategy_profile: str = None) -> dict:
    symbol = data_provider.normalize_symbol(symbol)
    exchange_mode = exchange_mode or config.EXCHANGE_MODE
    requested_exchange = exchange_id or config.DEFAULT_EXCHANGE

    try:
        df_raw = _fetch_ohlcv_cached(
            symbol,
            timeframe,
            days=400,
            ohlcv_limit=ohlcv_limit,
            data_cache=data_cache,
            exchange_id=exchange_id,
            exchange_mode=exchange_mode,
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
            "data_source_exchange": requested_exchange if exchange_mode == "manual" else None,
            "data_source_status": "DATA_UNAVAILABLE" if decision == "DATA_UNAVAILABLE" else None,
            "exchange_mode": exchange_mode,
            "fallback_used": False,
            "data_source_error": error_text,
            "market_type": "spot",
            "data_source_market_type": "spot",
            "btc_regime": btc_regime,
        }, timeframe)

    source_meta = _source_meta_from_df(df_raw)
    if df_raw is None or len(df_raw) < 210:
        return _add_action_plan({
            "symbol": symbol,
            "timeframe": timeframe,
            "signal": "NO_DATA",
            "decision": "NO_DATA",
            "error": "Not enough candles",
            "btc_regime": btc_regime,
            "strategy_profile": strategy_profile,
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
            "btc_regime": btc_regime,
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
    
    price = row["close"]
    ema200_val = row["ema200"]
    atr_val = row["atr"]

    # Decision
    res = strategy_engine.evaluate_signal(
        df_raw,
        symbol,
        mode="spot",
        timeframe=timeframe,
        exchange_id=exchange_id,
        market_type="spot",
        strategy_profile=strategy_profile,
        config={"btc_regime": btc_regime}
    )
    decision = res["decision"]
    score = res["score"]
    reasons = res["reasons"]
    warnings = res["warnings"]
    strat = res.get("strategy_params_used", {})
    profile_name = res.get("strategy_profile")
    raw = res.get("raw", {})
    score_max = raw.get("score_max", 10)

    # Confidence
    confidence = round(score / score_max * 100, 1) if score_max > 0 else 0

    # Indicators from row
    rsi_val = row.get("rsi")
    vol_ratio = row.get("vol_ratio")
    
    # S/R from raw
    nearest_sup = raw.get("nearest_support")
    nearest_res = raw.get("nearest_resistance")
    dist_sup = sr_module.distance_pct(price, nearest_sup)
    dist_res = sr_module.distance_pct(price, nearest_res)

    # 1D context bonus / penalty (restaurar lgica visual)
    daily_favorable = None
    if df_daily is not None and len(df_daily) > 0:
        d = df_daily.iloc[-1]
        if d["close"] > d["ema200"] and d["rsi"] >= 50:
            daily_favorable = True
        elif d["close"] < d["ema200"] and d["rsi"] < 45:
            daily_favorable = False

    # Regime filter
    regime_ok = price > ema200_val and (rsi_val or 0) >= 50
    close_above_ema200 = price > ema200_val

    # Signal (alias)
    signal = decision

    candle_time = row["datetime"].isoformat() if hasattr(row["datetime"], "isoformat") else str(row["datetime"])

    result = {
        "symbol": symbol,
        "timeframe": timeframe,
        "analysis_time": datetime.now(timezone.utc).isoformat(),
        "candle_time": candle_time,
        "price": utils.round_value(price),
        "signal": signal,
        "decision": decision,
        "score": score,
        "score_max": score_max,
        "confidence": confidence,
        "regime_filter_passed": regime_ok,
        "close_above_ema200": close_above_ema200,
        "rsi": round(float(rsi_val), 2) if rsi_val is not None else None,
        "ema20": utils.round_value(row.get("ema20")),
        "ema50": utils.round_value(row.get("ema50")),
        "ema200": utils.round_value(ema200_val),
        "atr": utils.round_value(atr_val),
        "atr_pct": round(float(row.get("atr_pct", 0)), 3),
        "vol_ratio": round(float(vol_ratio), 3) if pd.notna(vol_ratio) else None,
        "closed_candle_vol_ratio": volume_meta["closed_candle_vol_ratio"],
        "intracandle_vol_ratio": volume_meta["intracandle_vol_ratio"],
        "adjusted_intracandle_vol_ratio": volume_meta["adjusted_intracandle_vol_ratio"],
        "incomplete_candle_volume": volume_meta["incomplete_candle_volume"],
        "volume_warning": volume_meta["volume_warning"],
        "macd": round(float(row.get("macd", 0)), 6),
        "macd_signal": round(float(row.get("macd_signal", 0)), 6),
        "nearest_support": utils.round_value(nearest_sup) if nearest_sup is not None else None,
        "nearest_resistance": utils.round_value(nearest_res) if nearest_res is not None else None,
        "distance_to_support_pct": round(float(dist_sup), 3) if dist_sup is not None else None,
        "distance_to_resistance_pct": round(float(dist_res), 3) if dist_res is not None else None,
        "estimated_entry": res.get("entry"),
        "estimated_stop_loss": res.get("stop_loss"),
        "estimated_take_profit": res.get("take_profit"),
        "risk_pct": raw.get("risk_pct"),
        "reward_pct": raw.get("reward_pct"),
        "rr_ratio": res.get("risk_reward"),
        "reasons": reasons,
        "missing_conditions": raw.get("missing_conditions", []),
        "warnings": warnings,
        "btc_regime": btc_regime,
        "daily_context_favorable": daily_favorable,
        "mode": "SPOT",
        "market_type": "spot",
        "strategy_profile": profile_name,
        "strategy_signal": res,
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
    exchange_id=None,
    exchange_mode: str = None,
    btc_regime: dict = None,
    strategy_profile: str = None,
) -> dict:
    symbol = data_provider.normalize_symbol(symbol)
    selected_timeframes = _normalize_auto_timeframes(timeframes)
    exchange_mode = exchange_mode or config.EXCHANGE_MODE
    btc_regime_data = btc_regime or {}
    btc_regime_value = btc_regime_data.get("regime", "NEUTRAL")

    # Fetch daily for context
    df_daily = None
    try:
        df_daily_raw = _fetch_ohlcv_cached(
            symbol,
            "1d",
            days=400,
            ohlcv_limit=ohlcv_limit,
            data_cache=data_cache,
            exchange_id=exchange_id,
            exchange_mode=exchange_mode,
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
                                         data_cache=data_cache,
                                         exchange_id=exchange_id,
                                         exchange_mode=exchange_mode,
                                         btc_regime=btc_regime_value,
                                         strategy_profile=strategy_profile)
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
        return _build_no_clear_auto_result(
            symbol,
            timeframe_results,
            all_warnings,
            btc_regime=btc_regime_value,
        )

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
        "btc_regime": btc_regime_value,
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
