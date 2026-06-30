import pandas as pd
import numpy as np
from typing import Optional


# ─── Main entry point ────────────────────────────────────────────────────────

def compute_indicators(ohlcv: list) -> dict:
    if not ohlcv or len(ohlcv) < 20:
        return {}

    df = _to_df(ohlcv)
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    result = {}

    result["rsi_14"] = _rsi(close, 14)
    result["rsi_7"] = _rsi(close, 7)

    macd_line, signal_line, histogram = _macd(close)
    result["macd"] = macd_line
    result["macd_signal"] = signal_line
    result["macd_histogram"] = histogram
    result["macd_trend"] = "bullish" if (histogram or 0) > 0 else "bearish"
    result["macd_crossing"] = _macd_crossing(close)

    bb = _bollinger_bands(close, 20, 2)
    result.update({f"bb_{k}": v for k, v in bb.items()})

    result["ema_9"] = _ema(close, 9)
    result["ema_21"] = _ema(close, 21)
    result["ema_50"] = _ema(close, 50) if len(close) >= 50 else None
    result["ema_200"] = _ema(close, 200) if len(close) >= 200 else None
    result["ema_trend"] = "bullish" if (result["ema_9"] or 0) > (result["ema_21"] or 0) else "bearish"
    result["golden_cross"] = _golden_cross(close)

    avg_vol = volume.rolling(20).mean().iloc[-1]
    result["volume_current"] = round(float(volume.iloc[-1]), 4)
    result["volume_avg_20"] = round(float(avg_vol), 4)
    result["volume_ratio"] = round(float(volume.iloc[-1] / avg_vol), 2) if avg_vol > 0 else 1.0

    result["atr_14"] = _atr(high, low, close, 14)
    result["adx_14"] = _adx(high, low, close, 14)
    result["regime"] = _market_regime(result.get("adx_14"))

    result["vwap"] = _vwap(df)
    result["momentum_5"] = round(float((close.iloc[-1] / close.iloc[-6] - 1) * 100), 2)
    result["momentum_10"] = round(float((close.iloc[-1] / close.iloc[-11] - 1) * 100), 2) if len(close) > 11 else None

    result["current_price"] = round(float(close.iloc[-1]), 2)
    result["prev_close"] = round(float(close.iloc[-2]), 2)

    sr = detect_support_resistance(ohlcv)
    result["support_levels"] = sr["support"]
    result["resistance_levels"] = sr["resistance"]
    result["nearest_support"] = sr["nearest_support"]
    result["nearest_resistance"] = sr["nearest_resistance"]

    return result


def compute_multi_timeframe(ohlcv_mtf: dict) -> dict:
    """Compute indicators for each timeframe and return alignment summary."""
    tf_indicators = {}
    for tf, ohlcv in (ohlcv_mtf or {}).items():
        if ohlcv and len(ohlcv) >= 20:
            tf_indicators[tf] = compute_indicators(ohlcv)

    alignment = _compute_mtf_alignment(tf_indicators)
    return {"by_timeframe": tf_indicators, "alignment": alignment}


# ─── Multi-timeframe alignment ────────────────────────────────────────────────

def _compute_mtf_alignment(tf_ind: dict) -> dict:
    """Score confluence across 5m / 1h / 4h."""
    signals = {}
    for tf, ind in tf_ind.items():
        if not ind:
            continue
        bullish_votes = 0
        bearish_votes = 0

        if ind.get("ema_trend") == "bullish":
            bullish_votes += 1
        else:
            bearish_votes += 1

        if ind.get("macd_trend") == "bullish":
            bullish_votes += 1
        else:
            bearish_votes += 1

        rsi = ind.get("rsi_14")
        if rsi:
            if rsi < 45:
                bullish_votes += 1
            elif rsi > 55:
                bearish_votes += 1

        signals[tf] = {
            "bullish_votes": bullish_votes,
            "bearish_votes": bearish_votes,
            "bias": "bullish" if bullish_votes > bearish_votes else "bearish" if bearish_votes > bullish_votes else "neutral",
            "rsi": rsi,
            "ema_trend": ind.get("ema_trend"),
            "macd_trend": ind.get("macd_trend"),
            "regime": ind.get("regime"),
            "adx": ind.get("adx_14"),
        }

    # Overall confluence score
    biases = [v["bias"] for v in signals.values()]
    bullish_tfs = biases.count("bullish")
    bearish_tfs = biases.count("bearish")
    total_tfs = len(biases)

    if total_tfs == 0:
        confluence = "insufficient_data"
        score = 0
    elif bullish_tfs == total_tfs:
        confluence = "strong_bullish"
        score = 3
    elif bearish_tfs == total_tfs:
        confluence = "strong_bearish"
        score = -3
    elif bullish_tfs > bearish_tfs:
        confluence = "mild_bullish"
        score = 1
    elif bearish_tfs > bullish_tfs:
        confluence = "mild_bearish"
        score = -1
    else:
        confluence = "mixed"
        score = 0

    return {
        "per_tf": signals,
        "bullish_timeframes": bullish_tfs,
        "bearish_timeframes": bearish_tfs,
        "confluence": confluence,
        "score": score,
        "description": _mtf_description(signals),
    }


