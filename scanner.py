import csv
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import backtester
import config
import data_provider
import storage
import technical_analyzer


SCAN_LIMIT = 20
MIN_24H_QUOTE_VOLUME_USDT = 5_000_000
RUN_BACKTEST_FOR_TOP_N = 0
TOP_SYMBOL_FETCH_LIMIT = 100
SCAN_MODES = ["fast", "full"]
SCANNER_FAST_TIMEFRAMES = ["1h", "2h", "4h"]
SCANNER_FULL_TIMEFRAMES = ["15m", "30m", "1h", "2h", "4h", "1d"]
SCANNER_FAST_OHLCV_LIMIT = 320
SCANNER_FULL_OHLCV_LIMIT = None
SCANNER_MAX_WORKERS = config.SCANNER_MAX_WORKERS
EXCLUDED_BASE_ASSETS = {
    "USDC", "FDUSD", "TUSD", "BUSD", "DAI", "USDP",
    "USDD", "FRAX", "LUSD", "USD1", "RLUSD", "USDG", "USDE",
    "USDS", "PYUSD", "GUSD", "EUR", "EURI",
}
EXCLUDE_LOW_HISTORY_SYMBOLS = True
MIN_VALID_TIMEFRAMES_FOR_SCANNER = 2
SCANNER_UNVALIDATED_BACKTEST_VERDICTS = {
    "BACKTEST_BAD",
    "BACKTEST_WEAK",
    "NOT_ENOUGH_TRADES",
}
SCANNER_BACKTEST_DEGRADE_WARNING = "Scanner degradó la señal por backtest insuficiente/débil."

CSV_COLUMNS = [
    "generated_at",
    "scan_mode",
    "validation_status",
    "exchange_mode",
    "market_type",
    "data_source_exchange",
    "data_source_status",
    "fallback_used",
    "data_source_error",
    "rank",
    "symbol",
    "decision",
    "btc_regime",
    "recommended_timeframe",
    "score",
    "confidence",
    "price",
    "rsi",
    "rr_ratio",
    "vol_ratio",
    "quote_volume_24h",
    "entry_now_text",
    "main_reason",
    "entry_trigger",
    "estimated_entry",
    "estimated_stop_loss",
    "estimated_take_profit",
    "risk_pct",
    "reward_pct",
    "backtest_verdict",
    "backtest_profit_factor",
    "backtest_total_return_pct",
    "backtest_max_drawdown_pct",
    "warnings",
]


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value, default=0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_scan_mode(mode: str) -> str:
    mode = (mode or "fast").strip().lower()
    if mode not in SCAN_MODES:
        raise ValueError(f"Modo scanner invalido: {mode}. Usar: {', '.join(SCAN_MODES)}")
    return mode


def _timeframes_for_mode(mode: str) -> list:
    if _normalize_scan_mode(mode) == "fast":
        return list(SCANNER_FAST_TIMEFRAMES)
    return list(SCANNER_FULL_TIMEFRAMES)


def _ohlcv_limit_for_mode(mode: str):
    if _normalize_scan_mode(mode) == "fast":
        return SCANNER_FAST_OHLCV_LIMIT
    return SCANNER_FULL_OHLCV_LIMIT


def _normalize_workers(workers) -> int:
    try:
        workers = int(workers or SCANNER_MAX_WORKERS)
    except (TypeError, ValueError):
        workers = SCANNER_MAX_WORKERS
    return max(1, min(workers, 8))


