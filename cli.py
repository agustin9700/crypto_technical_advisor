#!/usr/bin/env python3
"""
Crypto Technical Advisor - CLI
Usage:
    python cli.py --symbol ETH/USDT --auto
    python cli.py --symbol ETH/USDT --timeframe 1h
    python cli.py --symbol ETH/USDT --timeframe 1h --backtest
    python cli.py --symbol ETH/USDT --timeframe 4h --backtest --days 180
"""

import argparse
import json
import sys
import pandas as pd
from datetime import datetime, timezone

import backtester
import config
import cycle_runner
import futures_analyzer
import paper_cycle
import report_builder
import scanner
import signal_tracker
import storage
import technical_analyzer
import utils
import validator
from paper_trader import PaperTrader

# Helper alias for unique items
_unique_items = utils.unique_items

import performance_metrics


def print_separator():
    print("-" * 60)


def _display_tf(result: dict) -> str:
    """Extract and format the timeframe from result."""
    tf = result.get("timeframe") or result.get("recommended_timeframe") or "?"
    return utils.display_timeframe(tf) if tf != "?" else "?"





def _backtest_warning(result: dict, bt_result: dict = None) -> str:
    verdict = (bt_result or {}).get("verdict") or result.get("backtest_verdict")
    if verdict in ("BACKTEST_WEAK", "BACKTEST_BAD"):
        return technical_analyzer.BACKTEST_NO_CONFIRM_WARNING
    return ""





def _print_list_section(title: str, items) -> None:
    items = utils.unique_items(items)
    if not items:
        return

    print(f"  {title}:")
    for item in items:
        print(f"     - {item}")


def _dedupe_scan_rows(rows: list, limit: int = 10) -> list:
    deduped = []
    seen_keys = set()
    seen_symbols = set()
    for row in rows:
        symbol = row.get("symbol") or ""
        timeframe = row.get("recommended_timeframe") or ""
        key = (symbol, timeframe)
        if symbol in seen_symbols or key in seen_keys:
            continue
        seen_symbols.add(symbol)
        seen_keys.add(key)
        deduped.append(row)
        if len(deduped) >= limit:
            break
    return deduped


