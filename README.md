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
python cli.py --scan --limit 20 --scan-mode fast --exchange kucoin --workers 5
python cli.py --validate-top --top 3
python cli.py --update-signals
python cli.py --run-cycle --limit 20 --top 3 --workers 5 --exchange kucoin
python cli.py --scan --limit 20 --exchange-mode fallback
python cli.py --futures --symbol BTC/USDT --auto --exchange kucoin
python cli.py --futures --symbol ETH/USDT --timeframe 1h --exchange binance
```

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
