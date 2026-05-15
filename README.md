# Crypto Technical Advisor

Streamlit dashboard para analisis tecnico crypto.

- SPOT mode = long-only.
- FUTURES mode = analiza posible LONG o SHORT.
- No ejecuta ordenes.
- No usa API keys.
- No calcula liquidacion exacta todavia.

## Local

```powershell
.\run.ps1
```

Or manually:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

## CLI

```bash
python cli.py --scan --limit 20 --scan-mode fast --workers 5
python cli.py --validate-top --top 3
python cli.py --update-signals
python cli.py --run-cycle --limit 20 --top 3 --workers 5
python cli.py --scan --limit 20 --exchange-mode fallback
python cli.py --futures --symbol BTC/USDT --auto
python cli.py --futures --symbol ETH/USDT --timeframe 1h --exchange kucoin --exchange-mode manual
```

## Fase de Estrategias y Performance

- **Strategy Profiles**: 5 perfiles configurables (`conservative`, `balanced`, `aggressive`, `scalping`, `swing`).
- **Dashboard de Performance**: Visualización de señales y paper trades desde SQLite.
- **Comparación de Estrategias**: Pestaña dedicada para comparar el rendimiento real de cada perfil.
- **Reportes CLI**: Generación de reportes Markdown mediante `python cli.py --strategy-report`.

## Exchange defaults

Default exchange:
- **Binance**

Fallback order:
1. Binance
2. KuCoin

Manual mode:
- Respeta el exchange elegido por el usuario.

Fallback mode:
- Intenta Binance primero.
- Si Binance falla, intenta KuCoin.

## Local

- No se deben guardar API keys en archivos versionables. Usar variables de entorno o un `.env` local ignorado por git.
- `.env.example` documenta las variables soportadas sin secretos reales.
- SPOT usa datos spot. FUTURES solicita mercado futures real; si el exchange/símbolo no lo soporta, devuelve warning/error claro en vez de caer a spot en silencio.
- `backtester.run_quick_backtest()` usa `strategy_engine.evaluate_signal()` para evaluar la misma capa de estrategia que consume el analyzer.
- `futures_analyzer.py` delega su scoring en `strategy_engine.evaluate_signal()`, evitando divergencia con backtests futures.
- SQLite es el backend default (`STORAGE_BACKEND=sqlite`). CSV queda disponible como fallback legacy con `STORAGE_BACKEND=csv`.
- `rate_limiter.py` aplica un límite global configurable antes de llamadas CCXT.

## Configuración segura

```bash
cp .env.example .env
```

Completar `.env` localmente y no commitearlo. Variables principales:

```env
PAPER_API_KEY=
PAPER_API_SECRET=
PAPER_EXCHANGE=binance
EXCHANGE_ID=binance
EXCHANGE_MODE=manual
MARKET_TYPE=spot
STORAGE_BACKEND=sqlite
DEFAULT_STRATEGY_PROFILE=balanced
```

## Paper trading

Git Bash:

```bash
export PAPER_API_KEY="tu_api_key"
export PAPER_API_SECRET="tu_api_secret"
bash start_paper.sh
```

PowerShell/CMD:

```bat
set PAPER_API_KEY=tu_api_key
set PAPER_API_SECRET=tu_api_secret
start_paper.bat
```

## Tests

```bash
python -m py_compile *.py
python tests_pipeline_smoke.py
python tests_futures_smoke.py
python tests_storage_sqlite.py
python tests_strategy_engine.py
python tests_market_type_routing.py
python tests_package_project.py
```

Si `pytest` está instalado:

```bash
pytest -q
```

## Paquete limpio

```bash
python tools/package_project.py --dry-run
python tools/package_project.py
```

El zip se genera en `dist/crypto_technical_advisor_clean.zip` y excluye `.git/`, `.venv/`, `venv/`, `outputs/`, caches, `.env`, logs, temporales y zips previos.

## Deploy Streamlit Community Cloud

1. Subir el repo a GitHub.
2. Entrar a https://share.streamlit.io
3. New app / Deploy an app.
4. Elegir repo, branch y `app.py`.
5. En Advanced settings elegir la misma version de Python usada localmente.
6. Deploy.

## Deploy notes

Binance may block some cloud providers with HTTP 451 restricted location.
If Binance fails on Render/Streamlit Cloud, use Diagnostics / Binance from server to confirm.
The app is paper/analysis only. No live trading. No API keys.
Only KuCoin and Binance are enabled. KuCoin is the default and recommended scanner source.
Manual exchange selection uses the selected exchange only.
Fallback mode tries KuCoin first and then Binance.

## Disclaimer

Paper/analysis only. No live trading. No financial advice.
