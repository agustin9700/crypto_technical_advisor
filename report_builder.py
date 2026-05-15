import csv
import os
from datetime import datetime, timezone

import config
import utils

# Helper alias for unique items
_unique_items = utils.unique_items

BACKTEST_NO_CONFIRM_WARNING = "Backtest no confirma la entrada en este timeframe."


def _fmt(value, decimals: int = 2) -> str:
    """Formatea un valor numérico con un número fijo de decimales."""
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return str(value)


def _price(value) -> str:
    """Formatea un precio usando format_price de utils."""
    return utils.format_price(value)





def _backtest_warning(analysis: dict, backtest: dict = None) -> str:
    verdict = (backtest or {}).get("verdict") or analysis.get("backtest_verdict")
    if verdict in ("BACKTEST_WEAK", "BACKTEST_BAD"):
        return BACKTEST_NO_CONFIRM_WARNING
    return ""


def _get_analysis_time(analysis: dict) -> str:
    best = analysis.get("best_setup") or {}
    return (
        analysis.get("analysis_time")
        or best.get("analysis_time")
        or datetime.now(timezone.utc).isoformat()
    )


def _format_analysis_time(value) -> str:
    if not value:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    if isinstance(value, datetime):
        dt = value
    else:
        raw = str(value)
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return raw

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def get_report_metadata(analysis: dict) -> dict:
    analysis = analysis or {}
    best = analysis.get("best_setup") or {}
    is_auto = bool(analysis.get("timeframe_results"))

    if is_auto:
        timeframe = analysis.get("recommended_timeframe") or (
            "ninguna clara" if analysis.get("no_clear_setup") else "?"
        )
        timeframe_label = "Timeframe recomendado"
    else:
        timeframe = (
            analysis.get("timeframe")
            or analysis.get("recommended_timeframe")
            or best.get("timeframe")
            or "?"
        )
        timeframe_label = "Timeframe analizado"

    analysis_time = _get_analysis_time(analysis)

    return {
        "symbol": analysis.get("symbol") or best.get("symbol") or "?",
        "timeframe": timeframe,
        "timeframe_label": timeframe_label,
        "analysis_time": analysis_time,
        "analysis_time_display": _format_analysis_time(analysis_time),
        "is_auto": is_auto,
    }


def markdown_matches_symbol(markdown_text: str, symbol: str) -> bool:
    return bool(symbol) and symbol.upper() in (markdown_text or "").upper()


def _merge_warnings(analysis: dict, best: dict) -> list:
    warnings = utils.unique_items(best.get("warnings", []))
    for warning in utils.unique_items(analysis.get("warnings", [])):
        if warning not in warnings:
            warnings.append(warning)
    return warnings


def _add_multi_timeframe_table(lines: list, analysis: dict) -> None:
    tf_results = analysis.get("timeframe_results") or {}
    if not tf_results:
        return

    lines += [
        "## Tabla multi-timeframe",
        "",
        "| TF | Decision | Score | Precio | RSI | RR |",
        "|----|----------|-------|--------|-----|----|",
    ]

    for tf, result in tf_results.items():
        if result.get("decision") == "NO_DATA":
            continue
        score = f"{result.get('score', 0)}/{result.get('score_max', 10)}"
        lines.append(
            "| {tf} | {decision} | {score} | {price} | {rsi} | {rr} |".format(
                tf=tf,
                decision=result.get("decision", "-"),
                score=score,
                price=_price(result.get("price")),
                rsi=_fmt(result.get("rsi"), 1),
                rr=_fmt(result.get("rr_ratio"), 2),
            )
        )

    lines.append("")








def _plan_items(best: dict) -> list:
    items = best.get("what_needs_to_happen") or []
    if items:
        return items
    return ["Setup listo; respetar invalidación y gestión de riesgo."]


