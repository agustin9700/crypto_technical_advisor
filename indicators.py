import pandas as pd
import numpy as np
import config


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(com=period - 1, adjust=False).mean()


def macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    ema_fast = ema(df["close"], fast)
    ema_slow = ema(df["close"], slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return pd.DataFrame({"macd": macd_line, "macd_signal": signal_line, "macd_hist": hist})


def bollinger_bands(df: pd.DataFrame, period: int = 20, std: float = 2.0) -> pd.DataFrame:
    mid = df["close"].rolling(period).mean()
    dev = df["close"].rolling(period).std()
    return pd.DataFrame({
        "bb_mid": mid,
        "bb_upper": mid + std * dev,
        "bb_lower": mid - std * dev,
    })


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["ema20"] = ema(df["close"], config.EMA_FAST)
    df["ema50"] = ema(df["close"], config.EMA_MID)
    df["ema200"] = ema(df["close"], config.EMA_LONG)

    df["rsi"] = rsi(df["close"], config.RSI_PERIOD)

    df["atr"] = atr(df, config.ATR_PERIOD)
    df["atr_pct"] = df["atr"] / df["close"] * 100

    macd_df = macd(df)
    df["macd"] = macd_df["macd"]
    df["macd_signal"] = macd_df["macd_signal"]
    df["macd_hist"] = macd_df["macd_hist"]

    bb_df = bollinger_bands(df)
    df["bb_mid"] = bb_df["bb_mid"]
    df["bb_upper"] = bb_df["bb_upper"]
    df["bb_lower"] = bb_df["bb_lower"]

    df["vol_ma20"] = df["volume"].rolling(config.VOLUME_MA_PERIOD).mean()
    df["vol_ratio"] = df["volume"] / df["vol_ma20"].replace(0, np.nan)

    return df