def print_result(result: dict, bt_result: dict = None):
    best = result.get("best_setup") or result
    symbol = result.get("symbol", "?")
    display_tf = _display_tf(result)
    decision = result.get("decision", "?")
    plan = result if result.get("action_summary") else best
    needs = plan.get("what_needs_to_happen", [])

    print_separator()
    print(f"  {symbol} - {display_tf}")
    print_separator()
    source = result.get("data_source_exchange") or best.get("data_source_exchange")
    if source:
        mode = result.get("exchange_mode") or best.get("exchange_mode") or config.EXCHANGE_MODE
        fallback_used = result.get("fallback_used") or best.get("fallback_used") or False
        print(f"  Exchange:                {str(source).lower()}")
        print(f"  Exchange mode:           {mode}")
        print(f"  Market type:             {result.get('market_type') or best.get('market_type') or 'spot'}")
        print(f"  Fallback used:           {'yes' if fallback_used else 'no'}")
    tf_str = result.get("recommended_timeframe") or result.get("timeframe")
    print(f"  Temporalidad recomendada: {utils.display_timeframe(tf_str) if tf_str else 'ninguna'}")
    print(f"  Decision:                 {decision}")
    print(f"  Entrada ahora:            {utils.entry_now_display(plan.get('entry_now_text'))}")
    print(f"  Motivo principal:         {plan.get('main_reason', 'N/A')}")
    print(f"  Strategy profile:         {result.get('strategy_profile') or 'balanced'}")
    print(f"  Conclusion:               {plan.get('human_verdict', 'N/A')}")
    if result.get("no_clear_setup"):
        print("  NO_CLEAR_SETUP: no hay temporalidad con setup claro ahora.")
    if result.get("auto_observation"):
        print(f"  {result.get('auto_observation')}")
    top_backtest_warning = _backtest_warning(result, bt_result)
    if top_backtest_warning:
        print(f"  {top_backtest_warning}")

    print_separator()
    print("  Que falta para entrar:")
    if needs:
        for item in needs:
            print(f"     - {item}")
    else:
        print("     - Nada critico segun el scoring actual; respetar invalidacion.")

    print_separator()
    print("  Plan de entrada:")
    print(f"  Entrada estimada:         {utils.format_price(best.get('estimated_entry'))}")
    print(f"  Gatillo valido:           {plan.get('entry_trigger', 'N/A')}")
    print(f"  Stop Loss:                {utils.format_price(best.get('estimated_stop_loss'))}")
    print(f"  Take Profit:              {utils.format_price(best.get('estimated_take_profit'))}")
    print(f"  Invalidacion:             {plan.get('invalidation_level', 'N/A')}")
    print(f"  RR:                       {best.get('rr_ratio', 'N/A')}")
    print(f"  Soporte:                  {utils.format_price(best.get('nearest_support'))}")
    print(f"  Resistencia:              {utils.format_price(best.get('nearest_resistance'))}")

    print_separator()
    print(f"  Score:                    {best.get('score', 0)}/{best.get('score_max', 10)}")
    print(f"  Confianza:                {best.get('confidence', 0)}%")
    print(f"  Precio:                   {utils.format_price(best.get('price'))}")
    print(f"  RSI:                      {best.get('rsi', 'N/A')}")
    if best.get("closed_candle_vol_ratio") is not None:
        print(f"  Vol vela cerrada:         {best.get('closed_candle_vol_ratio')}x")
        intra = best.get("intracandle_vol_ratio")
        print(f"  Vol intravela:            {f'{intra}x' if intra is not None else 'N/A'}")
        adjusted = best.get("adjusted_intracandle_vol_ratio")
        if adjusted is not None:
            print(f"  Vol intravela ajustado:   {adjusted}x")
    if best.get("volume_warning"):
        print(f"  Volume warning:           {best.get('volume_warning')}")

    _print_list_section("Razones", best.get("reasons", []))
    _print_list_section("Condiciones faltantes", best.get("missing_conditions", []))

    warnings = _unique_items(best.get("warnings", []))
    global_warnings = _unique_items(result.get("warnings", []))
    all_warnings = _unique_items(warnings + global_warnings)
    if top_backtest_warning:
        all_warnings = [w for w in all_warnings if w != top_backtest_warning]
    _print_list_section("Advertencias", all_warnings)

    if bt_result:
        print_separator()
        verdict = bt_result.get("verdict", "N/A")
        bt_tf = bt_result.get("timeframe") or display_tf
        if result.get("timeframe_results"):
            print(f"  Backtest rapido del timeframe recomendado: {bt_tf}")
        else:
            print(f"  Backtest rapido: {bt_tf}")
        print(f"  Veredicto: {verdict}")
        print(f"  Trades:    {bt_result.get('n_trades', 0)}")
        print(f"  Win Rate:  {bt_result.get('win_rate', 0):.1f}%")
        print(f"  PF:        {bt_result.get('profit_factor', 0):.3f}")
        print(f"  Retorno:   {bt_result.get('total_return_pct', 0):.2f}%")
        print(f"  Max DD:    {bt_result.get('max_drawdown_pct', 0):.2f}%")

    print_separator()
    print("  Solo analisis tecnico. No consejo financiero.")
    print(f"  Storage backend: {storage.get_storage_backend().upper()}")
    print_separator()


