import logging
import os
import platform
import traceback
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

import backtester
import config
import cycle_runner
import diagnostics
import futures_analyzer
import paper_trader
import report_builder
import scanner
import signal_tracker
import storage
import technical_analyzer
import utils
import validator
import performance_metrics
from paper_trader import PaperTrader


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
DEBUG_UI = os.getenv("DEBUG_UI", "false").lower() == "true"

EXCHANGE_LABELS = {
    "kucoin": "KuCoin",
    "binance": "Binance",
}


def _exchange_label(exchange_id: str) -> str:
    return EXCHANGE_LABELS.get(str(exchange_id).lower(), str(exchange_id))


def _exchange_id_from_label(label: str) -> str:
    reverse = {value: key for key, value in EXCHANGE_LABELS.items()}
    return reverse.get(label, str(label).lower())


# Helper aliases
_unique_items = utils.unique_items


def safe_unique_values(df, column):
    if df is None:
        return []
    if getattr(df, "empty", True):
        return []
    if column not in df.columns:
        return []
    values = df[column].dropna().unique().tolist()
    return sorted([str(v) for v in values if str(v).strip()])


def safe_union_unique(df_a, df_b, column):
    return sorted(
        set(safe_unique_values(df_a, column)) |
        set(safe_unique_values(df_b, column))
    )


def ensure_columns(df, columns):
    if df is None:
        df = pd.DataFrame()

    df = df.copy()

    for col in columns:
        if col not in df.columns:
            df[col] = None

    return df


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
        e1, e2, e3 = st.columns(3)
        e1.metric("Exchange real", source or "N/A")
        e2.metric("Market type", result.get("market_type") or best.get("market_type") or "spot")
        e3.metric("Fallback used", "sí" if fallback else "no")
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

    r1, r2, r3, r4 = st.columns(4)
    risk = result.get("risk_pct_to_stop")
    r1.metric("Riesgo al stop", f"{risk}%" if risk is not None else "N/A")
    r2.metric("Leverage sugerido", result.get("suggested_leverage_label") or "N/A")
    r3.metric("Exchange real", result.get("data_source_exchange") or "N/A")
    r4.metric("Market type", result.get("market_type") or result.get("data_source_market_type") or "futures")
    st.caption(f"Fallback used: {'sí' if result.get('fallback_used') else 'no'}")
    if result.get("market_symbol"):
        st.caption(f"Símbolo real de mercado: {result.get('market_symbol')}")
    if result.get("leverage_warning"):
        st.warning(result.get("leverage_warning"))


def _metric_display(value, suffix: str = "") -> str:
    """
    Formatea una métrica para la UI usando N/A cuando no hay valor.

    Parámetros:
        value: Valor numérico o textual a mostrar.
        suffix: Texto opcional para agregar al final, como "%".

    Retorno:
        String listo para usar en st.metric.

    Ejemplo:
        texto = _metric_display(None, "%")
    """
    if value is None:
        return "N/A"
    return f"{value}{suffix}"


def render_backtest_metrics(backtest_result: dict) -> None:
    """
    Muestra las métricas principales de un backtest rápido en Streamlit.

    Parámetros:
        backtest_result: Dict retornado por backtester.run_quick_backtest().

    Retorno:
        None. Renderiza las métricas directamente en la app.

    Ejemplo:
        render_backtest_metrics(backtester.run_quick_backtest("BTC/USDT", "4h"))
    """
    if not backtest_result:
        return

    st.subheader("Backtest rápido")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Trades", _metric_display(backtest_result.get("n_trades")))
    c2.metric("Win rate", _metric_display(backtest_result.get("win_rate"), "%"))
    c3.metric("Profit factor", _metric_display(backtest_result.get("profit_factor")))
    c4.metric("Return", _metric_display(backtest_result.get("total_return_pct"), "%"))

    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Max DD", _metric_display(backtest_result.get("max_drawdown_pct"), "%"))
    r2.metric("Sharpe", _metric_display(backtest_result.get("sharpe_ratio")))
    r3.metric("Calmar", _metric_display(backtest_result.get("calmar_ratio")))
    r4.metric("Loss streak", _metric_display(backtest_result.get("consecutive_losses_max")))

    q1, q2, q3, q4 = st.columns(4)
    q1.metric("Avg R", _metric_display(backtest_result.get("avg_r_multiple")))
    q2.metric("Expectancy R", _metric_display(backtest_result.get("expectancy_r")))
    q3.metric("Gap losses", _metric_display(backtest_result.get("gap_losses")))
    risk_per_trade = backtest_result.get("risk_per_trade_pct")
    risk_per_trade_display = round(risk_per_trade * 100, 3) if risk_per_trade is not None else None
    q4.metric("Risk/trade", _metric_display(risk_per_trade_display, "%"))


