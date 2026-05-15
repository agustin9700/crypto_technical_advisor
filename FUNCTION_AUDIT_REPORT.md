# Function Audit Report

## Estado general
**APROBADO CON OBSERVACIONES**
El sistema es funcional y estable, pero presenta redundancias en funciones de utilidad (redondeo, formateo, manejo de volumen) que están duplicadas en múltiples módulos. Se recomienda una fase de consolidación en `utils.py`.

## Funciones core que deben conservarse
- `strategy_engine.evaluate_signal`: Motor principal de decisión.
- `data_provider.fetch_ohlcv`: Punto de entrada único para datos de mercado.
- `storage.SQLiteStorage`: Capa de persistencia principal.
- `scanner.run_scan`: Lógica de escaneo masivo y validación.
- `paper_trader.PaperTrader`: Gestión de posiciones simuladas.

## Funciones UI que deben conservarse
- `app.render_performance_dashboard_tab`: Vista de métricas.
- `app.render_paper_trading_tab`: Interfaz de simulación.
- `app.render_result_summary`: Formateo de resultados de análisis.

## Funciones CLI que deben conservarse
- `cli.print_scan_result`: Formateo de tablas de escaneo.
- `cli.print_strategy_report`: Reporte de comparación de perfiles.
- `paper_cycle.run_paper_cycle`: Loop de ejecución de paper trading.

## Funciones legacy CSV conservadas
- `storage.CSVStorage` (dentro de lógica de fallback): Se mantiene para compatibilidad con datos históricos no migrados.
- `import_csv_to_sqlite.py`: Herramienta esencial para la transición.

## Funciones duplicadas detectadas (Candidatas a consolidar en utils.py)
- `_unique_items`: Duplicada en `app.py`, `cli.py`, `report_builder.py`, `scanner.py`.
- `_safe_float`: Duplicada en `futures_analyzer.py`, `scanner.py`, `strategy_engine.py`.
- `_round_value`: Duplicada en `futures_analyzer.py`, `strategy_engine.py`.
- `_now_utc`: Duplicada en `paper_trader.py`, `scanner.py`.
- `_clean_optional`: Duplicada en `validator.py`, `signal_tracker.py`, `storage.py`.

## Funciones candidatas a borrar (DELETE_SAFE)
- `data_provider.get_exchange_for_symbol`: Sin referencias detectadas.
- `data_provider.fetch_ticker_volume`: Sin referencias (se usa la versión con fallback).
- `data_provider.is_symbol_liquid`: Lógica absorbida por el scanner.
- `diagnostics.run_binance_diagnostics`: Superada por `run_exchange_diagnostics`.
- `report_builder.markdown_matches_symbol`: Código muerto.
- `utils.decision_color`: No se usa en la UI actual (Streamlit usa lógica propia o badges).
- `utils.decision_emoji`: No se usa.
- `utils.verdict_emoji`: No se usa.

## Funciones que requieren revisión manual
- `strategy_engine._legacy_evaluate_futures_row`: Marcada como legacy, verificar si el backtester aún la necesita para registros muy antiguos.
- `technical_analyzer._compute_score` (y proxies): Evaluar si eliminarlos mejora la claridad o si se prefieren como capa de abstracción.

## Riesgos detectados
1. **Regresión en Fallback**: Eliminar funciones de `data_provider` sin verificar el modo "fallback" en tiempo de ejecución.
2. **KeyError en UI**: Al consolidar `_unique_items`, asegurar que el manejo de nulos sea idéntico para no romper el Dashboard.
