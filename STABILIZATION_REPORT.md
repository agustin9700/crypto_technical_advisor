# Stabilization Report

## Cambios realizados

- Se eliminaron API keys hardcodeadas de `start_paper.sh` y `start_paper.bat`.
- Se agrego `.env.example` y se reforzo `.gitignore`.
- Se agrego `tools/package_project.py` para generar un zip limpio.
- Se agrego routing explicito `spot`/`futures` en `data_provider.py`.
- Se agrego `rate_limiter.py` para limitar llamadas CCXT globalmente.
- `strategy_engine.py` centraliza la evaluacion y `backtester.py` usa `evaluate_signal()`.
- SQLite quedo integrado al flujo real con fallback CSV controlado.
- `paper_trader.py`, `signal_tracker.py`, `scanner.py`, `validator.py` y `cycle_runner.py` ya no escriben CSV cuando `STORAGE_BACKEND=sqlite`.
- `futures_analyzer.py` delega el scoring en `strategy_engine.evaluate_signal()`, la misma fuente usada por `backtester.py`.
- UI/CLI muestran exchange real, fallback, market type y backend de storage.

## Archivos modificados

Ver `git status --short` para el listado exacto del workspace.

## Problemas encontrados

- Habia secretos reales en scripts de arranque.
- Futures podia pedir velas spot por default del provider.
- Backtester usaba logica simplificada distinta al analyzer.
- SQLite existia como modulo pero no estaba integrado al flujo real.
- Futures tenia dos fuentes activas de scoring.
- `outputs/` contiene archivos runtime locales que no deben empaquetarse.

## Problemas corregidos

- Scripts de arranque leen variables de entorno y no imprimen secretos.
- Futures solicita `market_type=futures` y no hace fallback silencioso a spot.
- Backtester acepta `exchange_id`, `exchange_mode`, `market_type` y `mode`.
- Packager excluye secretos, runtime, caches, virtualenvs y repositorio git.
- SQLite tiene transacciones, WAL e inserciones idempotentes para senales/trades.
- Scanner, validator, signal tracker, paper trader y cycle runner usan SQLite cuando `STORAGE_BACKEND=sqlite`.
- Futures Analyzer y Backtester comparten la misma logica de scoring mediante `strategy_engine.py`.

## Problemas pendientes

- Reducir duplicacion legacy no activa que queda en `futures_analyzer.py`.
- Agregar datasets matematicos validados contra TradingView u otra referencia externa.
- Migrar analiticas historicas avanzadas de equity a tablas dedicadas si se necesita reporting mas profundo.

## Tests ejecutados

- `python -m compileall data_provider.py technical_analyzer.py futures_analyzer.py strategy_engine.py backtester.py scanner.py validator.py paper_trader.py signal_tracker.py cycle_runner.py app.py cli.py storage.py rate_limiter.py`
- `python tests_pipeline_smoke.py`
- `python tests_futures_smoke.py`
- `python tests_storage_sqlite.py`
- `python tests_strategy_engine.py`
- `python tests_market_type_routing.py`
- `python tests_package_project.py`
- `python check_deploy_ready.py`
- `python tools/package_project.py --dry-run`
- `python tools/package_project.py`

## Resultado de tests

Los smoke tests y tests nuevos pasaron. El check de deploy valida los archivos incluidos por el packager, no los outputs runtime locales que quedan excluidos del zip.

## Como correr el proyecto

```bash
streamlit run app.py
python cli.py --symbol BTC/USDT --auto --exchange kucoin
python cli.py --futures --symbol BTC/USDT --auto --exchange binance
python cli.py --scan --limit 20 --scan-mode fast --exchange kucoin
```

## Como generar paquete limpio

```bash
python tools/package_project.py --dry-run
python tools/package_project.py
```

Salida esperada:

```text
dist/crypto_technical_advisor_clean.zip
```