def print_scan_result(scan_result: dict):
    rows = scan_result.get("rows", [])
    counts = scan_result.get("decision_counts", {})

    print_separator()
    print("  Market Scanner")
    print_separator()
    print(f"  Fecha/hora:              {scan_result.get('generated_at')}")
    print(f"  Modo scanner:            {scan_result.get('scan_mode', 'fast')}")
    print(f"  Timeframes analizados:   {', '.join(scan_result.get('timeframes', []))}")
    print(f"  Simbolos analizados:     {scan_result.get('analyzed_count', 0)}")
    print(f"  Backtests ejecutados:    {scan_result.get('backtests_executed', 0)}")
    source = scan_result.get("data_source_exchange") or "N/A"
    fallback = "yes" if scan_result.get("fallback_used") else "no"
    print(f"  Exchange:                {source}")
    print(f"  Exchange mode:           {scan_result.get('exchange_mode') or 'N/A'}")
    print(f"  Market type:             {scan_result.get('market_type') or 'spot'}")
    print(f"  Fallback used:           {fallback}")
    print(f"  Workers:                 {scan_result.get('workers', 1)}")
    print(f"  Tiempo total:            {scan_result.get('elapsed_display', '-')}")
    print(f"  Tiempo prom. por simbolo:{scan_result.get('average_symbol_display', '-')}")
    print(f"  Simbolos fallidos:       {scan_result.get('failed_symbols_count', 0)}")
    print(f"  AVOID:                   {counts.get('AVOID', 0)}")
    print(f"  Strategy profile:        {scan_result.get('strategy_profile') or 'balanced'}")
    print(f"  CSV:                     {scan_result.get('csv_path')}")
    print(f"  Markdown:                {scan_result.get('md_path')}")

    print_separator()
    print("  Top oportunidades:")
    if not rows:
        print("     - Sin resultados.")
    else:
        for row in _dedupe_scan_rows(rows, limit=10):
            print(
                "     #{rank} {symbol} | {decision} | {status} | TF {tf} | "
                "score {score} | conf {confidence}% | RR {rr} | BT {bt}".format(
                    rank=row.get("rank"),
                    symbol=row.get("symbol"),
                    decision=row.get("decision"),
                    status=row.get("validation_status") or "-",
                    tf=row.get("recommended_timeframe") or "-",
                    score=row.get("score"),
                    confidence=row.get("confidence"),
                    rr=row.get("rr_ratio"),
                    bt=row.get("backtest_verdict") or "-",
                )
            )

    warnings = scan_result.get("warnings", [])
    if warnings:
        print_separator()
        print("  Warnings del scan:")
        for warning in warnings:
            print(f"     - {warning}")

    print_separator()
    print("  Paper/analysis only. No live trading. No financial advice.")
    print(f"  Storage backend: {storage.get_storage_backend().upper()}")
    print_separator()


def print_futures_result(result: dict):
    symbol = result.get("symbol", "?")
    display_tf = result.get("recommended_timeframe") or result.get("timeframe") or "ninguna clara"
    entry_now = "sí" if result.get("entry_now") else "no"

    print_separator()
    print(f"  {symbol} - FUTURES - {display_tf}")
    print_separator()
    print(f"  Exchange:                {result.get('data_source_exchange') or 'N/A'}")
    print(f"  Exchange mode:           {result.get('exchange_mode') or 'N/A'}")
    print(f"  Market type:             {result.get('market_type') or result.get('data_source_market_type') or 'futures'}")
    if result.get("market_symbol"):
        print(f"  Market symbol:           {result.get('market_symbol')}")
    print(f"  Fallback used:           {'yes' if result.get('fallback_used') else 'no'}")
    print(f"  Direction:               {result.get('direction', 'NEUTRAL')}")
    print(f"  Decision:                {result.get('decision', 'N/A')}")
    print(f"  Entrada ahora:           {entry_now}")
    print(f"  Motivo principal:        {result.get('main_reason', 'N/A')}")
    print(f"  Strategy profile:        {result.get('strategy_profile') or 'balanced'}")
    print_separator()
    print(f"  Long score:              {result.get('long_score', 0)}/10")
    print(f"  Short score:             {result.get('short_score', 0)}/10")
    print(f"  Confianza:               {result.get('confidence', 0)}%")
    print(f"  Precio:                  {utils.format_price(result.get('price'))}")
    print_separator()
    print(f"  Entry:                   {utils.format_price(result.get('entry_price'))}")
    print(f"  Stop Loss:               {utils.format_price(result.get('stop_loss'))}")
    print(f"  Take Profit 1:           {utils.format_price(result.get('take_profit_1'))}")
    print(f"  Take Profit 2:           {utils.format_price(result.get('take_profit_2'))}")
    rr = result.get("rr_ratio")
    risk_pct = result.get("risk_pct_to_stop")
    max_leverage = result.get("suggested_leverage_max")
    print(f"  RR:                      {rr if rr is not None else 'N/A'}")
    print(f"  Riesgo al stop:          {f'{risk_pct}%' if risk_pct is not None else 'N/A'}")
    print(f"  Invalidacion:            {result.get('invalidation', 'N/A')}")
    print_separator()
    print(f"  Leverage sugerido:       {result.get('suggested_leverage_label', 'N/A')}")
    print(f"  Max leverage sugerido:   {f'{max_leverage}x' if max_leverage is not None else 'N/A'}")
    print(f"  Advertencia leverage:    {result.get('leverage_warning', 'N/A')}")
    _print_list_section("Condiciones faltantes", result.get("missing_conditions", []))
    _print_list_section("Advertencias", result.get("warnings", []))
    print_separator()
    print("  Solo análisis técnico. No consejo financiero. No live trading.")
    print(f"  Storage backend: {storage.get_storage_backend().upper()}")
    print_separator()


