# Changelog

## Stabilization Phase

- Removed hardcoded paper-trading credentials from startup scripts.
- Added `.env.example` with safe placeholders.
- Added clean package generator at `tools/package_project.py`.
- Added optional CSV-to-SQLite importer at `tools/import_csv_to_sqlite.py`.
- Added market type routing for `spot` and `futures` data requests.
- Added global CCXT request limiter with configurable requests per second.
- Added `strategy_engine.py` and routed backtesting through the shared strategy evaluator.
- Integrated SQLite storage into paper trading, signal tracking, scanner, validator and cycle runner.
- Routed Futures Analyzer scoring through the same `strategy_engine.evaluate_signal()` used by backtesting.
- Added tests for SQLite storage, strategy engine, market routing and packaging exclusions.
- Updated CLI/UI output to show exchange, fallback and market type metadata.

## Known Limitations

- CSV persistence remains available with `STORAGE_BACKEND=csv` for backwards compatibility.
- Some inactive legacy helper code remains in futures modules and can be removed in a later cleanup.
- Futures availability depends on CCXT exchange support and symbol naming.
