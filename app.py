import logging
import os
import traceback
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

import backtester
import config
import cycle_runner
import diagnostics
import futures_analyzer
import report_builder
import scanner
import signal_tracker
import technical_analyzer
import utils
import validator


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
DEBUG_UI = os.getenv("DEBUG_UI", "false").lower() == "true"

EXCHANGE_LABELS = {
    "bingx": "BingX",
    "kraken": "Kraken",
    "kucoin": "KuCoin",
    "okx": "OKX",
    "binance": "Binance",
}


def _exchange_label(exchange_id: str) -> str:
    return EXCHANGE_LABELS.get(str(exchange_id).lower(), str(exchange_id))


def _exchange_id_from_label(label: str) -> str:
    reverse = {value: key for key, value in EXCHANGE_LABELS.items()}
    return reverse.get(label, str(label).lower())


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
    text = f"{type(error).__name__}: {error}".lower()
    if "data_unavailable" in text:
        return "No se pudieron obtener datos desde los exchanges configurados."
    if _is_binance_network_error(error):
        return "No se pudo consultar Binance. Proba de nuevo en unos minutos."
    return f"{fallback}: {error}"


def _show_action_error(error: Exception, fallback: str, level: str = "error") -> None:
    logger.exception("Streamlit action failed")
    details = traceback.format_exc()
    print(details, flush=True)
    message = _friendly_error(error, fallback)
    if level == "warning":
        st.warning(message)
    else:
        st.error(message)
    st.caption(f"Error type: {type(error).__name__}")
    if DEBUG_UI:
        with st.expander("Detalles técnicos", expanded=False):
            st.code(details)


def render_decision_badge(decision, direction=None):
    value = direction if direction in ("LONG", "SHORT") else decision
    if value in ("ENTER_NOW_CANDIDATE", "LONG", "SHORT"):
        return f"🟢 {value}"
    if value == "WAIT":
        return "🟡 WAIT"
    if value == "AVOID":
        return "🔴 AVOID"
    if value == "DATA_UNAVAILABLE":
        return "⚪ DATA_UNAVAILABLE"
    return f"⚪ {value or 'N/A'}"


def _spot_best(result: dict) -> dict:
    return result.get("best_setup") or result or {}


def _spot_plan(result: dict) -> dict:
    best = _spot_best(result)
    return result if result.get("action_summary") else best


def _spot_entry_text(result: dict) -> str:
    plan = _spot_plan(result)
    text = plan.get("entry_now_text") or "Entrada ahora: no recomendable"
    prefix = "Entrada ahora:"
    if text.lower().startswith(prefix.lower()):
        text = text[len(prefix):].strip()
    return text or "no recomendable"


def render_action_hint(result, mode):
    decision = result.get("decision")
    if mode == "SPOT":
        hints = {
            "ENTER_NOW_CANDIDATE": "Setup técnico candidato. Validar con backtest/validation antes de tomarlo como señal paper.",
            "WAIT": "Esperar confirmación. No hay entrada inmediata.",
            "AVOID": "No hay setup claro ahora.",
            "DATA_UNAVAILABLE": "No se pudieron obtener datos del exchange.",
            "NO_DATA": "No se pudieron obtener datos suficientes.",
        }
    else:
        hints = {
            "LONG": "Sesgo long detectado. Revisar SL, TP y riesgo antes de considerar una señal paper.",
            "SHORT": "Sesgo short detectado. Revisar SL, TP y riesgo antes de considerar una señal paper.",
            "WAIT": "Hay dirección posible, pero falta confirmación.",
            "AVOID": "No hay ventaja técnica clara para long ni short.",
            "DATA_UNAVAILABLE": "No se pudieron obtener datos del exchange.",
        }
    st.subheader("Qué hago ahora")
    st.info(hints.get(decision, "Revisar el resumen técnico antes de actuar."))


def _summary_box(markdown: str, decision: str):
    if decision in ("ENTER_NOW_CANDIDATE", "LONG", "SHORT"):
        st.success(markdown)
    elif decision == "WAIT":
        st.warning(markdown)
    elif decision == "AVOID":
        st.error(markdown)
    else:
        st.info(markdown)