def _format_duration(seconds) -> str:
    seconds = _safe_float(seconds)
    if seconds >= 60:
        minutes = int(seconds // 60)
        remaining = seconds - minutes * 60
        return f"{minutes}m {remaining:.1f}s"
    return f"{seconds:.1f}s"


def _yes_no(value) -> str:
    return "sí" if value else "no"


def _base_asset(symbol: str) -> str:
    normalized = data_provider.normalize_symbol(symbol)
    return normalized.split("/", 1)[0]


def _is_excluded_base_asset(symbol: str) -> bool:
    return _base_asset(symbol) in EXCLUDED_BASE_ASSETS


def _analysis_has_enough_history(analysis: dict, min_valid_timeframes: int = None) -> bool:
    if min_valid_timeframes is None:
        min_valid_timeframes = MIN_VALID_TIMEFRAMES_FOR_SCANNER

    timeframe_results = (analysis or {}).get("timeframe_results") or {}
    if not timeframe_results:
        return (analysis or {}).get("decision") != "NO_DATA"

    valid_results = [
        result
        for result in timeframe_results.values()
        if result.get("decision") != "NO_DATA" and not result.get("error")
    ]
    return len(valid_results) >= min_valid_timeframes


def _append_warning_text(existing, warning: str) -> str:
    warnings = _unique_items(existing.split(";") if existing else [])
    if warning not in warnings:
        warnings.append(warning)
    return "; ".join(warnings)


def _degrade_unvalidated_candidate(row: dict, original_decision: str, backtest: dict) -> dict:
    verdict = (backtest or {}).get("verdict")
    if (
        original_decision != "ENTER_NOW_CANDIDATE"
        or verdict not in SCANNER_UNVALIDATED_BACKTEST_VERDICTS
    ):
        return row

    updated = dict(row)
    updated["decision"] = "WAIT"
    updated["entry_now_text"] = "Entrada ahora: no recomendable; setup no validado por backtest."
    updated["main_reason"] = (
        "Setup técnico fuerte, pero backtest no confirma o no hay historial suficiente."
    )
    updated["warnings"] = _append_warning_text(
        updated.get("warnings"),
        SCANNER_BACKTEST_DEGRADE_WARNING,
    )
    return updated


def _validation_status(decision: str, scan_mode: str, backtest: dict = None) -> str:
    verdict = (backtest or {}).get("verdict")
    if verdict == "BACKTEST_OK":
        return "BACKTEST_CONFIRMED"
    if verdict == "BACKTEST_WEAK":
        return "BACKTEST_WEAK"
    if verdict == "BACKTEST_BAD":
        return "BACKTEST_BAD"
    if verdict in ("NOT_ENOUGH_TRADES", "NO_DATA"):
        return "NOT_ENOUGH_HISTORY"
    if scan_mode == "fast" and decision == "ENTER_NOW_CANDIDATE":
        return "PENDING_BACKTEST"
    return "NOT_TESTED"


def _apply_fast_pending_validation(row: dict) -> dict:
    if row.get("validation_status") != "PENDING_BACKTEST":
        return row

    updated = dict(row)
    updated["entry_now_text"] = (
        "Candidato tecnico; validar con analisis completo/backtest antes de entrar."
    )
    return updated


def _unique_items(items) -> list:
    if not items:
        return []
    if isinstance(items, str):
        items = [items]

    seen = set()
    cleaned = []
    for item in items:
        if item is None:
            continue
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
    return cleaned


def _merge_warnings(analysis: dict, best: dict) -> list:
    warnings = _unique_items(best.get("warnings", []))
    for warning in _unique_items(analysis.get("warnings", [])):
        if warning not in warnings:
            warnings.append(warning)
    return warnings


def _decision_rank(decision: str) -> int:
    return {
        "ENTER_NOW_CANDIDATE": 0,
        "WAIT": 1,
        "AVOID": 2,
        "DATA_UNAVAILABLE": 3,
        "NO_DATA": 3,
    }.get(decision or "NO_DATA", 4)


def _sort_key(row: dict) -> tuple:
    return (
        _decision_rank(row.get("decision")),
        -_safe_float(row.get("score")),
        -_safe_float(row.get("confidence")),
        -_safe_float(row.get("rr_ratio")),
        -_safe_float(row.get("quote_volume_24h")),
    )


def _format_volume(value) -> str:
    value = _safe_float(value)
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"{value / 1_000:.2f}K"
    return f"{value:.0f}"


def _table_value(value) -> str:
    if value is None:
        return "N/A"
    text = str(value)
    return text.replace("|", "/")


def _scan_table(rows: list, limit: int = 15) -> list:
    lines = [
        "| Rank | Symbol | Decision | Status | TF | Score | Conf | RR | BT | PF | Return % | DD % | Vol 24h | Entry now | Main reason |",
        "|------|--------|----------|--------|----|-------|------|----|----|----|----------|------|---------|-----------|-------------|",
    ]
    for row in rows[:limit]:
        lines.append(
            "| {rank} | {symbol} | {decision} | {status} | {tf} | {score} | {conf}% | {rr} | {bt} | {pf} | {ret} | {dd} | {vol} | {entry} | {reason} |".format(
                rank=row.get("rank", ""),
                symbol=_table_value(row.get("symbol")),
                decision=_table_value(row.get("decision")),
                status=_table_value(row.get("validation_status")),
                tf=_table_value(row.get("recommended_timeframe")),
                score=_table_value(row.get("score")),
                conf=_table_value(row.get("confidence")),
                rr=_table_value(row.get("rr_ratio")),
                bt=_table_value(row.get("backtest_verdict")),
                pf=_table_value(row.get("backtest_profit_factor")),
                ret=_table_value(row.get("backtest_total_return_pct")),
                dd=_table_value(row.get("backtest_max_drawdown_pct")),
                vol=_format_volume(row.get("quote_volume_24h")),
                entry=_table_value(row.get("entry_now_text")),
                reason=_table_value(row.get("main_reason")),
            )
        )
    return lines


def _build_row(
    analysis: dict,
    quote_volume_24h: float,
    generated_at: str,
    scan_mode: str,
    warning_items: list = None,
    backtest: dict = None,
) -> dict:
    analysis = analysis or {}
    best = analysis.get("best_setup") or analysis
    plan = analysis if analysis.get("action_summary") else best
    is_auto = bool(analysis.get("timeframe_results"))
    recommended_timeframe = analysis.get("recommended_timeframe")
    if not is_auto and not recommended_timeframe:
        recommended_timeframe = best.get("timeframe") or analysis.get("timeframe")
    warnings = _merge_warnings(analysis, best)
    warnings.extend(_unique_items(warning_items))
    warnings = _unique_items(warnings)

    row = {
        "generated_at": generated_at,
        "scan_mode": scan_mode,
        "validation_status": _validation_status(
            analysis.get("decision") or best.get("decision") or "NO_DATA",
            scan_mode,
            backtest,
        ),
        "data_source_exchange": analysis.get("data_source_exchange") or best.get("data_source_exchange"),
        "data_source_status": analysis.get("data_source_status") or best.get("data_source_status"),
        "exchange_mode": analysis.get("exchange_mode") or best.get("exchange_mode"),
        "market_type": analysis.get("market_type") or best.get("market_type") or "spot",
        "fallback_used": analysis.get("fallback_used") or best.get("fallback_used") or False,
        "data_source_error": analysis.get("data_source_error") or best.get("data_source_error"),
        "rank": None,
        "symbol": analysis.get("symbol") or best.get("symbol"),
        "decision": analysis.get("decision") or best.get("decision") or "NO_DATA",
        "btc_regime": analysis.get("btc_regime") or best.get("btc_regime") or "NEUTRAL",
        "recommended_timeframe": recommended_timeframe,
        "score": best.get("score"),
        "confidence": best.get("confidence"),
        "price": best.get("price"),
        "rsi": best.get("rsi"),
        "rr_ratio": best.get("rr_ratio"),
        "vol_ratio": best.get("closed_candle_vol_ratio", best.get("vol_ratio")),
        "quote_volume_24h": quote_volume_24h,
        "entry_now_text": plan.get("entry_now_text"),
        "main_reason": plan.get("main_reason"),
        "entry_trigger": plan.get("entry_trigger"),
        "estimated_entry": best.get("estimated_entry"),
        "estimated_stop_loss": best.get("estimated_stop_loss"),
        "estimated_take_profit": best.get("estimated_take_profit"),
        "risk_pct": best.get("risk_pct"),
        "reward_pct": best.get("reward_pct"),
        "backtest_verdict": backtest.get("verdict") if backtest else None,
        "backtest_profit_factor": backtest.get("profit_factor") if backtest else None,
        "backtest_total_return_pct": backtest.get("total_return_pct") if backtest else None,
        "backtest_max_drawdown_pct": backtest.get("max_drawdown_pct") if backtest else None,
        "warnings": "; ".join(warnings),
    }
    return _apply_fast_pending_validation(row)


def _build_error_row(
    symbol: str,
    generated_at: str,
    scan_mode: str,
    quote_volume_24h: float,
    error: str,
    exchange_id=None,
    exchange_mode: str = None,
    btc_regime: str = "NEUTRAL",
) -> dict:
    is_data_unavailable = data_provider.DATA_UNAVAILABLE in str(error)
    return {
        "generated_at": generated_at,
        "scan_mode": scan_mode,
        "validation_status": "NOT_TESTED" if is_data_unavailable else "NOT_ENOUGH_HISTORY",
        "exchange_mode": exchange_mode,
        "market_type": "spot",
        "data_source_exchange": exchange_id,
        "data_source_status": "DATA_UNAVAILABLE" if is_data_unavailable else None,
        "fallback_used": False,
        "data_source_error": error,
        "rank": None,
        "symbol": symbol,
        "decision": "DATA_UNAVAILABLE" if is_data_unavailable else "NO_DATA",
        "btc_regime": btc_regime,
        "recommended_timeframe": None,
        "score": None,
        "confidence": None,
        "price": None,
        "rsi": None,
        "rr_ratio": None,
        "vol_ratio": None,
        "quote_volume_24h": quote_volume_24h,
        "entry_now_text": "Entrada ahora: no recomendable",
        "main_reason": (
            "No se pudieron obtener datos desde los exchanges configurados."
            if is_data_unavailable
            else "No hay datos suficientes"
        ),
        "entry_trigger": (
            "No se pudieron obtener datos desde los exchanges configurados."
            if is_data_unavailable
            else None
        ),
        "estimated_entry": None,
        "estimated_stop_loss": None,
        "estimated_take_profit": None,
        "risk_pct": None,
        "reward_pct": None,
        "backtest_verdict": None,
        "backtest_profit_factor": None,
        "backtest_total_return_pct": None,
        "backtest_max_drawdown_pct": None,
        "warnings": error,
    }


def _write_csv(rows: list, output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "latest_scan.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column) for column in CSV_COLUMNS})
    return path


def _write_markdown(scan_result: dict, output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "latest_scan.md")

    rows = scan_result["rows"]
    pending_rows = [r for r in rows if r.get("validation_status") == "PENDING_BACKTEST"]
    enter_rows = [
        r
        for r in rows
        if r.get("decision") == "ENTER_NOW_CANDIDATE"
        and r.get("validation_status") != "PENDING_BACKTEST"
    ]
    wait_rows = [r for r in rows if r.get("decision") == "WAIT"]
    filters = scan_result.get("filters", {})

    lines = [
        "# Crypto Technical Advisor — Market Scanner",
        "",
        "## Resumen",
        f"- Fecha/hora: {scan_result['generated_at']}",
        f"- Pares analizados: {scan_result['analyzed_count']}",
        f"- Modo scanner: {scan_result.get('scan_mode', 'fast')}",
        f"- Timeframes analizados: {', '.join(scan_result.get('timeframes', []))}",
        f"- Backtests ejecutados: {scan_result.get('backtests_executed', 0)}",
        f"- Exchange mode: {scan_result.get('exchange_mode') or 'N/A'}",
        f"- Market type: {scan_result.get('market_type') or 'spot'}",
        f"- Data source exchange: {scan_result.get('data_source_exchange') or 'N/A'}",
        f"- Fallback used: {_yes_no(scan_result.get('fallback_used', False))}",
        f"- Workers: {scan_result.get('workers', 1)}",
        f"- Tiempo total: {_format_duration(scan_result.get('elapsed_seconds', 0))}",
        f"- Tiempo promedio por simbolo: {_format_duration(scan_result.get('average_symbol_seconds', 0))}",
        f"- Simbolos fallidos: {scan_result.get('failed_symbols_count', 0)}",
        f"- ENTER_NOW_CANDIDATE encontrados: {scan_result['decision_counts'].get('ENTER_NOW_CANDIDATE', 0)}",
        f"- WAIT encontrados: {scan_result['decision_counts'].get('WAIT', 0)}",
        f"- AVOID encontrados: {scan_result['decision_counts'].get('AVOID', 0)}",
        f"- DATA_UNAVAILABLE encontrados: {scan_result['decision_counts'].get('DATA_UNAVAILABLE', 0)}",
        "",
        "## Filtros aplicados",
        "",
        f"- Stablecoins excluidas: {_yes_no(filters.get('stablecoins_excluded', True))}",
        f"- Modo scanner: {scan_result.get('scan_mode', 'fast')}",
        f"- Timeframes analizados: {', '.join(scan_result.get('timeframes', []))}",
        f"- Backtests ejecutados: {scan_result.get('backtests_executed', 0)}",
        f"- Exchange mode: {scan_result.get('exchange_mode') or 'N/A'}",
        f"- Market type: {scan_result.get('market_type') or 'spot'}",
        f"- Data source exchange: {scan_result.get('data_source_exchange') or 'N/A'}",
        f"- Fallback used: {_yes_no(scan_result.get('fallback_used', False))}",
        f"- Workers: {scan_result.get('workers', 1)}",
        f"- Tokens con historial insuficiente excluidos: {filters.get('low_history_excluded_count', 0)}",
        "",
        "## Candidatos tecnicos pendientes de validacion",
        "",
    ]

    if pending_rows:
        lines.extend(_scan_table(pending_rows, limit=len(pending_rows)))
    else:
        lines.append("_Sin candidatos tecnicos pendientes de validacion._")

    lines += [
        "",
        "## Entradas candidatas validadas",
        "",
    ]

    if enter_rows:
        lines.extend(_scan_table(enter_rows, limit=len(enter_rows)))
    else:
        lines.append("_Sin entradas candidatas ahora._")

    lines += [
        "",
        "## Setups en espera",
        "",
    ]
    if wait_rows:
        lines.extend(_scan_table(wait_rows, limit=len(wait_rows)))
    else:
        lines.append("_Sin setups en espera ahora._")

    lines += [
        "",
        "## Top observaciones",
        "",
    ]
    if rows:
        lines.extend(_scan_table(rows, limit=min(15, len(rows))))
    else:
        lines.append("_Sin resultados._")

    warnings = _unique_items(scan_result.get("warnings", []))
    if warnings:
        lines += [
            "",
            "## Warnings del scan",
            "",
        ]
        for warning in warnings:
            lines.append(f"- {warning}")

    lines += [
        "",
        "## Advertencias",
        "- Paper/analysis only",
        "- No live trading",
        "- No financial advice",
        "- Spot long-only. No futures.",
        "",
    ]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def _progress(progress_callback, current: int, total: int, message: str) -> None:
    if progress_callback:
        progress_callback(current, total, message)


def _fetch_scan_symbols(
    limit: int,
    min_quote_volume: float,
    exclude_stablecoins: bool = True,
    exchange_id=None,
    exchange_mode: str = None,
) -> tuple:
    fetch_limit = max(TOP_SYMBOL_FETCH_LIMIT, limit * 4)
    top_result = data_provider.get_top_usdt_symbols_by_volume_result(
        exchange_id=exchange_id,
        limit=fetch_limit,
        exchange_mode=exchange_mode,
    )
    symbols = top_result["symbols"]
    ranked_volume = {symbol: volume for symbol, volume in top_result.get("ranked", [])}

    selected = []
    warnings = []
    stats = {"stablecoins_excluded": 0}
    source_meta = {
        "exchange_id": top_result.get("exchange_id"),
        "exchange_mode": top_result.get("exchange_mode"),
        "market_type": top_result.get("market_type") or "spot",
        "data_source_status": top_result.get("data_source_status"),
        "fallback_used": top_result.get("fallback_used", False),
        "data_source_error": top_result.get("data_source_error"),
    }
    for symbol in symbols:
        if exclude_stablecoins and _is_excluded_base_asset(symbol):
            stats["stablecoins_excluded"] += 1
            continue

        quote_volume = _safe_float(ranked_volume.get(symbol))
        if quote_volume < min_quote_volume:
            continue
        selected.append((symbol, quote_volume))
        if len(selected) >= limit:
            break

    return selected, warnings, stats, source_meta


def _analyze_scan_symbol(
    symbol: str,
    quote_volume: float,
    generated_at: str,
    mode: str,
    scan_timeframes: list,
    ohlcv_limit,
    exclude_low_history: bool,
    exchange_id=None,
    exchange_mode: str = None,
    btc_regime: dict = None,
) -> dict:
    started_at = time.perf_counter()
    warnings = []
    try:
        local_data_cache = {}
        analysis = technical_analyzer.analyze_symbol_auto(
            symbol,
            timeframes=scan_timeframes,
            ohlcv_limit=ohlcv_limit,
            data_cache=local_data_cache,
            exchange_id=exchange_id,
            exchange_mode=exchange_mode,
            btc_regime=btc_regime,
        )
        if (
            exclude_low_history
            and analysis.get("decision") != "DATA_UNAVAILABLE"
            and not _analysis_has_enough_history(analysis)
        ):
            warning = f"{symbol}: excluido por historial insuficiente para scanner confiable"
            warnings.append(warning)
            return {
                "symbol": symbol,
                "row": None,
                "analysis": None,
                "warnings": warnings,
                "low_history_excluded": 1,
                "failed": False,
                "elapsed_seconds": time.perf_counter() - started_at,
            }

        return {
            "symbol": symbol,
            "row": _build_row(analysis, quote_volume, generated_at, mode),
            "analysis": analysis,
            "warnings": warnings,
            "low_history_excluded": 0,
            "failed": False,
            "elapsed_seconds": time.perf_counter() - started_at,
        }
    except Exception as exc:
        warning = f"{symbol}: fallo el analisis ({exc})"
        print(f"WARNING: {warning}")
        warnings.append(warning)
        return {
            "symbol": symbol,
            "row": _build_error_row(
                symbol,
                generated_at,
                mode,
                quote_volume,
                warning,
                exchange_id=exchange_id,
                exchange_mode=exchange_mode,
                btc_regime=(btc_regime or {}).get("regime", "NEUTRAL"),
            ),
            "analysis": None,
            "warnings": warnings,
            "low_history_excluded": 0,
            "failed": True,
            "elapsed_seconds": time.perf_counter() - started_at,
        }


def run_scan(
    limit: int = SCAN_LIMIT,
    min_quote_volume: float = MIN_24H_QUOTE_VOLUME_USDT,
    backtest_top_n: int = RUN_BACKTEST_FOR_TOP_N,
    mode: str = "fast",
    workers: int = SCANNER_MAX_WORKERS,
    output_dir: str = None,
    progress_callback=None,
    exclude_stablecoins: bool = True,
    exclude_low_history: bool = EXCLUDE_LOW_HISTORY_SYMBOLS,
    exchange_id=None,
    exchange_mode: str = None,
) -> dict:
    started_at = time.perf_counter()
    mode = _normalize_scan_mode(mode)
    exchange_mode = (exchange_mode or config.EXCHANGE_MODE).strip().lower()
    if exchange_mode not in ("manual", "fallback"):
        raise ValueError("exchange_mode debe ser 'manual' o 'fallback'")
    exchange_id = (exchange_id or config.DEFAULT_EXCHANGE).strip().lower()
    scan_timeframes = _timeframes_for_mode(mode)
    ohlcv_limit = _ohlcv_limit_for_mode(mode)
    workers = _normalize_workers(workers)
    limit = max(1, min(int(limit or SCAN_LIMIT), TOP_SYMBOL_FETCH_LIMIT))
    backtest_top_n = max(0, int(backtest_top_n or 0))
    if mode == "fast" and backtest_top_n:
        backtest_top_n = 0
        scan_warnings = ["Modo fast: backtest_top ignorado. Usar mode='full' para backtests."]
    else:
        scan_warnings = []
    output_dir = output_dir or config.OUTPUT_DIR
    generated_at = _now_utc()
    _progress(progress_callback, 0, limit, "Evaluando régimen BTC 4H...")
    btc_regime = technical_analyzer.get_btc_regime(
        exchange_id=exchange_id,
        exchange_mode=exchange_mode,
    )

    _progress(progress_callback, 0, limit, "Buscando pares USDT con mayor volumen...")
    symbols_with_volume, symbol_warnings, filter_stats, scan_source_meta = _fetch_scan_symbols(
        limit,
        min_quote_volume,
        exclude_stablecoins=exclude_stablecoins,
        exchange_id=exchange_id,
        exchange_mode=exchange_mode,
    )
    scan_warnings.extend(symbol_warnings)
    if scan_source_meta.get("fallback_used"):
        scan_warnings.append(
            "Scanner usando fallback de datos: "
            f"{scan_source_meta.get('exchange_id')} "
            f"({scan_source_meta.get('data_source_error')})"
        )
    low_history_excluded = 0

    rows = []
    analyses = {}
    failed_symbols = []
    symbol_elapsed_seconds = []
    total = len(symbols_with_volume)

    def handle_symbol_result(result: dict, completed: int) -> None:
        nonlocal low_history_excluded
        scan_warnings.extend(result.get("warnings", []))
        low_history_excluded += result.get("low_history_excluded", 0)
        if result.get("failed"):
            failed_symbols.append(result.get("symbol"))
        if result.get("elapsed_seconds") is not None:
            symbol_elapsed_seconds.append(result.get("elapsed_seconds"))
        if result.get("analysis"):
            analyses[result["symbol"]] = result["analysis"]
        if result.get("row"):
            rows.append(result["row"])
        _progress(progress_callback, completed, total, f"Analizado {result.get('symbol')}")

    if total and workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = []
            for symbol, quote_volume in symbols_with_volume:
                futures.append(
                    executor.submit(
                        _analyze_scan_symbol,
                        symbol,
                        quote_volume,
                        generated_at,
                        mode,
                        scan_timeframes,
                        ohlcv_limit,
                        exclude_low_history,
                        exchange_id,
                        exchange_mode,
                        btc_regime,
                    )
                )

            for completed, future in enumerate(as_completed(futures), start=1):
                handle_symbol_result(future.result(), completed)
    else:
        for completed, (symbol, quote_volume) in enumerate(symbols_with_volume, start=1):
            _progress(progress_callback, completed - 1, total, f"Analizando {symbol}...")
            result = _analyze_scan_symbol(
                symbol,
                quote_volume,
                generated_at,
                mode,
                scan_timeframes,
                ohlcv_limit,
                exclude_low_history,
                exchange_id,
                exchange_mode,
                btc_regime,
            )
            handle_symbol_result(result, completed)

    rows.sort(key=_sort_key)

    backtest_candidates = [
        (row_index, row)
        for row_index, row in enumerate(rows)
        if row.get("decision") in ("ENTER_NOW_CANDIDATE", "WAIT")
        and row.get("recommended_timeframe")
    ][:backtest_top_n]

    backtests_executed = 0
    if backtest_candidates:
        total_bt = len(backtest_candidates)
        for index, (row_index, row) in enumerate(backtest_candidates, start=1):
            symbol = row["symbol"]
            timeframe = row["recommended_timeframe"]
            _progress(progress_callback, index - 1, total_bt, f"Backtest {symbol} / {timeframe}...")
            try:
                backtest = backtester.run_quick_backtest(
                    symbol,
                    timeframe,
                    exchange_id=exchange_id,
                    exchange_mode=exchange_mode,
                    market_type="spot",
                    mode="spot",
                )
                if storage.is_sqlite_backend():
                    storage.get_storage().insert_backtest_result(backtest)
            except Exception as exc:
                warning = f"{symbol}: fallo el backtest {timeframe} ({exc})"
                print(f"WARNING: {warning}")
                scan_warnings.append(warning)
                _progress(progress_callback, index, total_bt, f"Backtest fallo {symbol}")
                continue

            analysis = analyses.get(symbol)
            original_decision = row.get("decision")
            if analysis:
                analysis = technical_analyzer.apply_backtest_to_analysis(analysis, backtest)
                analyses[symbol] = analysis
                updated_row = _build_row(
                    analysis,
                    row.get("quote_volume_24h"),
                    generated_at,
                    mode,
                    backtest=backtest,
                )
            else:
                updated_row = dict(row)
                updated_row["backtest_verdict"] = backtest.get("verdict")
                updated_row["backtest_profit_factor"] = backtest.get("profit_factor")
                updated_row["backtest_total_return_pct"] = backtest.get("total_return_pct")
                updated_row["backtest_max_drawdown_pct"] = backtest.get("max_drawdown_pct")
                updated_row["validation_status"] = _validation_status(
                    updated_row.get("decision"),
                    mode,
                    backtest,
                )

            updated_row = _degrade_unvalidated_candidate(
                updated_row,
                original_decision,
                backtest,
            )
            rows[row_index] = updated_row
            backtests_executed += 1
            _progress(progress_callback, index, total_bt, f"Backtest listo {symbol}")

    rows.sort(key=_sort_key)
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank

    decision_counts = {}
    validation_counts = {}
    for row in rows:
        decision = row.get("decision") or "NO_DATA"
        decision_counts[decision] = decision_counts.get(decision, 0) + 1
        validation_status = row.get("validation_status") or "NOT_TESTED"
        validation_counts[validation_status] = validation_counts.get(validation_status, 0) + 1

    elapsed_seconds = time.perf_counter() - started_at
    average_symbol_seconds = (
        sum(symbol_elapsed_seconds) / len(symbol_elapsed_seconds)
        if symbol_elapsed_seconds
        else 0
    )

    scan_result = {
        "generated_at": generated_at,
        "scan_limit": limit,
        "min_quote_volume": min_quote_volume,
        "scan_mode": mode,
        "timeframes": scan_timeframes,
        "ohlcv_limit": ohlcv_limit,
        "workers": workers,
        "exchange_mode": exchange_mode,
        "market_type": "spot",
        "btc_regime": btc_regime,
        "data_source_exchange": scan_source_meta.get("exchange_id"),
        "data_source_status": scan_source_meta.get("data_source_status"),
        "data_source_error": scan_source_meta.get("data_source_error"),
        "fallback_used": bool(scan_source_meta.get("fallback_used")),
        "filters": {
            "stablecoins_excluded": bool(exclude_stablecoins),
            "stablecoins_excluded_count": filter_stats.get("stablecoins_excluded", 0),
            "low_history_excluded": bool(exclude_low_history),
            "low_history_excluded_count": low_history_excluded,
        },
        "backtest_top_n": backtest_top_n,
        "backtests_executed": backtests_executed,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "elapsed_display": _format_duration(elapsed_seconds),
        "average_symbol_seconds": round(average_symbol_seconds, 3),
        "average_symbol_display": _format_duration(average_symbol_seconds),
        "failed_symbols_count": len(failed_symbols),
        "failed_symbols": failed_symbols,
        "analyzed_count": len(rows),
        "decision_counts": decision_counts,
        "validation_counts": validation_counts,
        "rows": rows,
        "warnings": _unique_items(scan_warnings),
        "storage_backend": storage.get_storage_backend(),
    }

    if storage.is_sqlite_backend():
        storage.get_storage().insert_scanner_run(scan_result)
        csv_path = None
    else:
        csv_path = _write_csv(rows, output_dir)
    md_path = _write_markdown(scan_result, output_dir)
    scan_result["csv_path"] = csv_path
    scan_result["md_path"] = md_path

    _progress(progress_callback, len(rows), len(rows), "Scanner terminado")
    return scan_result


def run_market_scan(
    limit=20,
    backtest_top=0,
    mode="fast",
    workers=SCANNER_MAX_WORKERS,
    exchange_id=None,
    exchange_mode="manual",
    **kwargs,
) -> dict:
    return run_scan(
        limit=limit,
        backtest_top_n=backtest_top,
        mode=mode,
        workers=workers,
        exchange_id=exchange_id,
        exchange_mode=exchange_mode,
        **kwargs,
    )


if __name__ == "__main__":
    result = run_scan()
    print(f"Scan listo: {result['analyzed_count']} pares analizados")
    print(f"Modo: {result['scan_mode']} | Timeframes: {', '.join(result['timeframes'])}")
    print(f"Backtests ejecutados: {result['backtests_executed']}")
    print(f"Workers: {result['workers']}")
    print(f"Tiempo total: {result['elapsed_display']}")
    print(f"Tiempo promedio por simbolo: {result['average_symbol_display']}")
    print(f"Simbolos fallidos: {result['failed_symbols_count']}")
    print(f"CSV: {result['csv_path']}")
    print(f"Markdown: {result['md_path']}")
