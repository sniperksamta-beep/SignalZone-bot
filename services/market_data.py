"""
services/market_data.py
جلب بيانات السوق الحقيقية وحساب المؤشرات التقنية الكاملة.
"""

import pandas as pd
import numpy as np
import yfinance as yf
from config import PAIRS, TIMEFRAMES


def fetch_candles(pair: str, timeframe: str) -> pd.DataFrame:
    """جلب الشمعات من Yahoo Finance."""
    info = PAIRS[pair]
    tf   = TIMEFRAMES[timeframe]
    ticker = yf.Ticker(info["yahoo"])
    df = ticker.history(interval=tf["yf_interval"], period=tf["yf_period"])
    if df.empty:
        raise ValueError(f"No data for {pair}")
    df = df.rename(columns={"Open":"open","High":"high","Low":"low","Close":"close","Volume":"volume"})
    df = df[["open","high","low","close","volume"]].dropna()
    # للفريم 4h نعيد التجميع يدوياً من 1h
    if timeframe == "4h":
        df = df.resample("4h").agg({
            "open":  "first",
            "high":  "max",
            "low":   "min",
            "close": "last",
            "volume":"sum"
        }).dropna()
    return df


def compute_indicators(df: pd.DataFrame) -> dict:
    """يحسب جميع المؤشرات التقنية ويعيدها كـ dict جاهز للـ AI."""
    close = df["close"]
    high  = df["high"]
    low   = df["low"]
    n     = len(df)

    # ── EMA ──────────────────────────────────────────────────────
    ema8   = close.ewm(span=8,   adjust=False).mean()
    ema21  = close.ewm(span=21,  adjust=False).mean()
    ema50  = close.ewm(span=50,  adjust=False).mean()
    ema200 = close.ewm(span=200, adjust=False).mean()

    # ── RSI ──────────────────────────────────────────────────────
    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rs    = gain / loss.replace(0, np.nan)
    rsi   = 100 - (100 / (1 + rs))

    # ── MACD ─────────────────────────────────────────────────────
    ema12      = close.ewm(span=12, adjust=False).mean()
    ema26      = close.ewm(span=26, adjust=False).mean()
    macd_line  = ema12 - ema26
    signal_line= macd_line.ewm(span=9, adjust=False).mean()
    histogram  = macd_line - signal_line

    # ── Bollinger Bands ───────────────────────────────────────────
    bb_mid   = close.rolling(20).mean()
    bb_std   = close.rolling(20).std()
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std

    # ── ATR ───────────────────────────────────────────────────────
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()

    # ── Stochastic ────────────────────────────────────────────────
    low14  = low.rolling(14).min()
    high14 = high.rolling(14).max()
    stoch_k = 100 * (close - low14) / (high14 - low14 + 1e-10)
    stoch_d = stoch_k.rolling(3).mean()

    # ── Support & Resistance ──────────────────────────────────────
    recent = df.tail(100)
    pivots_high = []
    pivots_low  = []
    for i in range(2, len(recent)-2):
        h = recent["high"].iloc
        l = recent["low"].iloc
        if h[i] > h[i-1] and h[i] > h[i-2] and h[i] > h[i+1] and h[i] > h[i+2]:
            pivots_high.append(h[i])
        if l[i] < l[i-1] and l[i] < l[i-2] and l[i] < l[i+1] and l[i] < l[i+2]:
            pivots_low.append(l[i])

    current = close.iloc[-1]

    # أقرب مستويات دعم ومقاومة
    resistances = sorted([p for p in pivots_high if p > current])[:3]
    supports    = sorted([p for p in pivots_low  if p < current], reverse=True)[:3]

    # ── Fibonacci ─────────────────────────────────────────────────
    swing_high = high.rolling(50).max().iloc[-1]
    swing_low  = low.rolling(50).min().iloc[-1]
    fib_range  = swing_high - swing_low
    fib_levels = {
        "0.0":   round(swing_low, 5),
        "0.236": round(swing_low + 0.236 * fib_range, 5),
        "0.382": round(swing_low + 0.382 * fib_range, 5),
        "0.5":   round(swing_low + 0.5   * fib_range, 5),
        "0.618": round(swing_low + 0.618 * fib_range, 5),
        "0.786": round(swing_low + 0.786 * fib_range, 5),
        "1.0":   round(swing_high, 5),
    }

    # ── آخر قيمة لكل مؤشر ────────────────────────────────────────
    def last(s):
        v = s.iloc[-1]
        return round(float(v), 5) if not np.isnan(v) else None

    return {
        "current_price": round(float(current), 5),
        "candles_count": n,
        "price_change_pct": round(float((close.iloc[-1] - close.iloc[-20]) / close.iloc[-20] * 100), 2),

        # EMA
        "ema8":   last(ema8),
        "ema21":  last(ema21),
        "ema50":  last(ema50),
        "ema200": last(ema200),
        "ema_trend": "bullish" if last(ema8) > last(ema21) > last(ema50) else
                     "bearish" if last(ema8) < last(ema21) < last(ema50) else "mixed",

        # RSI
        "rsi": last(rsi),
        "rsi_prev": round(float(rsi.iloc[-2]), 2) if len(rsi) > 1 else None,

        # MACD
        "macd":      last(macd_line),
        "macd_signal": last(signal_line),
        "macd_hist": last(histogram),
        "macd_cross": "bullish" if last(macd_line) > last(signal_line) else "bearish",

        # Bollinger
        "bb_upper": last(bb_upper),
        "bb_mid":   last(bb_mid),
        "bb_lower": last(bb_lower),
        "bb_width": round(float((bb_upper.iloc[-1] - bb_lower.iloc[-1]) / bb_mid.iloc[-1] * 100), 2),

        # ATR
        "atr": last(atr),
        "atr_pct": round(float(atr.iloc[-1] / current * 100), 3) if current else None,

        # Stochastic
        "stoch_k": last(stoch_k),
        "stoch_d": last(stoch_d),

        # S&R
        "resistances": [round(r, 5) for r in resistances],
        "supports":    [round(s, 5) for s in supports],

        # Fibonacci
        "fibonacci": fib_levels,
        "swing_high": round(float(swing_high), 5),
        "swing_low":  round(float(swing_low), 5),

        # آخر 5 شمعات للسياق
        "last_5_candles": [
            {
                "open":  round(float(df["open"].iloc[i]), 5),
                "high":  round(float(df["high"].iloc[i]), 5),
                "low":   round(float(df["low"].iloc[i]), 5),
                "close": round(float(df["close"].iloc[i]), 5),
            }
            for i in range(-5, 0)
        ],
    }