def render_result_summary(result, mode):
    if mode == "SPOT":
        best = _spot_best(result)
        plan = _spot_plan(result)
        decision = result.get("decision", "NO_DATA")
        display_tf = result.get("recommended_timeframe") or result.get("timeframe") or "ninguna clara"
        badge = render_decision_badge(decision)
        card = (
            f"### {badge}\n\n"
            f"**Timeframe recomendado:** {display_tf}  \n"
            f"**Entrada ahora:** {_spot_entry_text(result)}  \n"
            f"**Motivo principal:** {plan.get('main_reason', 'N/A')}"
        )
        _summary_box(card, decision)

        c1, c2, c3 = st.columns(3)
        c1.metric("Score", f"{best.get('score', 0)}/{best.get('score_max', 10)}")
        c2.metric("Confianza", f"{best.get('confidence', 0)}%")
        c3.metric("Precio", utils.format_price(best.get("price")))

        p1, p2, p3, p4 = st.columns(4)
        p1.metric("Entry", utils.format_price(best.get("estimated_entry")))
        p2.metric("Stop Loss", utils.format_price(best.get("estimated_stop_loss")))
        p3.metric("Take Profit", utils.format_price(best.get("estimated_take_profit")))
        p4.metric("RR", best.get("rr_ratio") or "N/A")

        source = result.get("data_source_exchange") or best.get("data_source_exchange")
        fallback = result.get("fallback_used") or best.get("fallback_used") or False
        e1, e2 = st.columns(2)
        e1.metric("Exchange real", source or "N/A")
        e2.metric("Fallback used", "sí" if fallback else "no")
        return

    decision = result.get("decision", "DATA_UNAVAILABLE")
    direction = result.get("direction", "NEUTRAL")
    badge = render_decision_badge(decision, direction)
    display_tf = result.get("recommended_timeframe") or result.get("timeframe") or "ninguna clara"
    card = (
        f"### {badge}\n\n"
        f"**Timeframe recomendado:** {display_tf}  \n"
        f"**Entrada ahora:** {'sí' if result.get('entry_now') else 'no'}  \n"
        f"**Motivo principal:** {result.get('main_reason', 'N/A')}"
    )
    _summary_box(card, decision)

    c1, c2, c3 = st.columns(3)
    c1.metric("Long score", f"{result.get('long_score', 0)}/10")
    c2.metric("Short score", f"{result.get('short_score', 0)}/10")
    c3.metric("RR", result.get("rr_ratio") or "N/A")

    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Entry", utils.format_price(result.get("entry_price")))
    p2.metric("Stop Loss", utils.format_price(result.get("stop_loss")))
    p3.metric("TP1", utils.format_price(result.get("take_profit_1")))
    p4.metric("TP2", utils.format_price(result.get("take_profit_2")))

    r1, r2, r3 = st.columns(3)
    risk = result.get("risk_pct_to_stop")
    r1.metric("Riesgo al stop", f"{risk}%" if risk is not None else "N/A")
    r2.metric("Leverage sugerido", result.get("suggested_leverage_label") or "N/A")
    r3.metric("Exchange real", result.get("data_source_exchange") or "N/A")
    st.caption(f"Fallback used: {'sí' if result.get('fallback_used') else 'no'}")
    if result.get("leverage_warning"):
        st.warning(result.get("leverage_warning"))


