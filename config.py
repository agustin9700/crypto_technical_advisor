SUPPORTED_EXCHANGES = ["bingx", "kraken", "kucoin", "okx", "binance"]
DEFAULT_EXCHANGE = "bingx"
EXCHANGE_PRIORITY = ["bingx", "kraken", "kucoin"]
EXCHANGE_MODE = "manual"  # "manual" or "fallback"

# Manual mode uses only DEFAULT_EXCHANGE unless overridden by CLI/UI.
# Fallback mode tries EXCHANGE_PRIORITY in order.
# Binance can be used locally, but may fail in cloud with HTTP 451 restricted location.

TIMEFRAMES = ["15m", "30m", "1h", "2h", "4h", "1d"]

PRIMARY_TIMEFRAMES = ["1h", "2h", "4h"]

SPOT_ONLY = True

MIN_24H_QUOTE_VOLUME_USDT = 5_000_000

DEFAULT_SYMBOL = "ETH/USDT"

ATR_PERIOD = 14
RSI_PERIOD = 14
EMA_FAST = 20
EMA_MID = 50
EMA_LONG = 200
VOLUME_MA_PERIOD = 20

ATR_SL_MULT = 2.0
ATR_TP_MULT = 3.0

MIN_RR_RATIO = 1.5

FEE_PCT = 0.001
SLIPPAGE_PCT = 0.0005

BACKTEST_DAYS_DEFAULT = 365
INITIAL_CAPITAL = 10_000

OUTPUT_DIR = "outputs"
