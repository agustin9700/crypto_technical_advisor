import math

import pandas as pd

import config
import data_provider
import indicators
import strategy_engine
import utils

# Helper for safe float conversion
_safe_float = utils.safe_float


FUTURES_TIMEFRAMES = ["15m", "30m", "1h", "2h", "4h"]
LEVERAGE_WARNING = strategy_engine.LEVERAGE_WARNING





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
    cache_key = (
        "FUTURES",
        symbol,
        timeframe,
        cache_limit,
        exchange_id or config.DEFAULT_EXCHANGE,
        exchange_mode,
        "futures",
    )
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
        market_type="futures",
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
        "market_type": attrs.get("market_type") or "futures",
        "data_source_market_type": attrs.get("data_source_market_type") or attrs.get("market_type") or "futures",
        "market_symbol": attrs.get("market_symbol"),
        "data_warnings": attrs.get("data_warnings", []),
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
        "action_summary": "No tomaria decision futures sin datos suficientes.",
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
        "market_type": "futures",
        "data_source_market_type": "futures",
        "market_symbol": None,
        "no_clear_setup": True,
    }


def _result_from_strategy_signal(signal: dict, source_meta: dict, exchange_mode: str) -> dict:
    raw = signal.get("raw") or {}
    decision = signal.get("decision") or "WAIT"
    direction = raw.get("direction") or "NEUTRAL"
    result = {
        "mode": "FUTURES",
        "symbol": signal.get("symbol"),
        "timeframe": signal.get("timeframe"),
        "recommended_timeframe": signal.get("timeframe"),
        "decision": decision,
        "direction": direction,
        "entry_now": bool(raw.get("entry_now")),
        "entry_price": raw.get("entry_price") or signal.get("entry"),
        "stop_loss": raw.get("stop_loss") or signal.get("stop_loss"),
        "take_profit_1": raw.get("take_profit_1") or signal.get("take_profit"),
        "take_profit_2": raw.get("take_profit_2"),
        "rr_ratio": raw.get("rr_ratio") or signal.get("risk_reward"),
        "risk_pct_to_stop": raw.get("risk_pct_to_stop"),
        "long_score": int(raw.get("long_score") or 0),
        "short_score": int(raw.get("short_score") or 0),
        "confidence": int(raw.get("confidence") or 0),
        "main_reason": raw.get("main_reason"),
        "action_summary": raw.get("action_summary"),
        "missing_conditions": raw.get("missing_conditions") or [],
        "warnings": list(signal.get("warnings") or []),
        "suggested_leverage_label": raw.get("suggested_leverage_label"),
        "suggested_leverage_max": raw.get("suggested_leverage_max"),
        "leverage_warning": raw.get("leverage_warning") or LEVERAGE_WARNING,
        "invalidation": raw.get("invalidation"),
        "price": utils.round_value(raw.get("price")),
        "rsi": utils.round_value(raw.get("rsi"), 2),
        "ema20": utils.round_value(raw.get("ema20")),
        "ema50": utils.round_value(raw.get("ema50")),
        "ema200": utils.round_value(raw.get("ema200")),
        "macd": utils.round_value(raw.get("macd")),
        "macd_signal": utils.round_value(raw.get("macd_signal")),
        "atr": utils.round_value(raw.get("atr")),
        "atr_pct": utils.round_value(raw.get("atr_pct"), 3),
        "bb_upper": utils.round_value(raw.get("bb_upper")),
        "bb_mid": utils.round_value(raw.get("bb_mid")),
        "bb_lower": utils.round_value(raw.get("bb_lower")),
        "vol_ratio": utils.round_value(raw.get("vol_ratio"), 3),
        "volume_confirms": bool(raw.get("volume_confirms")),
        "nearest_support": utils.round_value(raw.get("nearest_support")),
        "nearest_resistance": utils.round_value(raw.get("nearest_resistance")),
        "broken_resistance": utils.round_value(raw.get("broken_resistance")),
        "lost_support": utils.round_value(raw.get("lost_support")),
        "data_source_exchange": source_meta.get("data_source_exchange"),
        "exchange_mode": source_meta.get("exchange_mode") or exchange_mode,
        "fallback_used": source_meta.get("fallback_used", False),
        "data_source_error": source_meta.get("data_source_error"),
        "market_type": source_meta.get("market_type") or "futures",
        "data_source_market_type": source_meta.get("data_source_market_type") or "futures",
        "market_symbol": source_meta.get("market_symbol"),
        "no_clear_setup": bool(raw.get("no_clear_setup", decision in ("WAIT", "AVOID"))),
        "reasons": list(signal.get("reasons") or []),
        "strategy_profile": signal.get("strategy_profile"),
    }
    result["strategy_signal"] = signal
    return result

def analyze_futures_symbol_timeframe(
    symbol: str,
    timeframe: str = "1h",
    exchange_id: str | None = None,
    exchange_mode: str = "manual",
    ohlcv_limit: int | None = None,
    data_cache: dict | None = None,
    strategy_profile: str | None = None,
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
            "No hay suficientes velas validas luego de indicadores.",
            exchange_id=source_meta.get("data_source_exchange") or exchange_id,
            exchange_mode=source_meta.get("exchange_mode") or exchange_mode,
        )

    signal = strategy_engine.evaluate_signal(
        df,
        symbol=symbol,
        mode="futures",
        timeframe=timeframe,
        exchange_id=source_meta.get("data_source_exchange") or exchange_id,
        market_type="futures",
        strategy_profile=strategy_profile,
        config={"source_warnings": source_meta.get("data_warnings") or []},
    )
    return _result_from_strategy_signal(signal, source_meta, exchange_mode)


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
    timeframes: list | None = None,
    exchange_id: str | None = None,
    exchange_mode: str = "manual",
    ohlcv_limit: int | None = None,
    data_cache: dict | None = None,
    strategy_profile: str | None = None,
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
            strategy_profile=strategy_profile,
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
                "action_summary": "No tomaria decision futures sin datos disponibles.",
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
                "market_type": "futures",
                "data_source_market_type": "futures",
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
            "action_summary": "Evitar futures hasta que una temporalidad confirme direccion y volumen.",
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
            "market_type": "futures",
            "data_source_market_type": "futures",
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