def build_markdown(analysis: dict, backtest: dict = None) -> str:
    analysis = analysis or {}
    metadata = get_report_metadata(analysis)
    best = analysis.get("best_setup") or analysis

    symbol = metadata["symbol"]
    tf = metadata["timeframe"]
    decision = analysis.get("decision") or best.get("decision") or "?"
    price = analysis.get("price") if analysis.get("price") is not None else best.get("price")
    timeframe_label = "Temporalidad recomendada"

    entry = best.get("estimated_entry")
    sl = best.get("estimated_stop_loss")
    tp = best.get("estimated_take_profit")
    rr = best.get("rr_ratio")
    rsi_val = best.get("rsi")
    score = best.get("score")
    score_max = best.get("score_max", 10)
    confidence = best.get("confidence")
    nearest_res = best.get("nearest_resistance")
    nearest_sup = best.get("nearest_support")
    reasons = utils.unique_items(best.get("reasons", []))
    missing = utils.unique_items(best.get("missing_conditions", []))
    top_backtest_warning = _backtest_warning(analysis, backtest)
    warnings = _merge_warnings(analysis, best)
    if top_backtest_warning:
        warnings = [w for w in warnings if w != top_backtest_warning]
    regime = best.get("regime_filter_passed")
    entry_now = utils.entry_now_display(analysis.get("entry_now_text") or best.get("entry_now_text"))
    main_reason = analysis.get("main_reason") or best.get("main_reason") or "N/A"
    human_verdict = analysis.get("human_verdict") or best.get("human_verdict") or "N/A"
    entry_trigger = analysis.get("entry_trigger") or best.get("entry_trigger") or "N/A"
    invalidation = analysis.get("invalidation_level") or best.get("invalidation_level") or "N/A"
    exchange = analysis.get("data_source_exchange") or best.get("data_source_exchange") or "N/A"
    market_type = analysis.get("market_type") or best.get("market_type") or "spot"

    lines = [
        f"# {symbol} — Technical Advisor",
        "",
        "## Veredicto rápido",
        "",
        f"**Decisión:** {decision}  ",
        f"**{timeframe_label}:** {utils.display_timeframe(tf)}  ",
        f"**Exchange / mercado:** {exchange} / {market_type}  ",
        f"**Entrada ahora:** {entry_now}  ",
        f"**Motivo principal:** {main_reason}.  ",
        f"**Conclusión:** {human_verdict}",
        *(([f"**Backtest:** {top_backtest_warning}"] if top_backtest_warning else [])),
        *(([f"**Observación:** {analysis.get('auto_observation')}"] if analysis.get("auto_observation") else [])),
        "",
        "## Plan de entrada",
        "",
        f"- Entrada estimada: {utils.format_price(entry)}",
        f"- Gatillo válido: {entry_trigger}",
        f"- Take profit: {utils.format_price(tp)}",
        f"- Invalidación: {invalidation}",
        f"- Riesgo/recompensa: {rr:.2f}" if rr is not None else "- Riesgo/recompensa: N/A",
        "",
        "## Qué falta para entrar",
        "",
    ]

    plan_source = analysis if analysis.get("no_clear_setup") else best
    for item in _plan_items(plan_source):
        lines.append(f"- {item}")
    lines.append("")

    lines += [
        "## Contexto del análisis",
        "",
        f"**Análisis:** {metadata['analysis_time_display']}  ",
        f"**Precio actual:** {utils.format_price(price)}  ",
        f"**Score:** {score}/{score_max}  ",
        f"**Confianza:** {confidence:.1f}%  ",
        f"**Régimen OK:** {'SI' if regime else 'NO'}  ",
        f"**RSI:** {rsi_val:.1f}" if rsi_val is not None else "**RSI:** N/A",
        f"**Volumen vela cerrada:** {best.get('closed_candle_vol_ratio', 0):.2f}x  ",
        f"**Volumen intravela:** {best.get('intracandle_vol_ratio', 0):.2f}x",
        "",
    ]

    _add_multi_timeframe_table(lines, analysis)

    if reasons:
        lines.append("## Razones a favor")
        for reason in reasons:
            lines.append(f"- {reason}")
        lines.append("")

    if missing:
        lines.append("## Condiciones faltantes")
        for condition in missing:
            lines.append(f"- {condition}")
        lines.append("")

    if warnings:
        lines.append("## Advertencias")
        for warning in warnings:
            lines.append(f"- {warning}")
        lines.append("")

    lines += [
        "## Niveles estimados",
        "",
        "| Campo | Valor |",
        "|-------|-------|",
        f"| Entrada estimada | {utils.format_price(entry)} |",
        f"| Stop Loss | {utils.format_price(sl)} |",
        f"| Take Profit | {utils.format_price(tp)} |",
        f"| RR | {rr:.2f} |" if rr is not None else "| RR | N/A |",
        f"| Soporte cercano | {utils.format_price(nearest_sup)} |",
        f"| Resistencia cercana | {utils.format_price(nearest_res)} |",
        "",
    ]

    if backtest:
        verdict = backtest.get("verdict", "N/A")
        n_trades = backtest.get("n_trades", 0)
        pf = backtest.get("profit_factor")
        wr = backtest.get("win_rate")
        ret = backtest.get("total_return_pct")
        dd = backtest.get("max_drawdown_pct")
        bt_tf = backtest.get("timeframe") or tf
        bt_title = (
            f"## Backtest rápido del timeframe recomendado: {bt_tf}"
            if metadata["is_auto"]
            else f"## Backtest rápido: {bt_tf}"
        )
        lines += [
            bt_title,
            "",
            "| Métrica | Valor |",
            "|---------|-------|",
            f"| Veredicto | {verdict} |",
            f"| Trades | {n_trades} |",
            f"| Win Rate | {_fmt(wr, 1)}% |",
            f"| Profit Factor | {_fmt(pf, 3)} |",
            f"| Retorno total | {_fmt(ret, 2)}% |",
            f"| Max Drawdown | {_fmt(dd, 2)}% |",
            "",
        ]

    lines += [
        "---",
        "",
        "> Advertencia: Esto es solo analisis tecnico, no consejo financiero.",
        "> No se envian ordenes. No se usa apalancamiento. Solo spot.",
    ]

    return "\n".join(lines)