def _mtf_description(signals: dict) -> str:
    parts = []
    for tf, s in signals.items():
        parts.append(f"{tf}: {s['bias'].upper()} (EMA {s['ema_trend']}, MACD {s['macd_trend']}, RSI {s['rsi'] or 'N/A'})")
    return " | ".join(parts)


# ─── Signal scorecard ─────────────────────────────────────────────────────────

def build_signal_scorecard(
    ind: dict,
    mtf_alignment: dict,
    fear_greed: Optional[dict],
    funding_rate: Optional[dict],
) -> dict:
    """
    Produce a numeric score for each signal category.
    Returns scores and a total, ready to drop into the Claude prompt.
    """
    scores = {}

    # 1. Trend (EMA alignment + golden cross)
    trend_score = 0
    if ind.get("ema_trend") == "bullish":
        trend_score += 1
    if ind.get("golden_cross") == "golden":
        trend_score += 1
    elif ind.get("golden_cross") == "death":
        trend_score -= 2
    if ind.get("ema_50") and ind.get("ema_200"):
        if ind["ema_50"] > ind["ema_200"]:
            trend_score += 1
        else:
            trend_score -= 1
    scores["trend"] = max(-3, min(3, trend_score))

    # 2. Momentum (MACD + RSI)
    momentum_score = 0
    if ind.get("macd_trend") == "bullish":
        momentum_score += 1
    if ind.get("macd_crossing") == "bullish_cross":
        momentum_score += 1
    elif ind.get("macd_crossing") == "bearish_cross":
        momentum_score -= 1
    rsi = ind.get("rsi_14")
    if rsi:
        if rsi < 30:
            momentum_score += 2   # oversold
        elif rsi < 45:
            momentum_score += 1
        elif rsi > 70:
            momentum_score -= 2   # overbought
        elif rsi > 55:
            momentum_score -= 1
    scores["momentum"] = max(-3, min(3, momentum_score))

    # 3. Volume confirmation
    vol_ratio = ind.get("volume_ratio", 1.0)
    if vol_ratio >= 2.0:
        scores["volume"] = 2
    elif vol_ratio >= 1.3:
        scores["volume"] = 1
    elif vol_ratio < 0.7:
        scores["volume"] = -1
    else:
        scores["volume"] = 0

    # 4. Multi-timeframe confluence
    mtf_score = mtf_alignment.get("score", 0) if mtf_alignment else 0
    scores["mtf_confluence"] = max(-3, min(3, mtf_score))

    # 5. Sentiment (Fear & Greed — contrarian)
    sentiment_score = 0
    if fear_greed:
        fg = fear_greed["score"]
        if fg <= 20:
            sentiment_score = 2    # extreme fear → buy
        elif fg <= 35:
            sentiment_score = 1
        elif fg >= 80:
            sentiment_score = -2   # extreme greed → sell
        elif fg >= 65:
            sentiment_score = -1
    scores["sentiment"] = sentiment_score

    # 6. Funding rate (contrarian)
    funding_score = 0
    if funding_rate:
        rate = funding_rate["rate"]
        if rate > 0.001:           # > 0.1% → over-leveraged longs → bearish
            funding_score = -2
        elif rate > 0.0005:
            funding_score = -1
        elif rate < -0.0005:       # negative → shorts squeezable → bullish
            funding_score = 2
        elif rate < 0:
            funding_score = 1
    scores["funding_rate"] = funding_score

    # 7. Bollinger Band position
    bb_pct = ind.get("bb_pct", 0.5)
    if bb_pct is not None:
        if bb_pct < 0.15:
            scores["bb_position"] = 2     # near lower band → oversold
        elif bb_pct < 0.35:
            scores["bb_position"] = 1
        elif bb_pct > 0.85:
            scores["bb_position"] = -2    # near upper band → overbought
        elif bb_pct > 0.65:
            scores["bb_position"] = -1
        else:
            scores["bb_position"] = 0
    else:
        scores["bb_position"] = 0

    total = sum(scores.values())
    max_possible = 3 + 3 + 2 + 3 + 2 + 2 + 2  # 17
    min_possible = -17
    normalized_pct = round((total - min_possible) / (max_possible - min_possible) * 100, 1)

    return {
        "scores": scores,
        "total": total,
        "max_possible": max_possible,
        "normalized_pct": normalized_pct,
        "overall_bias": "bullish" if total > 2 else "bearish" if total < -2 else "neutral",
    }


# ─── Support & Resistance ────────────────────────────────────────────────────

