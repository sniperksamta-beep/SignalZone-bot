import os
import pandas as pd
import numpy as np
import aiohttp
from config import PAIRS, TIMEFRAMES

TWELVE_KEY = os.getenv("TWELVE_DATA_KEY", "")
TWELVE_URL = "https://api.twelvedata.com/time_series"

TWELVE_SYMBOLS = {
    "XAUUSD": "XAU/USD",
    "XAGUSD": "XAG/USD",
    "BTCUSD": "BTC/USD",
    "ETHUSD": "ETH/USD",
    "EURUSD": "EUR/USD",
    "USDJPY": "USD/JPY",
}

TWELVE_INTERVALS = {
    "5m":  "5min",
    "15m": "15min",
    "1h":  "1h",
    "4h":  "4h",
    "1d":  "1day",
}


async def fetch_candles(pair: str, timeframe: str) -> pd.DataFrame:
    symbol   = TWELVE_SYMBOLS.get(pair, pair)
    interval = TWELVE_INTERVALS.get(timeframe, "1h")
    params = {
        "symbol":     symbol,
        "interval":   interval,
        "outputsize": 200,
        "apikey":     TWELVE_KEY,
        "format":     "JSON",
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(TWELVE_URL, params=params,
                               timeout=aiohttp.ClientTimeout(total=20)) as resp:
            data = await resp.json()

    if data.get("status") == "error":
        raise ValueError(f"Twelve Data error: {data.get('message', 'unknown')}")

    values = data.get("values", [])
    if not values:
        raise ValueError(f"No data returned for {pair}")

    df = pd.DataFrame(values)
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0) if "volume" in df.columns else 0
    df = df[["open", "high", "low", "close", "volume"]].dropna()
    df = df.iloc[::-1].reset_index(drop=True)
    return df


def compute_indicators(df: pd.DataFrame) -> dict:
    close = df["close"]
    high  = df["high"]
    low   = df["low"]

    ema8   = close.ewm(span=8,   adjust=False).mean()
    ema21  = close.ewm(span=21,  adjust=False).mean()
    ema50  = close.ewm(span=50,  adjust=False).mean()
    ema200 = close.ewm(span=200, adjust=False).mean()

    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rsi   = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))

    ema12       = close.ewm(span=12, adjust=False).mean()
    ema26       = close.ewm(span=26, adjust=False).mean()
    macd_line   = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    histogram   = macd_line - signal_line

    bb_mid   = close.rolling(20).mean()
    bb_std   = close.rolling(20).std()
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std

    tr  = pd.concat([(high-low), (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()

    low14   = low.rolling(14).min()
    high14  = high.rolling(14).max()
    stoch_k = 100 * (close - low14) / (high14 - low14 + 1e-10)
    stoch_d = stoch_k.rolling(3).mean()

    recent      = df.tail(100)
    pivots_high = []
    pivots_low  = []
    for i in range(2, len(recent) - 2):
        h = recent["high"].iloc
        l = recent["low"].iloc
        if h[i] > h[i-1] and h[i] > h[i-2] and h[i] > h[i+1] and h[i] > h[i+2]:
            pivots_high.append(float(h[i]))
        if l[i] < l[i-1] and l[i] < l[i-2] and l[i] < l[i+1] and l[i] < l[i+2]:
            pivots_low.append(float(l[i]))

    current     = float(close.iloc[-1])
    resistances = sorted([p for p in pivots_high if p > current])[:3]
    supports    = sorted([p for p in pivots_low  if p < current], reverse=True)[:3]

    swing_high = float(high.rolling(50).max().iloc[-1])
    swing_low  = float(low.rolling(50).min().iloc[-1])
    fib_range  = swing_high - swing_low

    def last(s):
        v = s.iloc[-1]
        return round(float(v), 5) if not np.isnan(v) else None

    return {
        "current_price":    round(current, 5),
        "candles_count":    len(df),
        "price_change_pct": round((close.iloc[-1] - close.iloc[-20]) / close.iloc[-20] * 100, 2),
        "ema8": last(ema8), "ema21": last(ema21), "ema50": last(ema50), "ema200": last(ema200),
        "ema_trend": "bullish" if last(ema8) > last(ema21) > last(ema50) else "bearish" if last(ema8) < last(ema21) < last(ema50) else "mixed",
        "rsi": last(rsi), "rsi_prev": round(float(rsi.iloc[-2]), 2),
        "macd": last(macd_line), "macd_signal": last(signal_line), "macd_hist": last(histogram),
        "macd_cross": "bullish" if last(macd_line) > last(signal_line) else "bearish",
        "bb_upper": last(bb_upper), "bb_mid": last(bb_mid), "bb_lower": last(bb_lower),
        "bb_width": round((bb_upper.iloc[-1] - bb_lower.iloc[-1]) / bb_mid.iloc[-1] * 100, 2),
        "atr": last(atr), "atr_pct": round(float(atr.iloc[-1]) / current * 100, 3),
        "stoch_k": last(stoch_k), "stoch_d": last(stoch_d),
        "resistances": [round(r, 5) for r in resistances],
        "supports":    [round(s, 5) for s in supports],
        "fibonacci": {
            "0.0":   round(swing_low, 5),
            "0.236": round(swing_low + 0.236 * fib_range, 5),
            "0.382": round(swing_low + 0.382 * fib_range, 5),
            "0.5":   round(swing_low + 0.5   * fib_range, 5),
            "0.618": round(swing_low + 0.618 * fib_range, 5),
            "1.0":   round(swing_high, 5),
        },
        "swing_high": round(swing_high, 5),
        "swing_low":  round(swing_low,  5),
        "last_5_candles": [
            {"open": round(float(df["open"].iloc[i]), 5), "high": round(float(df["high"].iloc[i]), 5),
             "low":  round(float(df["low"].iloc[i]),  5), "close": round(float(df["close"].iloc[i]), 5)}
            for i in range(-5, 0)
        ],
    }