def save_report(
    analysis: dict,
    backtest: dict = None,
    output_dir: str = None,
    return_content: bool = False,
):
    if output_dir is None:
        output_dir = config.OUTPUT_DIR

    os.makedirs(output_dir, exist_ok=True)

    analysis_for_output = dict(analysis or {})
    analysis_for_output["analysis_time"] = _get_analysis_time(analysis_for_output)
    metadata = get_report_metadata(analysis_for_output)
    best = analysis_for_output.get("best_setup") or analysis_for_output
    warnings = _merge_warnings(analysis_for_output, best)
    md_content = build_markdown(analysis_for_output, backtest)

    md_path = os.path.join(output_dir, "latest_analysis.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    row = {
        "symbol": metadata["symbol"],
        "timeframe": metadata["timeframe"],
        "decision": analysis_for_output.get("decision"),
        "price": best.get("price"),
        "rsi": best.get("rsi"),
        "score": best.get("score"),
        "confidence": best.get("confidence"),
        "estimated_entry": best.get("estimated_entry"),
        "stop_loss": best.get("estimated_stop_loss"),
        "take_profit": best.get("estimated_take_profit"),
        "rr_ratio": best.get("rr_ratio"),
        "nearest_support": best.get("nearest_support"),
        "nearest_resistance": best.get("nearest_resistance"),
        "reasons": "; ".join(_unique_items(best.get("reasons", []))),
        "missing": "; ".join(_unique_items(best.get("missing_conditions", []))),
        "warnings": "; ".join(warnings),
        "closed_candle_vol_ratio": best.get("closed_candle_vol_ratio"),
        "intracandle_vol_ratio": best.get("intracandle_vol_ratio"),
        "adjusted_intracandle_vol_ratio": best.get("adjusted_intracandle_vol_ratio"),
        "volume_warning": best.get("volume_warning"),
        "no_clear_setup": analysis_for_output.get("no_clear_setup"),
        "auto_observation": analysis_for_output.get("auto_observation"),
        "action_summary": analysis_for_output.get("action_summary") or best.get("action_summary"),
        "entry_now_text": analysis_for_output.get("entry_now_text") or best.get("entry_now_text"),
        "entry_trigger": analysis_for_output.get("entry_trigger") or best.get("entry_trigger"),
        "invalidation_level": analysis_for_output.get("invalidation_level") or best.get("invalidation_level"),
        "main_reason": analysis_for_output.get("main_reason") or best.get("main_reason"),
        "what_needs_to_happen": "; ".join(
            analysis_for_output.get("what_needs_to_happen")
            or best.get("what_needs_to_happen", [])
        ),
        "human_verdict": analysis_for_output.get("human_verdict") or best.get("human_verdict"),
        "backtest_verdict": backtest.get("verdict") if backtest else None,
        "backtest_pf": backtest.get("profit_factor") if backtest else None,
        "backtest_trades": backtest.get("n_trades") if backtest else None,
        "backtest_dd": backtest.get("max_drawdown_pct") if backtest else None,
        "analysis_time": metadata["analysis_time"],
    }

    csv_path = os.path.join(output_dir, "latest_analysis.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        writer.writeheader()
        writer.writerow(row)

    if return_content:
        return md_path, csv_path, md_content

    return md_path, csv_path
