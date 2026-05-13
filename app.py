import streamlit as st
import pandas as pd
import os
from datetime import datetime, timezone

import config
import utils
import technical_analyzer
import backtester
import cycle_runner
import report_builder
import scanner
import signal_tracker
import validator


def _unique_items(items) -> list:
    if not items:
        return []
    if isinstance(items, str):
        items = [items]

    seen = set()
    cleaned = []
    section_labels = {"razones", "condiciones faltantes", "advertencias"}
    for item in items:
        if item is None:
            continue
        text = str(item).strip()
        if not text:
            continue
        if text.rstrip(":").strip().lower() in section_labels:
            continue
        if text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
    return cleaned


def _backtest_warning(result: dict, bt_result: dict = None) -> str:
    verdict = (bt_result or {}).get("verdict") or result.get("backtest_verdict")
    if verdict in ("BACKTEST_WEAK", "BACKTEST_BAD"):
        return technical_analyzer.BACKTEST_NO_CONFIRM_WARNING
    return ""


def _is_binance_network_error(error: Exception) -> bool:
    text = f"{type(error).__name__}: {error}".lower()
    hints = (
        "binance",
        "ccxt",
        "ssl",
        "certificate",
        "network",
        "connection",
        "timeout",
        "max retries",
        "exchangeinfo",
        "fetch_ohlcv",
        "fetch_ticker",
    )
    return any(hint in text for hint in hints)


def _friendly_error(error: Exception, fallback: str) -> str:
    if _is_binance_network_error(error):
        return "No se pudo consultar Binance. Proba de nuevo en unos minutos."
    return f"{fallback}: {error}"