def render_advanced_details(result, mode):
    best = _spot_best(result) if mode == "SPOT" else result
    plan = _spot_plan(result) if mode == "SPOT" else result

    with st.expander("Razones", expanded=False):
        items = utils.unique_items(best.get("reasons", []) or result.get("reasons", []))
        if items:
            for item in items:
                st.markdown(f"- {item}")
        else:
            st.caption("Sin razones detalladas.")

    with st.expander("Condiciones faltantes", expanded=False):
        items = utils.unique_items(plan.get("what_needs_to_happen", []) or result.get("missing_conditions", []) or best.get("missing_conditions", []))
        if items:
            for item in items:
                st.markdown(f"- {item}")
        else:
            st.caption("Sin condiciones faltantes.")

    with st.expander("Advertencias", expanded=False):
        items = utils.unique_items(utils.unique_items(best.get("warnings", [])) + utils.unique_items(result.get("warnings", [])))
        if items:
            for item in items:
                st.markdown(f"- {item}")
        else:
            st.caption("Sin advertencias.")

    with st.expander("Datos de exchange", expanded=False):
        st.write({
            "data_source_exchange": result.get("data_source_exchange") or best.get("data_source_exchange"),
            "exchange_mode": result.get("exchange_mode") or best.get("exchange_mode"),
            "market_type": result.get("market_type") or best.get("market_type"),
            "market_symbol": result.get("market_symbol") or best.get("market_symbol"),
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


def _paper_report_path(filename: str) -> str:
    return os.path.join(config.OUTPUT_DIR, filename)


def _get_paper_trader() -> PaperTrader:
    if "paper_trader" not in st.session_state:
        st.session_state["paper_trader"] = PaperTrader.load_from_report(
            exchange_id=selected_exchange,
            capital_usdt=1000.0,
        )
    return st.session_state["paper_trader"]


def _hours_since(dt_value) -> str:
    try:
        dt = pd.to_datetime(dt_value, utc=True).to_pydatetime()
        hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        return f"{hours:.1f}h"
    except Exception:
        return "N/A"


def _paper_positions_rows(trader: PaperTrader) -> list[dict]:
    rows = []
    for position in trader.positions:
        current_price = trader._last_prices.get(position.symbol)
        if current_price is None:
            current_price = trader._get_current_price(position.symbol)
            if current_price is not None:
                trader._last_prices[position.symbol] = current_price
        if current_price is None:
            pnl_pct = None
        elif position.direction == "LONG":
            pnl_pct = (current_price - position.entry_price) / position.entry_price * 100
        else:
            pnl_pct = (position.entry_price - current_price) / position.entry_price * 100
        rows.append({
            "Símbolo": position.symbol,
            "Dirección": position.direction,
            "Entry": position.entry_price,
            "SL": position.sl_price,
            "TP": position.tp_price,
            "Score": position.score,
            "Abierta hace": _hours_since(position.entry_time),
            "PnL no realizado %": round(pnl_pct, 3) if pnl_pct is not None else None,
        })
    return rows


def render_paper_trading_tab():
    """Renderiza la pestaña de paper trading con métricas, tablas y controles."""
    trader = _get_paper_trader()
    report_path = _paper_report_path(paper_trader.REPORT_FILENAME)
    equity_path = _paper_report_path(paper_trader.EQUITY_FILENAME)
    has_report = os.path.exists(report_path)

    if not has_report:
        st.info(
            "No hay datos de paper trading aún. Iniciá el ciclo con:\n\n"
            "python cli.py --paper-start"
        )

    summary = trader.get_summary()
    st.subheader("Resumen de performance")
    c1, c2, c3 = st.columns(3)
    c1.metric("Capital actual", summary.get("capital_actual"))
    c2.metric("Retorno %", summary.get("retorno_total_pct"))
    c3.metric("Win Rate", f"{summary.get('win_rate')}%")
    c4, c5, c6 = st.columns(3)
    c4.metric("Avg R-multiple", summary.get("avg_r_multiple"))
    c5.metric("Sharpe", summary.get("sharpe_ratio") if summary.get("sharpe_ratio") is not None else "N/A")
    c6.metric("Max DD%", summary.get("max_drawdown_pct"))

    st.subheader("Posiciones abiertas")
    position_rows = _paper_positions_rows(trader)
    if position_rows:
        st.dataframe(pd.DataFrame(position_rows), use_container_width=True, hide_index=True)
    else:
        st.caption("Sin posiciones abiertas.")

    st.subheader("Historial de trades")
    if has_report:
        report_df = pd.read_csv(report_path)
        if not report_df.empty:
            st.dataframe(report_df.tail(20), use_container_width=True, hide_index=True)
        else:
            st.caption("Sin trades cerrados todavía.")
    else:
        st.caption("Sin reporte de trades todavía.")

    st.subheader("Equity curve")
    if os.path.exists(equity_path):
        equity_df = pd.read_csv(equity_path)
        if not equity_df.empty and "equity" in equity_df.columns:
            chart_df = equity_df.copy()
            if "timestamp" in chart_df.columns:
                chart_df["timestamp"] = pd.to_datetime(chart_df["timestamp"], utc=True, errors="coerce")
                chart_df = chart_df.dropna(subset=["timestamp"]).set_index("timestamp")
            st.line_chart(chart_df[["equity"]])
        else:
            st.caption("Sin puntos de equity todavía.")
    else:
        st.caption("Sin curva de equity todavía.")

    st.subheader("Controles")
    st.session_state["paper_dry_run"] = st.toggle(
        "Dry run",
        value=st.session_state.get("paper_dry_run", True),
        help="No abrir nuevas posiciones desde la UI.",
    )
    p1, p2 = st.columns(2)
    with p1:
        if st.button("Actualizar posiciones", type="primary", use_container_width=True):
            try:
                closed = trader.update_positions()
                st.session_state["paper_trader"] = trader
                st.success(f"Posiciones cerradas en update: {len(closed)}")
            except Exception as exc:
                _show_action_error(exc, "No se pudieron actualizar posiciones")
    with p2:
        symbols = [position.symbol for position in trader.positions]
        selected_close_symbol = st.selectbox(
            "Cerrar posición",
            symbols or ["Sin posiciones"],
            disabled=not symbols,
        )
        if st.button("Cerrar posición manual", use_container_width=True, disabled=not symbols):
            try:
                closed = trader.close_position_manual(selected_close_symbol)
                st.session_state["paper_trader"] = trader
                if closed:
                    st.success(f"Cerrada {closed['symbol']} PnL {closed['net_pnl']:.4f}")
                else:
                    st.warning("No se encontró la posición seleccionada.")
            except Exception as exc:
                _show_action_error(exc, "No se pudo cerrar la posición")


@st.cache_data(ttl=60)
def _get_signals_cached():
    return storage.get_all_signals()

@st.cache_data(ttl=60)
def _get_trades_cached():
    return storage.get_all_paper_trades()

def render_performance_dashboard_tab():
    st.subheader("Performance Dashboard")
    
    signals = _get_signals_cached()
    trades = _get_trades_cached()
    
    df_signals = pd.DataFrame(signals) if signals else pd.DataFrame()
    df_trades = pd.DataFrame(trades) if trades else pd.DataFrame()
    
    # Normalización de columnas para evitar KeyError
    signal_columns = [
        "symbol", "exchange", "market_type", "timeframe", "decision",
        "score", "strategy_profile", "created_at", "warnings", "reasons",
    ]
    trade_columns = [
        "symbol", "exchange", "market_type", "timeframe", "status",
        "side", "pnl", "pnl_pct", "strategy_profile", "opened_at", "closed_at",
    ]
    
    df_signals = ensure_columns(df_signals, signal_columns)
    df_trades = ensure_columns(df_trades, trade_columns)
    
    # Manejo de legacy strategy profiles
    df_signals["strategy_profile"] = df_signals["strategy_profile"].fillna("legacy")
    df_trades["strategy_profile"] = df_trades["strategy_profile"].fillna("legacy")

    if df_signals.empty and df_trades.empty:
        st.info("📊 Todavía no hay datos de señales o trades para mostrar.")
        return
        
    dash_signals_tab, dash_trades_tab, dash_metrics_tab, dash_comparison_tab = st.tabs(["Señales", "Paper Trades", "Métricas & Gráficos", "Comparación de Estrategias"])
    
    with dash_signals_tab:
        st.markdown("### Filtros de Señales")
        if not df_signals.empty:
            if "created_at" in df_signals.columns:
                df_signals["created_at"] = pd.to_datetime(df_signals["created_at"], errors="coerce")
            else:
                df_signals["created_at"] = pd.NaT
            
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                sym_list = safe_unique_values(df_signals, "symbol")
                f_sym = st.selectbox("Symbol", ["Todos"] + sym_list, key="dash_sig_sym")
            with c2:
                exc_list = safe_unique_values(df_signals, "exchange")
                f_exc = st.selectbox("Exchange", ["Todos"] + exc_list, key="dash_sig_exc")
            with c3:
                mkt_list = safe_unique_values(df_signals, "market_type")
                f_mkt = st.selectbox("Market Type", ["Todos"] + mkt_list, key="dash_sig_mkt")
            with c4:
                tf_list = safe_unique_values(df_signals, "timeframe")
                f_tf = st.selectbox("Timeframe", ["Todos"] + tf_list, key="dash_sig_tf")
                
            c5, c6, c7 = st.columns(3)
            with c5:
                dec_list = safe_unique_values(df_signals, "decision")
                f_dec = st.selectbox("Decision", ["Todos"] + dec_list, key="dash_sig_dec")
            with c6:
                f_score = st.slider("Min Score", 0.0, 10.0, 0.0, 0.5, key="dash_sig_score")
            with c7:
                valid_dates = df_signals["created_at"].dropna()
                min_date = valid_dates.min().date() if not valid_dates.empty else datetime.today().date()
                max_date = valid_dates.max().date() if not valid_dates.empty else datetime.today().date()
                f_dates = st.date_input("Rango de Fechas", [min_date, max_date], key="dash_sig_dates")
            
            c_strat_1, c_strat_2 = st.columns(2)
            with c_strat_1:
                strat_list = safe_unique_values(df_signals, "strategy_profile")
                f_strat = st.selectbox("Strategy Profile", ["Todos"] + strat_list, key="dash_sig_strat")
            with c_strat_2:
                st.caption("Filtra por el perfil usado al generar la señal.")

            filtered_sig = df_signals.copy()
            if f_strat != "Todos" and "strategy_profile" in filtered_sig.columns: filtered_sig = filtered_sig[filtered_sig["strategy_profile"] == f_strat]
            if f_sym != "Todos" and "symbol" in filtered_sig.columns: filtered_sig = filtered_sig[filtered_sig["symbol"] == f_sym]
            if f_exc != "Todos" and "exchange" in filtered_sig.columns: filtered_sig = filtered_sig[filtered_sig["exchange"] == f_exc]
            if f_mkt != "Todos" and "market_type" in filtered_sig.columns: filtered_sig = filtered_sig[filtered_sig["market_type"] == f_mkt]
            if f_tf != "Todos" and "timeframe" in filtered_sig.columns: filtered_sig = filtered_sig[filtered_sig["timeframe"] == f_tf]
            if f_dec != "Todos" and "decision" in filtered_sig.columns: filtered_sig = filtered_sig[filtered_sig["decision"] == f_dec]
            if "score" in filtered_sig.columns:
                filtered_sig = filtered_sig[pd.to_numeric(filtered_sig["score"], errors="coerce").fillna(0) >= f_score]
            if len(f_dates) == 2 and "created_at" in filtered_sig.columns:
                filtered_sig = filtered_sig[(filtered_sig["created_at"].dt.date >= f_dates[0]) & (filtered_sig["created_at"].dt.date <= f_dates[1])]

            view_cols = ["symbol", "exchange", "market_type", "timeframe", "decision", "score", "entry", "stop_loss", "take_profit", "created_at", "warnings", "reasons"]
            available_cols = [c for c in view_cols if c in filtered_sig.columns]
            
            def format_list_cols(val):
                if isinstance(val, list):
                    return ", ".join(map(str, val))
                return val
            for col in ["warnings", "reasons"]:
                if col in available_cols:
                    filtered_sig[col] = filtered_sig[col].apply(format_list_cols)
                    
            st.dataframe(filtered_sig[available_cols], use_container_width=True, hide_index=True)
            
            csv_data = filtered_sig.to_csv(index=False).encode('utf-8')
            st.download_button("Exportar Señales a CSV", data=csv_data, file_name="señales_filtradas.csv", mime="text/csv")
        else:
            st.caption("No hay señales registradas.")

    with dash_trades_tab:
        st.markdown("### Filtros de Paper Trades")
        if not df_trades.empty:
            if "opened_at" in df_trades.columns:
                df_trades["opened_at"] = pd.to_datetime(df_trades["opened_at"], errors="coerce")
            else:
                df_trades["opened_at"] = pd.NaT
                
            if "closed_at" in df_trades.columns:
                df_trades["closed_at"] = pd.to_datetime(df_trades["closed_at"], errors="coerce")
                df_trades["duration_hours"] = (df_trades["closed_at"] - df_trades["opened_at"]).dt.total_seconds() / 3600.0
            else:
                df_trades["duration_hours"] = None
                
            c1, c2, c3 = st.columns(3)
            with c1:
                sym_list = safe_unique_values(df_trades, "symbol")
                t_sym = st.selectbox("Symbol", ["Todos"] + sym_list, key="dash_tr_sym")
            with c2:
                side_col_all = "side" if "side" in df_trades.columns else ("direction" if "direction" in df_trades.columns else None)
                if side_col_all:
                    t_side = st.selectbox("Side", ["Todos"] + list(df_trades[side_col_all].dropna().unique()), key="dash_tr_side")
                else:
                    t_side = "Todos"
            with c3:
                status_list = safe_unique_values(df_trades, "status")
                t_status = st.selectbox("Status", ["Todos"] + status_list, key="dash_tr_status")
            
            c_tr_strat_1, c_tr_strat_2 = st.columns(2)
            with c_tr_strat_1:
                t_strat_list = safe_unique_values(df_trades, "strategy_profile")
                t_strat = st.selectbox("Strategy Profile", ["Todos"] + t_strat_list, key="dash_tr_strat")
            with c_tr_strat_2:
                st.caption("Filtra por el perfil usado al abrir el paper trade.")
                
            filtered_tr = df_trades.copy()
            if t_strat != "Todos" and "strategy_profile" in filtered_tr.columns: filtered_tr = filtered_tr[filtered_tr["strategy_profile"] == t_strat]
            if t_sym != "Todos": filtered_tr = filtered_tr[filtered_tr["symbol"] == t_sym]
            side_col = "side" if "side" in filtered_tr.columns else ("direction" if "direction" in filtered_tr.columns else None)
            if t_side != "Todos" and side_col: filtered_tr = filtered_tr[filtered_tr[side_col] == t_side]
            if t_status != "Todos" and "status" in filtered_tr.columns: filtered_tr = filtered_tr[filtered_tr["status"] == t_status]
            
            view_cols = ["symbol", "status", "pnl", "pnl_pct", "reason_open", "reason_close", "duration_hours", side_col, "market_type", "exchange"]
            available_cols = [c for c in view_cols if c and c in filtered_tr.columns]
            
            st.dataframe(filtered_tr[available_cols], use_container_width=True, hide_index=True)
            
            csv_data = filtered_tr.to_csv(index=False).encode('utf-8')
            st.download_button("Exportar Trades a CSV", data=csv_data, file_name="trades_filtrados.csv", mime="text/csv")
        else:
            st.caption("No hay paper trades registrados.")
            
    with dash_metrics_tab:
        st.markdown("### Métricas Principales")
        
        total_signals = len(df_signals)
        total_trades = len(df_trades)
        open_trades = len(df_trades[df_trades.get("status") == "OPEN"]) if not df_trades.empty and "status" in df_trades.columns else 0
        closed_trades = len(df_trades[df_trades.get("status") == "CLOSED"]) if not df_trades.empty and "status" in df_trades.columns else 0
        
        winrate = 0.0
        total_pnl = 0.0
        avg_pnl = 0.0
        best_trade = 0.0
        worst_trade = 0.0
        if closed_trades > 0 and "pnl" in df_trades.columns:
            closed_df = df_trades[df_trades["status"] == "CLOSED"]
            wins = len(closed_df[pd.to_numeric(closed_df["pnl"], errors="coerce") > 0])
            winrate = (wins / closed_trades) * 100
            
            total_pnl = pd.to_numeric(closed_df["pnl"], errors="coerce").sum()
            avg_pnl = pd.to_numeric(closed_df["pnl"], errors="coerce").mean()
            best_trade = pd.to_numeric(closed_df["pnl"], errors="coerce").max()
            worst_trade = pd.to_numeric(closed_df["pnl"], errors="coerce").min()
            
        avg_score = pd.to_numeric(df_signals["score"], errors="coerce").mean() if not df_signals.empty and "score" in df_signals.columns else 0.0
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Señales", total_signals)
        m2.metric("Total Trades", total_trades)
        m3.metric("Trades Abiertos", open_trades)
        m4.metric("Trades Cerrados", closed_trades)
        
        m5, m6, m7, m8 = st.columns(4)
        m5.metric("Winrate", f"{winrate:.1f}%")
        m6.metric("PnL Total", f"${total_pnl:.2f}")
        m7.metric("Mejor Trade", f"${best_trade:.2f}")
        m8.metric("Peor Trade", f"${worst_trade:.2f}")
        
        m9, m10, m11, m12 = st.columns(4)
        m9.metric("PnL Promedio", f"${avg_pnl:.2f}")
        m10.metric("Avg Score Señal", f"{avg_score:.2f}")
        m11.metric("Señales Spot", len(df_signals[df_signals.get("market_type") == "spot"]) if not df_signals.empty and "market_type" in df_signals.columns else 0)
        m12.metric("Señales Futures", len(df_signals[df_signals.get("market_type") == "futures"]) if not df_signals.empty and "market_type" in df_signals.columns else 0)
        
        st.markdown("### Gráficos")
        
        if closed_trades > 0 and "closed_at" in df_trades.columns and "pnl" in df_trades.columns:
            closed_df = df_trades[df_trades["status"] == "CLOSED"].copy()
            closed_df["closed_at_date"] = closed_df["closed_at"].dt.date
            pnl_by_date = closed_df.groupby("closed_at_date")["pnl"].sum().cumsum()
            st.subheader("PnL Acumulado por Fecha")
            st.line_chart(pnl_by_date)
            
            st.subheader("PnL por Símbolo")
            pnl_by_symbol = closed_df.groupby("symbol")["pnl"].sum()
            st.bar_chart(pnl_by_symbol)
            
        if not df_signals.empty and "created_at" in df_signals.columns:
            st.subheader("Señales por Día")
            df_signals["created_at_date"] = df_signals["created_at"].dt.date
            signals_by_date = df_signals.groupby("created_at_date").size()
            st.bar_chart(signals_by_date)
            
            if "score" in df_signals.columns:
                st.subheader("Distribución de Scores")
                scores = pd.to_numeric(df_signals["score"], errors="coerce").dropna()
                if not scores.empty:
                    st.bar_chart(scores.value_counts().sort_index())
                
        if closed_trades > 0 and "timeframe" in df_trades.columns:
            st.subheader("Winrate por Timeframe")
            closed_df = df_trades[df_trades["status"] == "CLOSED"].copy()
            closed_df["is_win"] = pd.to_numeric(closed_df["pnl"], errors="coerce") > 0
            winrate_tf = closed_df.groupby("timeframe")["is_win"].mean() * 100
            st.bar_chart(winrate_tf)
            
        if not df_signals.empty and "market_type" in df_signals.columns:
            st.subheader("Señales: Spot vs Futures")
            mkt_counts = df_signals["market_type"].value_counts()
            st.bar_chart(mkt_counts)

    with dash_comparison_tab:
        st.markdown("### Comparador de Estrategias")
        
        # Filtros Globales de Comparación
        c1, c2, c3 = st.columns(3)
        with c1:
            all_syms = safe_union_unique(df_signals, df_trades, "symbol")
            f_comp_sym = st.selectbox("Símbolo", ["Todos"] + all_syms, key="comp_f_sym")
        with c2:
            all_excs = safe_union_unique(df_signals, df_trades, "exchange")
            f_comp_exc = st.selectbox("Exchange", ["Todos"] + all_excs, key="comp_f_exc")
        with c3:
            f_comp_mkt = st.selectbox("Market Type", ["Todos", "spot", "futures"], key="comp_f_mkt")
            
        c4, c5, c6 = st.columns(3)
        with c4:
            all_tfs = safe_union_unique(df_signals, df_trades, "timeframe")
            f_comp_tf = st.selectbox("Timeframe", ["Todos"] + all_tfs, key="comp_f_tf")
        with c5:
            # Rango de fechas combinado
            all_dates = pd.to_datetime(pd.concat([df_signals.get("created_at", pd.Series()), df_trades.get("opened_at", pd.Series())]), errors="coerce").dropna()
            min_d = all_dates.min().date() if not all_dates.empty else datetime.today().date()
            max_d = all_dates.max().date() if not all_dates.empty else datetime.today().date()
            f_comp_dates = st.date_input("Rango de Fechas", [min_d, max_d], key="comp_f_dates")
        with c6:
            f_comp_closed = st.checkbox("Solo trades cerrados", value=True, key="comp_f_closed")

        # Aplicar filtros antes de cálculos
        def apply_comp_filters(df, date_col):
            if df.empty: return df
            res = df.copy()
            if f_comp_sym != "Todos": res = res[res["symbol"] == f_comp_sym]
            if f_comp_exc != "Todos" and "exchange" in res.columns: res = res[res["exchange"] == f_comp_exc]
            if f_comp_mkt != "Todos" and "market_type" in res.columns: res = res[res["market_type"] == f_comp_mkt]
            if f_comp_tf != "Todos" and "timeframe" in res.columns: res = res[res["timeframe"] == f_comp_tf]
            if len(f_comp_dates) == 2 and date_col in res.columns:
                res[date_col] = pd.to_datetime(res[date_col], utc=True, errors="coerce")
                res = res[(res[date_col].dt.date >= f_comp_dates[0]) & (res[date_col].dt.date <= f_comp_dates[1])]
            return res

        f_sig_comp = apply_comp_filters(df_signals, "created_at")
        f_trd_comp = apply_comp_filters(df_trades, "opened_at")
        if f_comp_closed and not f_trd_comp.empty:
            f_trd_comp = f_trd_comp[f_trd_comp["status"].isin(["CLOSED", "EXITED", "hit_tp", "hit_sl"])]

        summary = performance_metrics.calculate_profile_summary(f_sig_comp, f_trd_comp)
        
        if not summary:
            st.warning("No hay datos para los filtros seleccionados.")
        else:
            # Cards de resumen
            cc1, cc2, cc3 = st.columns(3)
            cc1.metric("Mejor PnL", f"{summary['best_pnl_profile']}", f"${summary['best_pnl_value']:.2f}")
            cc2.metric("Mejor Winrate", f"{summary['best_winrate_profile']}", f"{summary['best_winrate_value']:.1f}%")
            cc3.metric("Más Señales", f"{summary['most_signals_profile']}", f"{summary['most_signals_count']}")
            
            cc4, cc5, cc6 = st.columns(3)
            cc4.metric("Mejor PF", f"{summary['best_profit_factor_profile']}", f"{summary['best_profit_factor_value']}")
            cc5.metric("Mejor Score", f"{summary['best_score_profile']}", f"{summary['best_score_value']:.2f}")
            cc6.metric("Perfiles", summary['total_profiles'])
            
            # Tabla Comparativa
            st.markdown("### Tabla Comparativa por Perfil")
            comparison_df = performance_metrics.calculate_strategy_comparison(f_sig_comp, f_trd_comp)
            st.dataframe(comparison_df.sort_values("total_pnl", ascending=False), use_container_width=True, hide_index=True)
            
            # Gráficos
            st.markdown("### Visualización")
            g1, g2 = st.columns(2)
            with g1:
                st.subheader("PnL por Perfil")
                st.bar_chart(comparison_df.set_index("strategy_profile")["total_pnl"])
            with g2:
                st.subheader("Winrate por Perfil (%)")
                st.bar_chart(comparison_df.set_index("strategy_profile")["winrate"])
            
            g3, g4 = st.columns(2)
            with g3:
                st.subheader("Señales por Perfil")
                st.bar_chart(comparison_df.set_index("strategy_profile")["total_signals"])
            with g4:
                st.subheader("Score Promedio")
                st.bar_chart(comparison_df.set_index("strategy_profile")["avg_score"])

            # Equity curve
            st.subheader("Curva de Equidad por Perfil")
            equity_df = performance_metrics.calculate_equity_curve(f_trd_comp)
            if not equity_df.empty:
                # Pivot para graficar múltiples líneas
                pivot_equity = equity_df.pivot(index="timestamp", columns="strategy_profile", values="equity").ffill().fillna(0)
                st.line_chart(pivot_equity)
            else:
                st.caption("No hay suficientes trades cerrados para generar la curva de equidad.")

            # Exportación
            st.markdown("### Exportar Reportes")
            ex1, ex2, ex3 = st.columns(3)
            with ex1:
                csv_comp = comparison_df.to_csv(index=False).encode('utf-8')
                st.download_button("Descargar Comparativa (CSV)", csv_comp, "strategy_comparison.csv", "text/csv")
            with ex2:
                csv_sig = f_sig_comp.to_csv(index=False).encode('utf-8')
                st.download_button("Descargar Señales Filtradas (CSV)", csv_sig, "filtered_signals.csv", "text/csv")
            with ex3:
                csv_trd = f_trd_comp.to_csv(index=False).encode('utf-8')
                st.download_button("Descargar Trades Filtrados (CSV)", csv_trd, "filtered_trades.csv", "text/csv")

            # Reporte Markdown
            if st.button("Generar Reporte Markdown"):
                md_report = f"""# Strategy Performance Comparison Report
                
Generado el: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Filtros Utilizados
- Símbolo: {f_comp_sym}
- Exchange: {f_comp_exc}
- Market Type: {f_comp_mkt}
- Timeframe: {f_comp_tf}
- Rango: {f_comp_dates}
- Solo cerrados: {f_comp_closed}

## Resumen de Mejores Perfiles
- **Mejor PnL**: {summary['best_pnl_profile']} (${summary['best_pnl_value']:.2f})
- **Mejor Winrate**: {summary['best_winrate_profile']} ({summary['best_winrate_value']:.1f}%)
- **Mejor Profit Factor**: {summary['best_profit_factor_profile']} ({summary['best_profit_factor_value']})

## Tabla de Comparación
{comparison_df.to_markdown(index=False)}

## Notas
- Reporte generado automáticamente por Crypto Technical Advisor.
- Los datos reflejan ejecuciones de Paper Trading y escaneos históricos.
- Paper/analysis only. No financial advice.
"""
                st.text_area("Copia el reporte Markdown:", md_report, height=300)
                st.download_button("Descargar Reporte (MD)", md_report, "strategy_report.md", "text/markdown")


st.set_page_config(
    page_title="Crypto Technical Advisor",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.title("Crypto Technical Advisor")
st.caption("Paper/analysis only. No live trading. No financial advice.")
st.caption(f"Storage backend: {storage.get_storage_backend().upper()}")

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
    selected_exchange_mode_label = st.selectbox("Exchange mode", ["Manual", "Fallback"], index=1)

strategy_files = [f.replace(".json", "") for f in os.listdir("strategies") if f.endswith(".json")]
if not strategy_files:
    strategy_files = ["balanced"]

g_strat_1, g_strat_2 = st.columns([1, 1])
with g_strat_1:
    selected_strategy = st.selectbox("Strategy Profile", strategy_files, index=strategy_files.index("balanced") if "balanced" in strategy_files else 0)
with g_strat_2:
    st.caption(f"Usando parámetros de: strategies/{selected_strategy}.json")

selected_exchange = _exchange_id_from_label(selected_exchange_label)
selected_exchange_mode = selected_exchange_mode_label.lower()

tf_options = config.TIMEFRAMES if selected_mode == "SPOT" else futures_analyzer.FUTURES_TIMEFRAMES
g5, g6 = st.columns(2)
with g5:
    timeframe_mode = st.radio("Timeframe mode", ["Auto", "Manual"], index=0, horizontal=True)
with g6:
    selected_timeframe = st.selectbox("Timeframe", tf_options, index=tf_options.index("1h") if "1h" in tf_options else 0, disabled=timeframe_mode == "Auto")

if selected_exchange_mode == "fallback":
    fallback_priority = " -> ".join(_exchange_label(exchange) for exchange in config.EXCHANGE_PRIORITY)
    st.caption(f"Fallback mode tries: {fallback_priority}.")
else:
    st.caption(f"Manual mode uses only {_exchange_label(selected_exchange)}.")

analyze_tab, scanner_tab, validate_tab, signals_tab, cycle_tab, paper_tab, dashboard_tab, diagnostics_tab = st.tabs([
    "Analyze",
    "Market Scanner",
    "Validate",
    "Signals",
    "Full Cycle",
    "Paper Engine",
    "Dashboard",
    "Diagnostics",
])

with analyze_tab:
    symbol = selected_symbol.strip() or "BTC/USDT"
    use_auto = timeframe_mode == "Auto"
    st.subheader(f"{selected_mode} Analyze")
    run_spot_backtest = False

    if selected_mode == "FUTURES":
        st.warning(
            "Futures tiene riesgo elevado por apalancamiento y liquidación. "
            "Esta herramienta es solo análisis técnico/paper, no consejo financiero."
        )

    if selected_mode == "SPOT":
        run_spot_backtest = st.checkbox("Run quick backtest", value=False)

    button_label = "Analyze SPOT" if selected_mode == "SPOT" else "Analyze FUTURES"
    if st.button(button_label, type="primary", use_container_width=True):
        bt_result = None
        with st.spinner(f"Analyzing {selected_mode} {symbol}..."):
            try:
                if selected_mode == "SPOT":
                    if use_auto:
                        result = technical_analyzer.analyze_symbol_auto(
                            symbol,
                            exchange_id=selected_exchange,
                            exchange_mode=selected_exchange_mode,
                            strategy_profile=selected_strategy,
                        )
                    else:
                        result = technical_analyzer.analyze_symbol_timeframe(
                            symbol,
                            selected_timeframe,
                            exchange_id=selected_exchange,
                            exchange_mode=selected_exchange_mode,
                            strategy_profile=selected_strategy,
                        )
                    if not result.get("analysis_time"):
                        result["analysis_time"] = datetime.now(timezone.utc).isoformat()
                    if run_spot_backtest:
                        bt_tf = (
                            result.get("recommended_timeframe")
                            or result.get("timeframe")
                            or selected_timeframe
                        )
                        if bt_tf:
                            bt_result = backtester.run_quick_backtest(
                                symbol,
                                bt_tf,
                                days=st.session_state.get("bt_days", 90),
                                exchange_id=selected_exchange,
                                exchange_mode=selected_exchange_mode,
                                strategy_profile=selected_strategy,
                            )
                            result = technical_analyzer.apply_backtest_to_analysis(result, bt_result)
                    try:
                        report_builder.save_report(result, bt_result)
                    except Exception as report_error:
                        st.caption(f"No se pudo guardar latest_analysis: {report_error}")
                else:
                    if use_auto:
                        result = futures_analyzer.analyze_futures_symbol_auto(
                            symbol,
                            exchange_id=selected_exchange,
                            exchange_mode=selected_exchange_mode,
                            strategy_profile=selected_strategy,
                        )
                    else:
                        result = futures_analyzer.analyze_futures_symbol_timeframe(
                            symbol,
                            selected_timeframe,
                            exchange_id=selected_exchange,
                            exchange_mode=selected_exchange_mode,
                            strategy_profile=selected_strategy,
                        )
            except Exception as e:
                _show_action_error(e, f"{selected_mode} analysis failed")
                st.stop()

        render_action_hint(result, selected_mode)
        render_result_summary(result, selected_mode)
        if bt_result:
            render_backtest_metrics(bt_result)
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
                        strategy_profile=selected_strategy,
                    )
                    st.session_state["latest_scan"] = scan_result
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
            c4, c5, c6, c7 = st.columns(4)
            c4.metric("AVOID", counts.get("AVOID", 0))
            c5.metric("Tiempo total", scan_result.get("elapsed_display", "-"))
            c6.metric("Exchange", scan_result.get("data_source_exchange") or "N/A")
            c7.metric("Market", scan_result.get("market_type") or "spot")
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
                    res = validator.run_validation(
                        top_n=int(top_n),
                        exchange_id=selected_exchange,
                        exchange_mode=selected_exchange_mode,
                        strategy_profile=selected_strategy,
                    )
                    st.session_state["latest_validation"] = res
                    if res:
                        st.success(f"Validación guardada en {res.get('md_path', 'N/A')}")
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
                        strategy_profile=selected_strategy,
                    )
                    st.session_state["latest_cycle"] = res
                    st.success(f"Ciclo completado en {res['total_time']:.2f}s.")
                except Exception as e:
                    _show_action_error(e, "Error during cycle")
            try:
                with open(os.path.join(config.OUTPUT_DIR, "latest_cycle_summary.md"), "r", encoding="utf-8") as f:
                    st.markdown(f.read())
            except Exception:
                st.info("No cycle summary found.")

with paper_tab:
    render_paper_trading_tab()

with dashboard_tab:
    render_performance_dashboard_tab()

with diagnostics_tab:
    st.markdown("### System Information")
    c1, c2 = st.columns(2)
    with c1:
        st.write(f"**Python Version:** {platform.python_version()}")
        st.write(f"**Storage Backend:** {config.STORAGE_BACKEND.upper()}")
        st.write(f"**SQLite Path:** `{config.SQLITE_PATH}`")
    with c2:
        st.write(f"**Default Exchange:** {config.DEFAULT_EXCHANGE}")
        st.write(f"**Fallback Order:** {' -> '.join(config.EXCHANGE_PRIORITY)}")
        st.write(f"**Strategy Profiles:** {', '.join(strategy_files)}")
    
    st.divider()
    st.info("Pruebas de conectividad con exchanges.")
    if st.button("Test connectivity", type="primary", use_container_width=True):
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
