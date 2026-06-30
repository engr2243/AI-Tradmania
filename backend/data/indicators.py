import pandas as pd
import numpy as np
from typing import Optional


def compute_indicators(ohlcv: list) -> dict:
    if not ohlcv or len(ohlcv) < 20:
        return {}

    df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    result = {}

    # RSI
    result["rsi_14"] = _rsi(close, 14)

    # MACD
    macd_line, signal_line, histogram = _macd(close)
    result["macd"] = macd_line
    result["macd_signal"] = signal_line
    result["macd_histogram"] = histogram
    result["macd_trend"] = "bullish" if (histogram or 0) > 0 else "bearish"

    # Bollinger Bands
    bb = _bollinger_bands(close, 20, 2)
    result["bb_upper"] = bb["upper"]
    result["bb_middle"] = bb["middle"]
    result["bb_lower"] = bb["lower"]
    result["bb_pct"] = bb["pct"]  # 0=lower, 1=upper
    result["bb_squeeze"] = bb["width"] < bb["avg_width"] * 0.7

    # EMAs
    result["ema_9"] = _ema(close, 9)
    result["ema_21"] = _ema(close, 21)
    result["ema_50"] = _ema(close, 50) if len(close) >= 50 else None
    result["ema_trend"] = "bullish" if result["ema_9"] > result["ema_21"] else "bearish"

    # Volume analysis
    avg_vol = volume.rolling(20).mean().iloc[-1]
    result["volume_current"] = round(float(volume.iloc[-1]), 4)
    result["volume_avg_20"] = round(float(avg_vol), 4)
    result["volume_ratio"] = round(float(volume.iloc[-1] / avg_vol), 2) if avg_vol > 0 else 1.0

    # ATR (volatility)
    result["atr_14"] = _atr(high, low, close, 14)

    # Price momentum
    result["momentum_5"] = round(float((close.iloc[-1] / close.iloc[-6] - 1) * 100), 2)
    result["momentum_10"] = round(float((close.iloc[-1] / close.iloc[-11] - 1) * 100), 2) if len(close) > 10 else None

    # Current price
    result["current_price"] = round(float(close.iloc[-1]), 2)
    result["prev_close"] = round(float(close.iloc[-2]), 2)

    return result


def _rsi(series: pd.Series, period: int = 14) -> Optional[float]:
    if len(series) < period + 1:
        return None
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    val = rsi.iloc[-1]
    return round(float(val), 2) if not np.isnan(val) else None


def _ema(series: pd.Series, period: int) -> Optional[float]:
    if len(series) < period:
        return None
    val = series.ewm(span=period, adjust=False).mean().iloc[-1]
    return round(float(val), 2)


def _macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    if len(series) < slow + signal:
        return None, None, None
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return (
        round(float(macd_line.iloc[-1]), 4),
        round(float(signal_line.iloc[-1]), 4),
        round(float(histogram.iloc[-1]), 4),
    )


def _bollinger_bands(series: pd.Series, period: int = 20, std_dev: float = 2):
    sma = series.rolling(period).mean()
    std = series.rolling(period).std()
    upper = sma + std_dev * std
    lower = sma - std_dev * std
    width = upper - lower

    current_close = series.iloc[-1]
    upper_val = float(upper.iloc[-1])
    lower_val = float(lower.iloc[-1])
    middle_val = float(sma.iloc[-1])
    width_val = float(width.iloc[-1])
    avg_width = float(width.rolling(20).mean().iloc[-1]) if len(width) >= 20 else width_val

    pct = (current_close - lower_val) / (upper_val - lower_val) if (upper_val - lower_val) > 0 else 0.5

    return {
        "upper": round(upper_val, 2),
        "middle": round(middle_val, 2),
        "lower": round(lower_val, 2),
        "width": round(width_val, 2),
        "avg_width": round(avg_width, 2),
        "pct": round(float(pct), 3),
    }


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> Optional[float]:
    if len(close) < period + 1:
        return None
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(period).mean().iloc[-1]
    return round(float(atr), 4) if not np.isnan(atr) else None


def format_indicators_summary(ind: dict) -> str:
    if not ind:
        return "Insufficient data for indicators."

    lines = []
    lines.append(f"RSI(14): {ind.get('rsi_14', 'N/A')}")
    lines.append(f"MACD: {ind.get('macd_trend', 'N/A')} (histogram: {ind.get('macd_histogram', 'N/A')})")
    lines.append(f"Bollinger Band %B: {ind.get('bb_pct', 'N/A')} (squeeze: {ind.get('bb_squeeze', False)})")
    lines.append(f"EMA Trend: {ind.get('ema_trend', 'N/A')} (EMA9: {ind.get('ema_9')}, EMA21: {ind.get('ema_21')})")
    lines.append(f"Volume Ratio vs 20-avg: {ind.get('volume_ratio', 'N/A')}x")
    lines.append(f"Momentum 5-bar: {ind.get('momentum_5', 'N/A')}%")
    lines.append(f"ATR(14): {ind.get('atr_14', 'N/A')}")
    return "\n".join(lines)