def detect_support_resistance(ohlcv: list, lookback: int = 100, cluster_pct: float = 0.008) -> dict:
    """Detect key S/R levels by finding price clusters with multiple touches."""
    if not ohlcv or len(ohlcv) < 20:
        return {"support": [], "resistance": [], "nearest_support": None, "nearest_resistance": None}

    df = _to_df(ohlcv[-lookback:])
    current_price = float(df["close"].iloc[-1])
    highs = df["high"].tolist()
    lows = df["low"].tolist()

    def cluster_levels(prices: list, is_resistance: bool) -> list:
        prices = sorted(prices, reverse=is_resistance)
        levels = []
        for p in prices:
            merged = False
            for i, lvl in enumerate(levels):
                if abs(p - lvl["price"]) / lvl["price"] < cluster_pct:
                    # Merge into existing cluster
                    levels[i]["touches"] += 1
                    levels[i]["price"] = (levels[i]["price"] * levels[i]["touches"] + p) / (levels[i]["touches"] + 1)
                    merged = True
                    break
            if not merged:
                levels.append({"price": p, "touches": 1})
        # Only keep levels touched 2+ times
        return [round(l["price"], 2) for l in levels if l["touches"] >= 2]

    resistance_levels = [r for r in cluster_levels(highs, True) if r > current_price][:4]
    support_levels = [s for s in cluster_levels(lows, False) if s < current_price][:4]

    nearest_resistance = min(resistance_levels, key=lambda x: x - current_price) if resistance_levels else None
    nearest_support = max(support_levels, key=lambda x: x) if support_levels else None

    return {
        "support": support_levels,
        "resistance": resistance_levels,
        "nearest_support": nearest_support,
        "nearest_resistance": nearest_resistance,
    }


# ─── Individual indicator functions ──────────────────────────────────────────

def _to_df(ohlcv: list) -> pd.DataFrame:
    df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


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


def _macd_crossing(series: pd.Series) -> str:
    """Detect fresh MACD crossovers in the last 3 bars."""
    if len(series) < 35:
        return "none"
    ema_fast = series.ewm(span=12, adjust=False).mean()
    ema_slow = series.ewm(span=26, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    if hist.iloc[-1] > 0 and hist.iloc[-2] <= 0:
        return "bullish_cross"
    if hist.iloc[-1] < 0 and hist.iloc[-2] >= 0:
        return "bearish_cross"
    return "none"


def _bollinger_bands(series: pd.Series, period: int = 20, std_dev: float = 2) -> dict:
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
        "squeeze": width_val < avg_width * 0.7,
    }


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> Optional[float]:
    if len(close) < period + 1:
        return None
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.rolling(period).mean().iloc[-1]
    return round(float(atr), 4) if not np.isnan(atr) else None


def _adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> Optional[float]:
    """Average Directional Index — measures trend strength, not direction."""
    if len(close) < period * 2:
        return None
    try:
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)

        prev_close = close.shift(1)
        tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)

        atr = tr.ewm(alpha=1 / period, adjust=False).mean()
        plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr
        minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
        adx = dx.ewm(alpha=1 / period, adjust=False).mean().iloc[-1]
        return round(float(adx), 2) if not np.isnan(adx) else None
    except Exception:
        return None


def _market_regime(adx: Optional[float]) -> str:
    if adx is None:
        return "unknown"
    if adx >= 40:
        return "strong_trend"
    elif adx >= 25:
        return "trending"
    else:
        return "ranging"


def _vwap(df: pd.DataFrame) -> Optional[float]:
    try:
        typical = (df["high"] + df["low"] + df["close"]) / 3
        vwap = (typical * df["volume"]).cumsum() / df["volume"].cumsum()
        return round(float(vwap.iloc[-1]), 2)
    except Exception:
        return None


def _golden_cross(series: pd.Series) -> Optional[str]:
    if len(series) < 200:
        return None
    ema50 = series.ewm(span=50, adjust=False).mean()
    ema200 = series.ewm(span=200, adjust=False).mean()
    if ema50.iloc[-1] > ema200.iloc[-1] and ema50.iloc[-5] <= ema200.iloc[-5]:
        return "golden"     # fresh golden cross
    if ema50.iloc[-1] < ema200.iloc[-1] and ema50.iloc[-5] >= ema200.iloc[-5]:
        return "death"      # fresh death cross
    if ema50.iloc[-1] > ema200.iloc[-1]:
        return "above"      # bullish long-term
    return "below"          # bearish long-term


def format_indicators_summary(ind: dict) -> str:
    if not ind:
        return "Insufficient data."
    lines = [
        f"RSI(14): {ind.get('rsi_14', 'N/A')} | RSI(7): {ind.get('rsi_7', 'N/A')}",
        f"MACD: {ind.get('macd_trend')} (histogram: {ind.get('macd_histogram')}, crossing: {ind.get('macd_crossing')})",
        f"BB %B: {ind.get('bb_pct')} | Squeeze: {ind.get('bb_squeeze')}",
        f"EMA Trend: {ind.get('ema_trend')} | Golden Cross: {ind.get('golden_cross')}",
        f"ADX(14): {ind.get('adx_14')} → Regime: {ind.get('regime')}",
        f"VWAP: {ind.get('vwap')} | Price vs VWAP: {'above' if (ind.get('current_price') or 0) > (ind.get('vwap') or 0) else 'below'}",
        f"Volume Ratio: {ind.get('volume_ratio')}x",
        f"Momentum 5-bar: {ind.get('momentum_5')}%",
        f"Support: {ind.get('support_levels')} | Resistance: {ind.get('resistance_levels')}",
    ]
    return "\n".join(lines)
