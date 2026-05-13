# Crypto Technical Advisor

Streamlit dashboard para analisis tecnico crypto spot long-only.

## Local

```bash
pip install -r requirements.txt
streamlit run app.py
```

## CLI

```bash
python cli.py --scan --limit 20 --scan-mode fast --workers 5
python cli.py --validate-top --top 3
python cli.py --update-signals
python cli.py --run-cycle --limit 20 --top 3 --workers 5
```

## Deploy Streamlit Community Cloud

1. Subir el repo a GitHub.
2. Entrar a https://share.streamlit.io
3. New app / Deploy an app.
4. Elegir repo, branch y `app.py`.
5. En Advanced settings elegir la misma version de Python usada localmente.
6. Deploy.

## Disclaimer

Paper/analysis only. No live trading. No financial advice.
