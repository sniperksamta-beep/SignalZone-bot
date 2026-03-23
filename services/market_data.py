import os
import pandas as pd
import numpy as np
import aiohttp
from datetime import datetime, timezone
from config import PAIRS, TIMEFRAMES

TWELVE_KEY = os.getenv("TWELVE_DATA_KEY", "")
TWELVE_URL = "https://api.twelvedata.com/time_series"

TWELVE_SYMBOLS = {
    "XAUUSD": "XAU/USD",
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


def candle_dna(df: pd.DataFrame) -> dict:
    o = df["open"].values
    h = df["high"].values
    l = df["low"].values
    c = df["close"].values

    body        = np.abs(c - o)
    total_range = h - l + 1e-10
    upper_wick  = h - np.maximum(c, o)
    lower_wick  = np.minimum(c, o) - l
    direction   = np.where(c > o, 1, -1)

    efficiency    = body / total_range
    buy_pressure  = lower_wick / total_range
    sell_pressure = upper_wick / total_range
    delta_est     = (buy_pressure - sell_pressure) * direction

    ranges_5  = total_range[-5:]
    ranges_10 = total_range[-10:-5]
    exhaustion = "expanding" if np.mean(ranges_5) > np.mean(ranges_10) * 1.2 else \
                 "exhausting" if np.mean(ranges_5) < np.mean(ranges_10) * 0.7 else "normal"

    avg_range_20  = np.mean(total_range[-20:])
    avg_range_5   = np.mean(total_range[-5:])
    squeeze_ratio = avg_range_5 / avg_range_20
    is_squeeze    = squeeze_ratio < 0.6

    consecutive = 0
    last_dir    = direction[-1]
    for i in range(len(direction)-1, max(len(direction)-10, 0), -1):
        if direction[i] == last_dir:
            consecutive += 1
        else:
            break

    last_efficiency    = round(float(efficiency[-1]),    3)
    last_buy_pressure  = round(float(buy_pressure[-1]),  3)
    last_sell_pressure = round(float(sell_pressure[-1]), 3)
    last_delta         = round(float(delta_est[-1]),     3)
    avg_delta_5        = round(float(np.mean(delta_est[-5:])), 3)

    strong_rejection = None
    if last_sell_pressure > 0.6:
        strong_rejection = "bearish_rejection"
    elif last_buy_pressure > 0.6:
        strong_rejection = "bullish_rejection"

    bull_count = int(np.sum(direction[-10:] == 1))
    bear_count = int(np.sum(direction[-10:] == -1))
    trend_consistency = f"{bull_count} صاعدة vs {bear_count} هابطة من آخر 10"

    last_5 = []
    for i in range(-5, 0):
        last_5.append({
            "direction":     "🟢" if direction[i] == 1 else "🔴",
            "open":          round(float(o[i]), 5),
            "high":          round(float(h[i]), 5),
            "low":           round(float(l[i]), 5),
            "close":         round(float(c[i]), 5),
            "efficiency":    round(float(efficiency[i]),    2),
            "buy_pressure":  round(float(buy_pressure[i]),  2),
            "sell_pressure": round(float(sell_pressure[i]), 2),
        })

    return {
        "last_efficiency":     last_efficiency,
        "last_buy_pressure":   last_buy_pressure,
        "last_sell_pressure":  last_sell_pressure,
        "last_delta":          last_delta,
        "avg_delta_5":         avg_delta_5,
        "exhaustion":          exhaustion,
        "is_squeeze":          is_squeeze,
        "squeeze_ratio":       round(float(squeeze_ratio), 2),
        "consecutive_candles": consecutive,
        "strong_rejection":    strong_rejection,
        "trend_consistency":   trend_consistency,
        "last_5_candles":      last_5,
    }


def detect_key_levels(df: pd.DataFrame) -> dict:
    current   = float(df["close"].iloc[-1])
    h         = df["high"].values
    l         = df["low"].values
    tolerance = current * 0.001

    resistance_zones = []
    support_zones    = []

    for i in range(2, len(h) - 2):
        if h[i] > h[i-1] and h[i] > h[i+1]:
            for j in range(i+2, min(i+30, len(h))):
                if abs(h[j] - h[i]) < tolerance and h[j] > current:
                    resistance_zones.append(round(float((h[i] + h[j]) / 2), 5))
                    break
        if l[i] < l[i-1] and l[i] < l[i+1]:
            for j in range(i+2, min(i+30, len(l))):
                if abs(l[j] - l[i]) < tolerance and l[j] < current:
                    support_zones.append(round(float((l[i] + l[j]) / 2), 5))
                    break

    resistance_zones = sorted(list(set([round(r, 3) for r in resistance_zones if r > current])))[:3]
    support_zones    = sorted(list(set([round(s, 3) for s in support_zones    if s < current])), reverse=True)[:3]

    return {"resistance": resistance_zones, "support": support_zones}


def detect_session(timeframe: str) -> dict:
    now  = datetime.now(timezone.utc)
    hour = now.hour

    if 8 <= hour < 13:
        session   = "لندن 🇬🇧"
        liquidity = "عالية"
    elif 13 <= hour < 17:
        session   = "تداخل لندن-نيويورك 🔥"
        liquidity = "أعلى سيولة في اليوم"
    elif 17 <= hour < 22:
        session   = "نيويورك 🇺🇸"
        liquidity = "عالية"
    elif 0 <= hour < 8:
        session   = "آسيا 🌏"
        liquidity = "منخفضة"
    else:
        session   = "بين الجلسات"
        liquidity = "منخفضة جداً"

    warning = None
    if timeframe in ("5m", "15m") and liquidity in ("منخفضة", "منخفضة جداً"):
        warning = "⚠️ سيولة منخفضة — إشارات الفريمات الصغيرة أقل موثوقية الآن"

    return {"session": session, "liquidity": liquidity, "hour_utc": hour, "warning": warning}


def compute_indicators(df: pd.DataFrame) -> dict:
    current = round(float(df["close"].iloc[-1]), 5)
    close   = df["close"]
    high    = df["high"]
    low     = df["low"]

    tr  = pd.concat([(high-low), (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
    atr = round(float(tr.rolling(14).mean().iloc[-1]), 5)

    ema50  = close.ewm(span=50,  adjust=False).mean()
    ema200 = close.ewm(span=200, adjust=False).mean()
    trend  = "صاعد" if float(ema50.iloc[-1]) > float(ema200.iloc[-1]) else "هابط"

    return {
        "current_price": current,
        "atr":           atr,
        "trend":         trend,
        "dna":           candle_dna(df),
        "levels":        detect_key_levels(df),
        "session":       detect_session("1h"),
    }
