import os


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


SUPPORTED_EXCHANGES = ["kucoin", "binance"]
DEFAULT_EXCHANGE = os.getenv("EXCHANGE_ID", "kucoin").strip().lower()
EXCHANGE_PRIORITY = ["kucoin", "binance"]
EXCHANGE_MODE = os.getenv("EXCHANGE_MODE", "manual").strip().lower()  # "manual" or "fallback"
DEFAULT_MARKET_TYPE = os.getenv("MARKET_TYPE", "spot").strip().lower()

# Manual mode uses only DEFAULT_EXCHANGE unless overridden by CLI/UI.
# Fallback mode tries EXCHANGE_PRIORITY in order.
# KuCoin is the default source. Binance can be used locally, but may fail in
# some cloud providers with HTTP 451 restricted location.

TIMEFRAMES = ["15m", "30m", "1h", "2h", "4h", "1d"]

PRIMARY_TIMEFRAMES = ["1h", "2h", "4h"]

SPOT_ONLY = False

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
RISK_PER_TRADE_PCT = 0.01
MAX_OPEN_TRADES = 3

OUTPUT_DIR = "outputs"

STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "sqlite").strip().lower()
SQLITE_PATH = os.getenv("SQLITE_PATH", "outputs/crypto_technical_advisor.sqlite3")

GLOBAL_RATE_LIMIT_ENABLED = _env_bool("GLOBAL_RATE_LIMIT_ENABLED", True)
GLOBAL_RATE_LIMIT_REQUESTS_PER_SECOND = _env_float("GLOBAL_RATE_LIMIT_REQUESTS_PER_SECOND", 3.0)
GLOBAL_RATE_LIMIT_MAX_RETRIES = _env_int("GLOBAL_RATE_LIMIT_MAX_RETRIES", 2)
GLOBAL_RATE_LIMIT_BACKOFF_SECONDS = _env_float("GLOBAL_RATE_LIMIT_BACKOFF_SECONDS", 1.0)
SCANNER_MAX_WORKERS = _env_int("SCANNER_MAX_WORKERS", 4)