def print_paper_summary(summary: dict, trader: PaperTrader = None):
    """Imprime en consola el resumen actual del paper trader."""
    print_separator()
    print("  Paper Trading")
    print_separator()
    print(f"  Modo:                 {summary.get('modo')}")
    print(f"  Exchange:             {summary.get('exchange')}")
    print(f"  Capital inicial:      {summary.get('capital_inicial')}")
    print(f"  Capital actual:       {summary.get('capital_actual')}")
    print(f"  Retorno total:        {summary.get('retorno_total_pct')}%")
    print(f"  Posiciones abiertas:  {summary.get('posiciones_abiertas')}")
    print(f"  Trades cerrados:      {summary.get('trades_cerrados')}")
    print(f"  Win rate:             {summary.get('win_rate')}%")
    print(f"  Avg R:                {summary.get('avg_r_multiple')}")
    print(f"  Expectancy R:         {summary.get('expectancy_r')}")
    print(f"  Max DD:               {summary.get('max_drawdown_pct')}%")
    print(f"  Sharpe:               {summary.get('sharpe_ratio') or 'N/A'}")
    print(f"  Storage backend:      {storage.get_storage_backend().upper()}")
    if trader and trader.positions:
        print_separator()
        print("  Posiciones abiertas:")
        for position in trader.positions:
            print(
                f"     - {position.symbol} {position.direction} "
                f"entry {position.entry_price} SL {position.sl_price} TP {position.tp_price}"
            )
    print_separator()


def print_strategy_report(comparison_df, summary):
    """Imprime el resumen comparativo de estrategias en la consola."""
    print_separator()
    print("  Strategy Performance Comparison")
    print_separator()
    
    if summary:
        print(f"  Mejor PnL:        {summary['best_pnl_profile']} (${summary['best_pnl_value']:.2f})")
        print(f"  Mejor Winrate:    {summary['best_winrate_profile']} ({summary['best_winrate_value']:.1f}%)")
        print(f"  Mejor Score:      {summary['best_score_profile']} ({summary['best_score_value']:.2f})")
        print(f"  Perfiles totales: {summary['total_profiles']}")
        print_separator()

    if not comparison_df.empty:
        # Formatear tabla simple para consola
        print(f"{'Profile':<15} | {'Signals':<7} | {'Trades':<6} | {'Winrate':<7} | {'PnL':<8} | {'Score':<5}")
        print("-" * 60)
        for _, row in comparison_df.sort_values("total_pnl", ascending=False).iterrows():
            print(f"{str(row['strategy_profile']):<15} | {int(row['total_signals']):<7} | {int(row['closed_trades']):<6} | {float(row['winrate']):<6.1f}% | {float(row['total_pnl']):<8.2f} | {float(row['avg_score']):<5.2f}")
    else:
        print("  Sin datos suficientes para comparar.")
    print_separator()


