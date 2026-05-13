# Crypto Technical Advisor

Streamlit dashboard para analisis tecnico crypto.

- SPOT mode = long-only.
- FUTURES mode = analiza posible LONG o SHORT.
- No ejecuta ordenes.
- No usa API keys.
- No calcula liquidacion exacta todavia.

## Local

```bash
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
python cli.py --futures --symbol ETH/USDT --timeframe 1h --exchange okx
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
For scanner runs on Render, KuCoin is currently recommended: recent tests returned the full top 10 with 0 failed symbols.
Manual exchange selection remains available in the UI/CLI and avoids silent exchange changes.
BingX is available and worked for individual BTC/USDT analysis, but validate scanner coverage before using it as the scanner source.
Kraken is useful for majors, but it has poor alt coverage for scanner runs.
OKX is available, but review symbols/stablecoin filtering and BTC/USDT behavior before using it as the scanner default.
Fallback mode can try BingX -> Kraken -> KuCoin.

## Disclaimer

Paper/analysis only. No live trading. No financial advice.