def render_advanced_details(result, mode):
    best = _spot_best(result) if mode == "SPOT" else result
    plan = _spot_plan(result) if mode == "SPOT" else result

    with st.expander("Razones", expanded=False):
        items = _unique_items(best.get("reasons", []) or result.get("reasons", []))
        if items:
            for item in items:
                st.markdown(f"- {item}")
        else:
            st.caption("Sin razones detalladas.")

    with st.expander("Condiciones faltantes", expanded=False):
        items = _unique_items(plan.get("what_needs_to_happen", []) or result.get("missing_conditions", []) or best.get("missing_conditions", []))
        if items:
            for item in items:
                st.markdown(f"- {item}")
        else:
            st.caption("Sin condiciones faltantes.")

    with st.expander("Advertencias", expanded=False):
        items = _unique_items(_unique_items(best.get("warnings", [])) + _unique_items(result.get("warnings", [])))
        if items:
            for item in items:
                st.markdown(f"- {item}")
        else:
            st.caption("Sin advertencias.")

    with st.expander("Datos de exchange", expanded=False):
        st.write({
            "data_source_exchange": result.get("data_source_exchange") or best.get("data_source_exchange"),
            "exchange_mode": result.get("exchange_mode") or best.get("exchange_mode"),
            "fallback_used": result.get("fallback_used") or best.get("fallback_used"),
            "data_source_error": result.get("data_source_error") or best.get("data_source_error"),
        })

    with st.expander("Detalles técnicos", expanded=False):
        if mode == "SPOT":
            st.write({
                "RSI": best.get("rsi"),
                "EMA20": best.get("ema20"),
                "EMA50": best.get("ema50"),
                "EMA200": best.get("ema200"),
                "ATR": best.get("atr"),
                "Vol ratio": best.get("closed_candle_vol_ratio", best.get("vol_ratio")),
                "Soporte": best.get("nearest_support"),
                "Resistencia": best.get("nearest_resistance"),
            })
        else:
            st.write({
                "RSI": result.get("rsi"),
                "EMA20": result.get("ema20"),
                "EMA50": result.get("ema50"),
                "EMA200": result.get("ema200"),
                "ATR": result.get("atr"),
                "ATR %": result.get("atr_pct"),
                "Vol ratio": result.get("vol_ratio"),
                "Soporte": result.get("nearest_support"),
                "Resistencia": result.get("nearest_resistance"),
                "Invalidación": result.get("invalidation"),
            })

    if DEBUG_UI:
        with st.expander("Raw result dict", expanded=False):
            st.json(result)


def futures_unavailable_notice():
    st.info("El scanner futures todavía no está disponible. Usá Analyze para evaluar LONG/SHORT en un símbolo.")