st.set_page_config(
    page_title="Crypto Technical Advisor",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Header ──────────────────────────────────────────────────────────────────

st.title("📊 Crypto Technical Advisor")
st.caption("Spot long-only · Analysis only · No live orders · No API keys required")
st.warning("Paper/analysis only. No live trading. No financial advice.")

# ─── Input ───────────────────────────────────────────────────────────────────

st.markdown("---")
col1, col2 = st.columns([2, 1])

with col1:
    symbol_input = st.text_input(
        "Symbol",
        value=config.DEFAULT_SYMBOL,
        placeholder="e.g. ETH/USDT, SOL/USDT, PEPE/USDT",
        help="Binance spot pair",
    )

with col2:
    tf_options = ["Auto timeframe"] + config.TIMEFRAMES
    timeframe_select = st.selectbox("Timeframe", tf_options, index=0)

run_backtest = st.checkbox("Run quick backtest (takes ~10s extra)", value=False)
analyze_btn = st.button("🔍 Analyze", type="primary", use_container_width=True)

st.markdown("---")
st.subheader("Market Scanner")
scan_col1, scan_col2, scan_col3, scan_col4, scan_col5 = st.columns([1, 1, 1, 1, 2])
with scan_col1:
    scan_limit = st.selectbox("Symbols to scan", [20, 50, 100], index=0)
with scan_col2:
    scan_mode_label = st.selectbox("Scan mode", ["Fast", "Full"], index=0)
with scan_col3:
    scan_backtest_top = st.selectbox("Backtest top N", [0, 3, 5, 10], index=0)
with scan_col4:
    scan_workers = st.selectbox("Workers", [1, 3, 5, 8], index=2)
with scan_col5:
    st.write("")
    scan_btn = st.button("Run scanner", use_container_width=True)

st.info("Fast mode analiza solo 1h, 2h y 4h. Para backtest o todos los timeframes usar Full.")

if scan_btn:
    progress_bar = st.progress(0)
    progress_text = st.empty()

    def update_scan_progress(current, total, message):
        pct = 0 if not total else min(max(current / total, 0), 1)
        progress_bar.progress(pct)
        progress_text.caption(message)

    with st.spinner("Scanning top USDT spot pairs..."):
        try:
            scan_result = scanner.run_scan(
                limit=scan_limit,
                backtest_top_n=scan_backtest_top,
                mode=scan_mode_label.lower(),
                workers=scan_workers,
                progress_callback=update_scan_progress,
            )
        except Exception as e:
            st.error(_friendly_error(e, "Scanner failed"))
            st.stop()

    progress_bar.progress(1.0)
    progress_text.caption("Scanner finished")

    scan_rows = scan_result.get("rows", [])
    scan_counts = scan_result.get("decision_counts", {})
    scan_filters = scan_result.get("filters", {})
    scan_df = pd.DataFrame(scan_rows)

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Simbolos analizados", scan_result.get("analyzed_count", 0))
    m2.metric("ENTER_NOW_CANDIDATE", scan_counts.get("ENTER_NOW_CANDIDATE", 0))
    m3.metric("WAIT", scan_counts.get("WAIT", 0))
    m4.metric("AVOID", scan_counts.get("AVOID", 0))
    m5.metric("Tiempo total", scan_result.get("elapsed_display", "-"))
    st.metric("Tiempo promedio por simbolo", scan_result.get("average_symbol_display", "-"))
    st.caption(
        "Modo scanner: {mode} | Timeframes: {timeframes} | Backtests ejecutados: {backtests} | Workers: {workers}".format(
            mode=scan_result.get("scan_mode", "-"),
            timeframes=", ".join(scan_result.get("timeframes", [])),
            backtests=scan_result.get("backtests_executed", 0),
            workers=scan_result.get("workers", 1),
        )
    )
    st.caption(
        "Filtros: stablecoins excluidas {stablecoins}; historial insuficiente {history}".format(
            stablecoins=scan_filters.get("stablecoins_excluded_count", 0),
            history=scan_filters.get("low_history_excluded_count", 0),
        )
    )

    table_cols = [
        "rank",
        "symbol",
        "decision",
        "validation_status",
        "recommended_timeframe",
        "score",
        "confidence",
        "rr_ratio",
        "quote_volume_24h",
        "entry_now_text",
        "main_reason",
        "backtest_verdict",
    ]

    if not scan_df.empty:
        visible_cols = [col for col in table_cols if col in scan_df.columns]
        pending_df = scan_df[scan_df["validation_status"] == "PENDING_BACKTEST"]
        candidates_df = scan_df[
            (scan_df["decision"] == "ENTER_NOW_CANDIDATE")
            & (scan_df["validation_status"] != "PENDING_BACKTEST")
        ]
        wait_df = scan_df[scan_df["decision"] == "WAIT"]

        st.subheader("Candidatos tecnicos pendientes de validacion")
        if not pending_df.empty:
            st.dataframe(pending_df[visible_cols], use_container_width=True, hide_index=True)
        else:
            st.info("Sin candidatos tecnicos pendientes de validacion.")

        st.subheader("Entradas candidatas validadas")
        if not candidates_df.empty:
            st.dataframe(candidates_df[visible_cols], use_container_width=True, hide_index=True)
        else:
            st.info("Sin entradas candidatas validadas ahora.")

        st.subheader("Setups en espera")
        if not wait_df.empty:
            st.dataframe(wait_df[visible_cols], use_container_width=True, hide_index=True)
        else:
            st.info("Sin setups en espera ahora.")

        with st.expander("Tabla completa del scanner", expanded=False):
            st.dataframe(scan_df, use_container_width=True, hide_index=True)
    else:
        st.info("El scanner no devolvio resultados.")

    scan_warnings = scan_result.get("warnings", [])
    if scan_warnings:
        with st.expander("Warnings del scan", expanded=False):
            for warning in scan_warnings:
                st.warning(warning)

    with st.expander("latest_scan.md", expanded=False):
        try:
            with open(scan_result.get("md_path"), "r", encoding="utf-8") as f:
                st.markdown(f.read())
        except Exception as e:
            st.warning(f"No se pudo leer latest_scan.md: {e}")

# ─── Validation & Signal Tracking ────────────────────────────────────────────

st.markdown("---")
st.subheader("Validation & Signal Tracking")

v_col1, v_col2 = st.columns(2)
with v_col1:
    val_top = st.number_input("Top candidates to validate", min_value=1, max_value=20, value=5)
    validate_btn = st.button("Validate top scanner candidates", use_container_width=True)
with v_col2:
    st.write("")
    st.write("")
    update_signals_btn = st.button("Update signal tracking", use_container_width=True)

if validate_btn:
    with st.spinner(f"Validating top {val_top} candidates..."):
        try:
            res = validator.run_validation(top_n=val_top)
            if res:
                st.success(f"Validación completada. Guardada en outputs/")
            else:
                st.warning("No se pudo realizar la validación. Revisa si hay scan results.")
        except Exception as e:
            st.error(_friendly_error(e, "Error during validation"))

if update_signals_btn:
    with st.spinner("Updating signals..."):
        try:
            res = signal_tracker.update_signals()
            st.success(f"Señales actualizadas: {res['updated']}, Cerradas: {res['closed']}.")
        except Exception as e:
            st.error(_friendly_error(e, "Error updating signals"))

st.markdown("---")
st.subheader("Run Full Cycle")
c_col1, c_col2, c_col3, c_col4 = st.columns(4)
with c_col1:
    cycle_limit = st.selectbox("Scan limit", [20, 50, 100], index=0, key="cycle_limit")
with c_col2:
    cycle_top = st.number_input("Top N to validate", min_value=1, max_value=20, value=3, key="cycle_top")
with c_col3:
    cycle_workers = st.selectbox("Workers", [1, 3, 5, 8], index=2, key="cycle_workers")
with c_col4:
    st.write("")
    cycle_btn = st.button("Run full cycle", type="primary", use_container_width=True)

if cycle_btn:
    with st.spinner("Running full cycle (Scan -> Validate -> Update Signals)..."):
        try:
            res = cycle_runner.run_cycle(scan_limit=cycle_limit, top_n=cycle_top, workers=cycle_workers)
            st.success(f"Ciclo completado en {res['total_time']:.2f}s.")
        except Exception as e:
            st.error(_friendly_error(e, "Error during cycle"))

v_tabs = st.tabs(["Validation Report", "Signal Status", "Cycle Summary"])

with v_tabs[0]:
    try:
        with open(os.path.join(config.OUTPUT_DIR, "latest_validation.md"), "r", encoding="utf-8") as f:
            st.markdown(f.read())
    except Exception:
        st.info("No validation report found. Run validation first.")

with v_tabs[1]:
    try:
        with open(os.path.join(config.OUTPUT_DIR, "signal_status.md"), "r", encoding="utf-8") as f:
            st.markdown(f.read())
    except Exception:
        st.info("No signal status report found. Run update signals first.")

with v_tabs[2]:
    try:
        with open(os.path.join(config.OUTPUT_DIR, "latest_cycle_summary.md"), "r", encoding="utf-8") as f:
            st.markdown(f.read())
    except Exception:
        st.info("No cycle summary found. Run a full cycle first.")

# ─── Analysis ────────────────────────────────────────────────────────────────

if analyze_btn:
    symbol = symbol_input.strip() or config.DEFAULT_SYMBOL
    use_auto = timeframe_select == "Auto timeframe"
    timeframe = None if use_auto else timeframe_select

    with st.spinner(f"Fetching data and analyzing {symbol}..."):
        try:
            if use_auto:
                result = technical_analyzer.analyze_symbol_auto(symbol)
                best = result.get("best_setup") or {}
                tf_results = result.get("timeframe_results", {})
                recommended_tf = result.get("recommended_timeframe", "?")
                main_decision = result.get("decision", "NO_DATA")
                global_warnings = result.get("warnings", [])
            else:
                result_tf = technical_analyzer.analyze_symbol_timeframe(symbol, timeframe)
                best = result_tf
                tf_results = {timeframe: result_tf}
                recommended_tf = timeframe
                main_decision = result_tf.get("decision", "NO_DATA")
                global_warnings = result_tf.get("warnings", [])
                result = result_tf

        except Exception as e:
            st.error(_friendly_error(e, "Error"))
            st.stop()

    if not result.get("analysis_time"):
        result["analysis_time"] = (
            (best or {}).get("analysis_time")
            or datetime.now(timezone.utc).isoformat()
        )

    bt_result = None
    if run_backtest:
        bt_tf = recommended_tf if use_auto else timeframe
        if use_auto and not recommended_tf:
            st.info("Auto no encontró temporalidad clara; no se ejecuta backtest principal.")
        elif bt_tf:
            with st.spinner(f"Running backtest {symbol} / {bt_tf}..."):
                try:
                    bt_result = backtester.run_quick_backtest(symbol, bt_tf)
                except Exception as e:
                    st.warning(_friendly_error(e, "Backtest failed"))

    if bt_result:
        result = technical_analyzer.apply_backtest_to_analysis(result, bt_result)
        best = result.get("best_setup") or result
        recommended_tf = result.get("recommended_timeframe")
        main_decision = result.get("decision", "NO_DATA")
        global_warnings = result.get("warnings", [])

    # Save report
    try:
        md_path, csv_path, md_text = report_builder.save_report(
            result,
            bt_result,
            return_content=True,
        )
        report_metadata = report_builder.get_report_metadata(result)
    except Exception as e:
        st.error(
            "No se pudo regenerar outputs/latest_analysis.md y "
            f"outputs/latest_analysis.csv: {e}"
        )
        st.stop()

    st.markdown("---")

    # ─── Decision card ───────────────────────────────────────────────────────

    dec_emoji = utils.decision_emoji(main_decision)
    plan = result if result.get("action_summary") else best
    display_symbol = result.get("symbol", symbol)
    display_tf = recommended_tf or ("ninguna clara" if use_auto else timeframe or "-")
    decision_card = (
        f"### {display_symbol} · {dec_emoji} {main_decision}\n\n"
        f"**Timeframe recomendado:** {display_tf}  \n"
        f"**Plan:** {plan.get('action_summary', '-')}  \n"
        f"**{plan.get('entry_now_text', 'Entrada ahora: no recomendable')}**  \n"
        f"**Motivo principal:** {plan.get('main_reason', '-')}"
    )

    if main_decision == "ENTER_NOW_CANDIDATE":
        st.success(decision_card)
    elif main_decision == "WAIT":
        st.warning(decision_card)
    elif main_decision == "AVOID":
        st.error(decision_card)
    else:
        st.info(decision_card)

    top_backtest_warning = _backtest_warning(result, bt_result)
    if top_backtest_warning:
        st.warning(top_backtest_warning)

    # Key metrics row
    k1, k2, k3, k4, k5 = st.columns(5)
    score = best.get("score", 0)
    score_max = best.get("score_max", 10)
    confidence = best.get("confidence", 0)
    rr = best.get("rr_ratio", 0)
    vol_ratio = best.get("vol_ratio")

    k1.metric("Timeframe", display_tf)
    k2.metric("Score", f"{score}/{score_max}")
    k3.metric("Confianza", f"{confidence}%")
    k4.metric("RR", f"{rr:.2f}" if rr else "-")
    k5.metric("Vol Ratio", f"{vol_ratio:.2f}x" if vol_ratio else "N/A")

    if result.get("no_clear_setup"):
        st.warning("Auto timeframe: NO_CLEAR_SETUP. No hay temporalidad principal clara ahora.")
    if result.get("auto_observation"):
        st.info(result.get("auto_observation"))

    if best.get("closed_candle_vol_ratio") is not None:
        vc1, vc2, vc3 = st.columns(3)
        vc1.metric("Vol vela cerrada", f"{best.get('closed_candle_vol_ratio'):.2f}x")
        intra_vol = best.get("intracandle_vol_ratio")
        vc2.metric("Vol intravela", f"{intra_vol:.2f}x" if intra_vol is not None else "N/A")
        adjusted_vol = best.get("adjusted_intracandle_vol_ratio")
        vc3.metric("Vol intravela ajustado", f"{adjusted_vol:.2f}x" if adjusted_vol is not None else "N/A")

    if best.get("volume_warning"):
        st.info(best.get("volume_warning"))

    global_warnings = _unique_items(global_warnings)
    if top_backtest_warning:
        global_warnings = [w for w in global_warnings if w != top_backtest_warning]
    if global_warnings:
        for w in global_warnings:
            st.warning(f"⚠️ {w}")

    st.markdown("---")

    # ─── Multi-timeframe table ────────────────────────────────────────────────

    if use_auto and tf_results:
        st.subheader("📋 Multi-Timeframe Overview")
        rows = []
        for tf, r in tf_results.items():
            if r.get("decision") == "NO_DATA":
                continue
            reas = r.get("reasons", [])
            main_reason = reas[0] if reas else r.get("missing_conditions", [""])[0]
            rows.append({
                "TF": tf,
                "Decision": r.get("decision", "-"),
                "Score": f"{r.get('score', 0)}/{r.get('score_max', 10)}",
                "Price": utils.format_price(r.get("price")),
                "RSI": r.get("rsi"),
                "EMA200": utils.format_price(r.get("ema200")),
                "Vol Ratio": r.get("closed_candle_vol_ratio", r.get("vol_ratio")),
                "RR": r.get("rr_ratio"),
                "Main Reason": r.get("main_reason") or (main_reason[:60] if main_reason else "-"),
            })

        if rows:
            df_table = pd.DataFrame(rows)
            st.dataframe(df_table, use_container_width=True, hide_index=True)

    # ─── Levels ──────────────────────────────────────────────────────────────

    st.subheader("Plan de entrada")
    lc1, lc2 = st.columns(2)

    with lc1:
        entry = best.get("estimated_entry")
        sl = best.get("estimated_stop_loss")
        tp = best.get("estimated_take_profit")
        risk_pct = best.get("risk_pct")
        reward_pct = best.get("reward_pct")

        st.metric("Entrada estimada", utils.format_price(entry))
        st.metric("Stop Loss", utils.format_price(sl),
                  delta=f"-{risk_pct:.2f}%" if risk_pct else None,
                  delta_color="inverse")
        st.metric("Take Profit", utils.format_price(tp),
                  delta=f"+{reward_pct:.2f}%" if reward_pct else None)

    with lc2:
        nearest_sup = best.get("nearest_support")
        nearest_res = best.get("nearest_resistance")
        dist_sup = best.get("distance_to_support_pct")
        dist_res = best.get("distance_to_resistance_pct")

        st.metric("Soporte cercano", utils.format_price(nearest_sup),
                  delta=f"{dist_sup:.2f}%" if dist_sup is not None else None,
                  delta_color="normal")
        st.metric("Resistencia cercana", utils.format_price(nearest_res),
                  delta=f"+{dist_res:.2f}%" if dist_res is not None else None)
        st.metric("RR Ratio", f"{rr:.2f}" if rr else "-")

    st.markdown(f"**Gatillo de entrada:** {plan.get('entry_trigger', '-')}")
    st.markdown(f"**Invalidación:** {plan.get('invalidation_level', '-')}")

    st.markdown("---")

    st.subheader("Qué falta para entrar")
    needs = plan.get("what_needs_to_happen", [])
    if needs:
        for item in needs:
            st.markdown(f"- {item}")
    else:
        st.markdown("_Nada crítico según el scoring actual; respetar invalidación y gestión de riesgo._")

    st.markdown("---")

    # ─── Reasons / Missing / Warnings ────────────────────────────────────────

    reasons = _unique_items(best.get("reasons", []))
    missing = _unique_items(best.get("missing_conditions", []))
    warnings_local = _unique_items(best.get("warnings", []))
    if top_backtest_warning:
        warnings_local = [w for w in warnings_local if w != top_backtest_warning]

    rc1, rc2, rc3 = st.columns(3)

    with rc1:
        st.subheader("✅ Razones a favor")
        if reasons:
            for r in reasons:
                st.markdown(f"- {r}")
        else:
            st.markdown("_Ninguna_")

    with rc2:
        st.subheader("⏳ Condiciones faltantes")
        if missing:
            for m in missing:
                st.markdown(f"- {m}")
        else:
            st.markdown("_Ninguna_")

    with rc3:
        st.subheader("⚠️ Advertencias")
        if warnings_local:
            for w in warnings_local:
                st.markdown(f"- {w}")
        else:
            st.markdown("_Ninguna_")

    st.markdown("---")

    # ─── Backtest ─────────────────────────────────────────────────────────────

    if bt_result:
        bt_display_tf = bt_result.get("timeframe") or recommended_tf or "ninguna clara"
        if use_auto:
            st.subheader(f"Backtest rápido del timeframe recomendado: {bt_display_tf}")
        else:
            st.subheader(f"Backtest rápido: {bt_display_tf}")
        verdict = bt_result.get("verdict", "N/A")
        v_emoji = utils.verdict_emoji(verdict)

        if verdict == "BACKTEST_OK":
            st.success(f"{v_emoji} {verdict}")
        elif verdict == "BACKTEST_WEAK":
            st.warning(f"{v_emoji} {verdict}")
        elif verdict in ("BACKTEST_BAD", "NO_DATA"):
            st.error(f"{v_emoji} {verdict}")
        else:
            st.info(f"{v_emoji} {verdict}")

        bc1, bc2, bc3, bc4, bc5 = st.columns(5)
        bc1.metric("Trades", bt_result.get("n_trades", 0))
        bc2.metric("Win Rate", f"{bt_result.get('win_rate', 0):.1f}%")
        bc3.metric("Profit Factor", f"{bt_result.get('profit_factor', 0):.3f}")
        bc4.metric("Retorno total", f"{bt_result.get('total_return_pct', 0):.2f}%")
        bc5.metric("Max Drawdown", f"{bt_result.get('max_drawdown_pct', 0):.2f}%")

        st.markdown("---")

    # ─── Report ──────────────────────────────────────────────────────────────

    if md_path:
        st.subheader("📄 Reporte")
        r1, r2, r3 = st.columns(3)
        r1.metric("Símbolo analizado", report_metadata["symbol"])
        r2.metric(report_metadata["timeframe_label"], report_metadata["timeframe"])
        r3.metric("Fecha/hora del análisis", report_metadata["analysis_time_display"])

        try:
            with open(md_path, "r", encoding="utf-8") as f:
                disk_md_text = f.read()
            if not report_builder.markdown_matches_symbol(
                disk_md_text,
                report_metadata["symbol"],
            ):
                st.warning(
                    "El reporte en disco no coincide con el análisis actual. Regenerá el análisis."
                )
        except Exception as e:
            st.warning(f"No se pudo leer el reporte en disco: {e}")

        with st.expander("Ver reporte completo (Markdown)", expanded=False):
            st.markdown(md_text)

    st.markdown("---")
    st.caption("⚠️ Solo análisis técnico. No es consejo financiero. No se envían órdenes. Solo spot.")
