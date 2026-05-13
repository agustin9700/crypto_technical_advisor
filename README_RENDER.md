# Deploy on Render

## Settings

Service type: Web Service
Runtime: Python
Build command:
pip install -r requirements.txt

Start command:
streamlit run app.py --server.port=$PORT --server.address=0.0.0.0

## Notes

- Free service spins down after inactivity.
- Local files in outputs/ are ephemeral on free plan.
- If Binance fails, check Render logs.