def main():
    parser = argparse.ArgumentParser(description="Crypto Technical Advisor CLI")
    parser.add_argument("--symbol", default=config.DEFAULT_SYMBOL, help="Trading pair, e.g. ETH/USDT")
    parser.add_argument("--timeframe", default=None, help="Timeframe: 15m, 30m, 1h, 2h, 4h, 1d")
    parser.add_argument("--auto", action="store_true", help="Auto-select best timeframe")
    parser.add_argument("--strategy", help="Strategy profile: conservative, balanced, aggressive, scalping, swing")
    parser.add_argument("--backtest", action="store_true", help="Run quick backtest")
    parser.add_argument("--futures", action="store_true", help="Analyze futures LONG/SHORT direction")
    parser.add_argument("--scan", action="store_true", help="Scan top USDT spot pairs by volume")
    parser.add_argument("--limit", type=int, default=scanner.SCAN_LIMIT, help="Scanner symbol limit")
    parser.add_argument(
        "--scan-mode",
        choices=scanner.SCAN_MODES,
        default="fast",
        help="Scanner mode: fast (1h, 2h, 4h) or full (all timeframes)",
    )
    parser.add_argument(
        "--backtest-top",
        type=int,
        default=scanner.RUN_BACKTEST_FOR_TOP_N,
        help="Run quick backtest for top scanner candidates",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=scanner.SCANNER_MAX_WORKERS,
        help="Scanner worker threads",
    )
    parser.add_argument("--days", type=int, default=config.BACKTEST_DAYS_DEFAULT, help="Backtest days")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument("--validate-top", action="store_true", help="Validate top scan results")
    parser.add_argument("--top", type=int, default=3, help="Number of top symbols to validate")
    parser.add_argument("--update-signals", action="store_true", help="Update tracking signals")
    parser.add_argument("--run-cycle", action="store_true", help="Run full cycle (scan -> validate -> update signals)")
    parser.add_argument("--paper-start", action="store_true", help="Start continuous paper trading cycle")
    parser.add_argument("--paper-status", action="store_true", help="Show current paper trader summary")
    parser.add_argument("--paper-close", metavar="SYMBOL", help="Manually close an open paper position")
    parser.add_argument("--paper-capital", type=float, default=1000.0, help="Initial paper capital")
    parser.add_argument("--strategy-report", action="store_true", help="Compare strategy profiles performance")
    parser.add_argument("--from-date", help="Filter report from date (YYYY-MM-DD)")
    parser.add_argument("--to-date", help="Filter report to date (YYYY-MM-DD)")
    parser.add_argument("--market-type", help="Filter report by market type (spot/futures)")
    parser.add_argument("--out", help="Output path for Markdown report")
    parser.add_argument("--paper-interval", type=int, default=60, help="Minutes between paper scans")
    parser.add_argument("--paper-dry-run", action="store_true", help="Run paper cycle without opening new positions")
    parser.add_argument(
        "--exchange",
        choices=config.SUPPORTED_EXCHANGES,
        default=config.DEFAULT_EXCHANGE,
        help="Data source exchange for manual mode",
    )
    parser.add_argument(
        "--exchange-mode",
        choices=["manual", "fallback"],
        default=config.EXCHANGE_MODE,
        help="Data source mode: manual uses one exchange; fallback tries configured priority",
    )
    args = parser.parse_args()
    exchange_was_provided = "--exchange" in sys.argv

    if args.paper_status:
        trader = PaperTrader.load_from_report(exchange_id=args.exchange, capital_usdt=args.paper_capital)
        summary = trader.get_summary()
        if args.json:
            print(json.dumps({"summary": summary, "positions": [p.__dict__ for p in trader.positions]}, indent=2, default=str))
        else:
            print_paper_summary(summary, trader)
        return

    if args.paper_close:
        trader = PaperTrader.load_from_report(exchange_id=args.exchange, capital_usdt=args.paper_capital)
        closed = trader.close_position_manual(args.paper_close)
        if args.json:
            print(json.dumps({"closed": closed, "summary": trader.get_summary()}, indent=2, default=str))
        else:
            if closed:
                print(f"  Posición cerrada: {closed['symbol']} PnL {closed['net_pnl']:.4f} R {closed['r_multiple']:.3f}")
            else:
                print(f"  No hay posición abierta para {args.paper_close}")
            print_paper_summary(trader.get_summary(), trader)
        return

    if args.paper_start:
        paper_cycle.run_paper_cycle(
            exchange_id=args.exchange,
            capital_usdt=args.paper_capital,
            scan_interval_minutes=args.paper_interval,
            scan_limit=args.limit,
            scan_mode=args.scan_mode,
            workers=args.workers,
            dry_run=args.paper_dry_run,
            strategy_profile=args.strategy,
        )
        return

    if args.run_cycle:
        print("\n  Running cycle...")
        print(f"  Exchange: {args.exchange}")
        print(f"  Exchange mode: {args.exchange_mode}")
        res = cycle_runner.run_cycle(
            scan_limit=args.limit,
            top_n=args.top,
            workers=args.workers,
            exchange_id=args.exchange,
            exchange_mode=args.exchange_mode,
            strategy_profile=args.strategy,
        )
        print(f"  Scanner: {res['scan_time']:.2f} segundos")
        print(f"  Validation: {res['val_time']:.2f} segundos")
        print(f"  Signals updated: {res['signals_updated']}")
        print(f"  Cycle summary: {res['md_path']}")
        return

    if args.strategy_report:
        print("\n  Generando reporte comparativo de estrategias...")
        signals = storage.get_all_signals()
        trades = storage.get_all_paper_trades()
        
        df_sig = pd.DataFrame(signals) if signals else pd.DataFrame()
        df_trd = pd.DataFrame(trades) if trades else pd.DataFrame()
        
        # Filtros
        def filter_df(df, date_col):
            if df.empty: return df
            res = df.copy()
            if args.market_type:
                res = res[res["market_type"] == args.market_type]
            if args.from_date:
                res[date_col] = pd.to_datetime(res[date_col], utc=True, errors="coerce")
                res = res[res[date_col].dt.date >= datetime.strptime(args.from_date, "%Y-%m-%d").date()]
            if args.to_date:
                res[date_col] = pd.to_datetime(res[date_col], utc=True, errors="coerce")
                res = res[res[date_col].dt.date <= datetime.strptime(args.to_date, "%Y-%m-%d").date()]
            return res

        f_sig = filter_df(df_sig, "created_at")
        f_trd = filter_df(df_trd, "opened_at")
        
        comparison_df = performance_metrics.calculate_strategy_comparison(f_sig, f_trd)
        summary = performance_metrics.calculate_profile_summary(f_sig, f_trd)
        
        if args.json:
            out = {
                "summary": summary,
                "comparison": comparison_df.to_dict(orient="records")
            }
            print(json.dumps(out, indent=2, default=str))
        else:
            print_strategy_report(comparison_df, summary)
            
        if args.out:
            md_report = f"""# Strategy Performance Comparison Report

Generado el: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Filtros
- Desde: {args.from_date or 'Inicio'}
- Hasta: {args.to_date or 'Hoy'}
- Market: {args.market_type or 'Todos'}

## Resumen
- **Mejor PnL**: {summary.get('best_pnl_profile')} (${summary.get('best_pnl_value', 0):.2f})
- **Mejor Winrate**: {summary.get('best_winrate_profile')} ({summary.get('best_winrate_value', 0):.1f}%)
- **Mejor Score**: {summary.get('best_score_profile')} ({summary.get('best_score_value', 0):.2f})

## Tabla Comparativa
{comparison_df.to_markdown(index=False) if not comparison_df.empty else 'Sin datos.'}

---
Paper/analysis only. No financial advice.
"""
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(md_report)
            print(f"  Reporte guardado en: {args.out}")
        return

    if args.validate_top:
        print(f"\n  Validating top {args.top} scanner candidates...")
        validation_exchange = args.exchange if exchange_was_provided else None
        res = validator.run_validation(
            top_n=args.top,
            exchange_id=validation_exchange,
            exchange_mode=args.exchange_mode,
            strategy_profile=args.strategy,
        )
        if res:
            print(f"  Validacion completada. Guardada en {res['md_path']}")
        else:
            print("  No se pudo realizar la validacion. Revisa si hay scan results.")
        return

    if args.update_signals:
        print("\n  Actualizando señales de tracking...")
        res = signal_tracker.update_signals()
        print(f"  Actualizadas: {res['updated']}, Cerradas: {res['closed']}.")
        return

    if args.scan:
        print(
            f"\n  Corriendo scanner de mercado "
            f"(top {args.limit}, modo {args.scan_mode}, "
            f"backtest top {args.backtest_top}, workers {args.workers}, "
            f"exchange {args.exchange}, exchange mode {args.exchange_mode}) ..."
        )
        scan_result = scanner.run_market_scan(
            limit=args.limit,
            mode=args.scan_mode,
            backtest_top=args.backtest_top,
            workers=args.workers,
            exchange_id=args.exchange,
            exchange_mode=args.exchange_mode,
            strategy_profile=args.strategy,
        )
        if args.json:
            print(json.dumps(scan_result, indent=2, default=str))
        else:
            print_scan_result(scan_result)
        return

    symbol = args.symbol
    use_auto = args.auto or args.timeframe is None
    timeframe = args.timeframe or "1h"

    if args.futures:
        print(f"\n  Analizando FUTURES {symbol} {'(auto TF)' if use_auto else timeframe} ...")
        print(f"  Exchange: {args.exchange}")
        print(f"  Exchange mode: {args.exchange_mode}")
        if use_auto:
            result = futures_analyzer.analyze_futures_symbol_auto(
                symbol,
                exchange_id=args.exchange,
                exchange_mode=args.exchange_mode,
                strategy_profile=args.strategy,
            )
        else:
            result = futures_analyzer.analyze_futures_symbol_timeframe(
                symbol,
                timeframe,
                exchange_id=args.exchange,
                exchange_mode=args.exchange_mode,
                strategy_profile=args.strategy,
            )
        if args.json:
            print(json.dumps({"analysis": result}, indent=2, default=str))
        else:
            print_futures_result(result)
        return

    print(f"\n  Analizando {symbol} {'(auto TF)' if use_auto else timeframe} ...")
    print(f"  Exchange: {args.exchange}")
    print(f"  Exchange mode: {args.exchange_mode}")

    if use_auto:
        result = technical_analyzer.analyze_symbol_auto(
            symbol,
            exchange_id=args.exchange,
            exchange_mode=args.exchange_mode,
            strategy_profile=args.strategy,
        )
    else:
        result = technical_analyzer.analyze_symbol_timeframe(
            symbol,
            timeframe,
            exchange_id=args.exchange,
            exchange_mode=args.exchange_mode,
            strategy_profile=args.strategy,
        )

    bt_result = None
    if args.backtest:
        bt_tf = result.get("recommended_timeframe") if use_auto else timeframe
        if use_auto and not bt_tf:
            print("  Auto no encontro temporalidad clara; no se ejecuta backtest principal.")
        else:
            print(f"  Corriendo backtest {symbol} / {bt_tf} ({args.days} dias) ...")
            bt_result = backtester.run_quick_backtest(
                symbol,
                bt_tf,
                days=args.days,
                exchange_mode=args.exchange_mode,
                market_type="spot",
                mode="spot",
                strategy_profile=args.strategy,
            )
            result = technical_analyzer.apply_backtest_to_analysis(result, bt_result)

    try:
        report_builder.save_report(result, bt_result)
        print("  Reporte guardado en outputs/")
    except Exception as e:
        print(f"  (No se pudo guardar reporte: {e})")

    if args.json:
        output = {"analysis": result, "backtest": bt_result}
        print(json.dumps(output, indent=2, default=str))
    else:
        print_result(result, bt_result)


if __name__ == "__main__":
    main()