st.set_page_config(
    page_title="Crypto Technical Advisor",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.title("Crypto Technical Advisor")
st.caption("Paper/analysis only. No live trading. No financial advice.")

exchange_options = [_exchange_label(exchange) for exchange in config.SUPPORTED_EXCHANGES]
default_exchange_index = config.SUPPORTED_EXCHANGES.index(config.DEFAULT_EXCHANGE)

g1, g2 = st.columns([1, 2])
with g1:
    selected_mode = st.radio("Mode", ["SPOT", "FUTURES"], index=0, horizontal=True)
with g2:
    selected_symbol = st.text_input("Symbol", value="BTC/USDT", placeholder="BTC/USDT")

g3, g4 = st.columns(2)
with g3:
    selected_exchange_label = st.selectbox("Exchange", exchange_options, index=default_exchange_index)
with g4:
    selected_exchange_mode_label = st.selectbox("Exchange mode", ["Manual", "Fallback"], index=0)

selected_exchange = _exchange_id_from_label(selected_exchange_label)
selected_exchange_mode = selected_exchange_mode_label.lower()

tf_options = config.TIMEFRAMES if selected_mode == "SPOT" else futures_analyzer.FUTURES_TIMEFRAMES
g5, g6 = st.columns(2)
with g5:
    timeframe_mode = st.radio("Timeframe mode", ["Auto", "Manual"], index=0, horizontal=True)
with g6:
    selected_timeframe = st.selectbox("Timeframe", tf_options, index=tf_options.index("1h") if "1h" in tf_options else 0, disabled=timeframe_mode == "Auto")

if selected_exchange_mode == "fallback":
    st.caption("Fallback mode tries the configured exchange priority.")
else:
    st.caption(f"Manual mode uses only {_exchange_label(selected_exchange)}.")

analyze_tab, scanner_tab, validate_tab, signals_tab, cycle_tab, diagnostics_tab = st.tabs([
    "Analyze",
    "Market Scanner",
    "Validate",
    "Signals",
    "Full Cycle",
    "Diagnostics",
])

with analyze_tab:
    symbol = selected_symbol.strip() or "BTC/USDT"
    use_auto = timeframe_mode == "Auto"
    st.subheader(f"{selected_mode} Analyze")

    if selected_mode == "FUTURES":
        st.warning(
            "Futures tiene riesgo elevado por apalancamiento y liquidación. "
            "Esta herramienta es solo análisis técnico/paper, no consejo financiero."
        )

    button_label = "Analyze SPOT" if selected_mode == "SPOT" else "Analyze FUTURES"
    if st.button(button_label, type="primary", use_container_width=True):
        with st.spinner(f"Analyzing {selected_mode} {symbol}..."):
            try:
                if selected_mode == "SPOT":
                    if use_auto:
                        result = technical_analyzer.analyze_symbol_auto(
                            symbol,
                            exchange_id=selected_exchange,
                            exchange_mode=selected_exchange_mode,
                        )
                    else:
                        result = technical_analyzer.analyze_symbol_timeframe(
                            symbol,
                            selected_timeframe,
                            exchange_id=selected_exchange,
                            exchange_mode=selected_exchange_mode,
                        )
                    if not result.get("analysis_time"):
                        result["analysis_time"] = datetime.now(timezone.utc).isoformat()
                    try:
                        report_builder.save_report(result, None)
                    except Exception as report_error:
                        st.caption(f"No se pudo guardar latest_analysis: {report_error}")
                else:
                    if use_auto:
                        result = futures_analyzer.analyze_futures_symbol_auto(
                            symbol,
                            exchange_id=selected_exchange,
                            exchange_mode=selected_exchange_mode,
                        )
                    else:
                        result = futures_analyzer.analyze_futures_symbol_timeframe(
                            symbol,
                            selected_timeframe,
                            exchange_id=selected_exchange,
                            exchange_mode=selected_exchange_mode,
                        )
            except Exception as e:
                _show_action_error(e, f"{selected_mode} analysis failed")
                st.stop()

        render_action_hint(result, selected_mode)
        render_result_summary(result, selected_mode)
        render_advanced_details(result, selected_mode)

with scanner_tab:
    if selected_mode == "FUTURES":
        futures_unavailable_notice()
    else:
        st.info("Scanner: busca oportunidades actuales en el mercado. No valida todavía con backtest completo salvo que lo actives.")
        s1, s2 = st.columns(2)
        with s1:
            scan_limit = st.number_input(
                "Cantidad de monedas a escanear",
                min_value=5,
                max_value=100,
                value=20,
                step=5,
                key="scan_limit",
            )
        with s2:
            scan_mode_label = st.selectbox("Scan mode", ["Fast", "Full"], index=0)

        s3, s4 = st.columns(2)
        with s3:
            scan_workers = st.selectbox("Workers", [1, 3, 5, 8], index=2)
        with s4:
            scan_backtest_top = st.selectbox("Backtest top N", [0, 3, 5, 10], index=0)

        if st.button("Run scanner", type="primary", use_container_width=True):
            progress_bar = st.progress(0)
            progress_text = st.empty()

            def update_scan_progress(current, total, message):
                pct = 0 if not total else min(max(current / total, 0), 1)
                progress_bar.progress(pct)
                progress_text.caption(message)

            with st.spinner("Scanning top USDT spot pairs..."):
                try:
                    scan_result = scanner.run_scan(
                        limit=int(scan_limit),
                        backtest_top_n=scan_backtest_top,
                        mode=scan_mode_label.lower(),
                        workers=scan_workers,
                        progress_callback=update_scan_progress,
                        exchange_id=selected_exchange,
                        exchange_mode=selected_exchange_mode,
                    )
                except Exception as e:
                    _show_action_error(e, "Scanner failed")
                    st.stop()

            progress_bar.progress(1.0)
            progress_text.caption("Scanner finished")
            counts = scan_result.get("decision_counts", {})
            c1, c2, c3 = st.columns(3)
            c1.metric("Analizadas", scan_result.get("analyzed_count", 0))
            c2.metric("ENTER", counts.get("ENTER_NOW_CANDIDATE", 0))
            c3.metric("WAIT", counts.get("WAIT", 0))
            c4, c5, c6 = st.columns(3)
            c4.metric("AVOID", counts.get("AVOID", 0))
            c5.metric("Tiempo total", scan_result.get("elapsed_display", "-"))
            c6.metric("Exchange", scan_result.get("data_source_exchange") or "N/A")
            st.caption(f"Fallback used: {'sí' if scan_result.get('fallback_used') else 'no'}")

            rows = scan_result.get("rows", [])
            if rows:
                preview_cols = ["rank", "symbol", "decision", "validation_status", "recommended_timeframe", "score", "confidence", "rr_ratio"]
                preview_df = pd.DataFrame(rows)
                visible_cols = [col for col in preview_cols if col in preview_df.columns]
                st.dataframe(preview_df[visible_cols].head(10), use_container_width=True, hide_index=True)
                with st.expander("Tabla completa", expanded=False):
                    st.dataframe(preview_df, use_container_width=True, hide_index=True)
            else:
                st.info("El scanner no devolvió resultados.")

            if scan_result.get("warnings"):
                with st.expander("Warnings", expanded=False):
                    for warning in scan_result.get("warnings", []):
                        st.warning(warning)

with validate_tab:
    if selected_mode == "FUTURES":
        futures_unavailable_notice()
    else:
        st.info("Valida los mejores candidatos del último scan. No vuelve a escanear el mercado.")
        top_n = st.number_input("Top N a validar", min_value=1, max_value=20, value=3, step=1)
        if st.button("Validate latest scan", type="primary", use_container_width=True):
            with st.spinner(f"Validating top {top_n} candidates..."):
                try:
                    res = validator.run_validation(top_n=int(top_n))
                    if res:
                        st.success(f"Validación guardada en {res['md_path']}")
                    else:
                        st.warning("No se pudo validar. Revisá si existe outputs/latest_scan.csv.")
                except Exception as e:
                    _show_action_error(e, "Error during validation")
            try:
                with open(os.path.join(config.OUTPUT_DIR, "latest_validation.md"), "r", encoding="utf-8") as f:
                    st.markdown(f.read())
            except Exception:
                st.info("No validation report found.")

with signals_tab:
    if selected_mode == "FUTURES":
        st.info("Las señales paper actuales pertenecen al flujo SPOT.")
    st.info("Actualiza señales paper abiertas y revisa TP, SL o expiración.")
    if st.button("Update open signals", type="primary", use_container_width=True):
        with st.spinner("Updating open signals..."):
            try:
                res = signal_tracker.update_signals()
                st.success(f"Actualizadas: {res['updated']}, cerradas: {res['closed']}.")
            except Exception as e:
                _show_action_error(e, "Error updating signals")
        try:
            with open(os.path.join(config.OUTPUT_DIR, "signal_status.md"), "r", encoding="utf-8") as f:
                st.markdown(f.read())
        except Exception:
            st.info("No signal status report found.")

with cycle_tab:
    if selected_mode == "FUTURES":
        futures_unavailable_notice()
    else:
        st.info("Ejecuta todo desde cero: scanner + validación + actualización de señales.")
        c1, c2 = st.columns(2)
        with c1:
            cycle_limit = st.number_input("Scan limit", min_value=5, max_value=100, value=20, step=5, key="cycle_limit")
        with c2:
            cycle_top = st.number_input("Top N", min_value=1, max_value=20, value=3, step=1, key="cycle_top")
        cycle_workers = st.selectbox("Workers", [1, 3, 5, 8], index=2, key="cycle_workers")
        if st.button("Run full cycle", type="primary", use_container_width=True):
            with st.spinner("Running full cycle..."):
                try:
                    res = cycle_runner.run_cycle(
                        scan_limit=int(cycle_limit),
                        top_n=int(cycle_top),
                        workers=cycle_workers,
                        exchange_id=selected_exchange,
                        exchange_mode=selected_exchange_mode,
                    )
                    st.success(f"Ciclo completado en {res['total_time']:.2f}s.")
                except Exception as e:
                    _show_action_error(e, "Error during cycle")
            try:
                with open(os.path.join(config.OUTPUT_DIR, "latest_cycle_summary.md"), "r", encoding="utf-8") as f:
                    st.markdown(f.read())
            except Exception:
                st.info("No cycle summary found.")

with diagnostics_tab:
    st.info("Diagnostics explícitos. Los detalles técnicos se muestran solo aquí o con DEBUG_UI=true.")
    if st.button("Test exchanges", type="primary", use_container_width=True):
        with st.spinner("Testing exchange availability..."):
            try:
                exchange_rows = diagnostics.run_exchange_diagnostics()
            except Exception as e:
                _show_action_error(e, "Exchange diagnostics failed")
                exchange_rows = []

        if exchange_rows:
            exchange_df = pd.DataFrame(exchange_rows)
            st.dataframe(exchange_df, use_container_width=True, hide_index=True)
            failed_rows = exchange_df[
                (exchange_df["load_markets"] == "FAIL")
                | (exchange_df["ticker"] == "FAIL")
                | (exchange_df["ohlcv"] == "FAIL")
            ]
            if not failed_rows.empty:
                with st.expander("Errores técnicos", expanded=False):
                    for _, row in failed_rows.iterrows():
                        st.markdown(f"**{row['exchange']}**")
                        st.code(row.get("error") or "")
