import os
import pandas as pd
import numpy as np
import aiohttp
from datetime import datetime, timezone
from config import PAIRS

TWELVE_KEY = os.getenv("TWELVE_DATA_KEY", "")
TWELVE_URL = "https://api.twelvedata.com/time_series"

TWELVE_SYMBOLS = {
    "XAUUSD": "XAU/USD",
    "BTCUSD": "BTC/USD",
    "ETHUSD": "ETH/USD",
    "EURUSD": "EUR/USD",
    "USDJPY": "USD/JPY",
}

MTF_MAP = {
    "5m":  {"trend": "1h",  "structure": "15m", "entry": "5m"},
    "15m": {"trend": "4h",  "structure": "1h",  "entry": "15m"},
    "1h":  {"trend": "1d",  "structure": "4h",  "entry": "1h"},
    "4h":  {"trend": "1d",  "structure": "4h",  "entry": "4h"},
    "1d":  {"trend": "1d",  "structure": "1d",  "entry": "1d"},
}

TWELVE_INTERVALS = {
    "5m":  "5min",
    "15m": "15min",
    "1h":  "1h",
    "4h":  "4h",
    "1d":  "1day",
}


async def _fetch(symbol: str, interval: str, size: int = 150) -> pd.DataFrame:
    params = {
        "symbol":     symbol,
        "interval":   interval,
        "outputsize": size,
        "apikey":     TWELVE_KEY,
        "format":     "JSON",
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(TWELVE_URL, params=params,
                               timeout=aiohttp.ClientTimeout(total=20)) as resp:
            data = await resp.json()

    if data.get("status") == "error":
        raise ValueError(f"Twelve Data: {data.get('message','unknown')}")

    values = data.get("values", [])
    if not values:
        raise ValueError("No data returned")

    df = pd.DataFrame(values)
    for col in ["open","high","low","close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0) if "volume" in df.columns else 0
    df = df[["open","high","low","close","volume"]].dropna()
    df = df.iloc[::-1].reset_index(drop=True)
    return df


async def fetch_candles(pair: str, timeframe: str) -> dict:
    sym = TWELVE_SYMBOLS.get(pair, pair)
    mtf = MTF_MAP.get(timeframe, MTF_MAP["1h"])
    frames = {}
    for role, tf in mtf.items():
        interval = TWELVE_INTERVALS.get(tf, "1h")
        frames[role] = await _fetch(sym, interval)
    return frames


def _ema(series, span):
    return series.ewm(span=span, adjust=False).mean()

def _rsi(series, period=14):
    delta = series.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    return 100 - (100 / (1 + gain / loss.replace(0, np.nan)))

def _atr(df, period=14):
    h, l, c = df["high"], df["low"], df["close"]
    tr = pd.concat([(h-l),(h-c.shift()).abs(),(l-c.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def _trend_direction(df) -> str:
    close = df["close"]
    e50   = float(_ema(close, 50).iloc[-1])
    e200  = float(_ema(close, 200).iloc[-1])
    if e50 > e200 * 1.001:
        return "bullish"
    elif e50 < e200 * 0.999:
        return "bearish"
    return "neutral"

def _key_levels(df) -> dict:
    current   = float(df["close"].iloc[-1])
    h         = df["high"].values
    l         = df["low"].values
    tolerance = current * 0.0015
    res, sup  = [], []

    for i in range(2, len(h)-2):
        if h[i] > h[i-1] and h[i] > h[i+1]:
            for j in range(i+2, min(i+40, len(h))):
                if abs(h[j]-h[i]) < tolerance:
                    level = round((h[i]+h[j])/2, 5)
                    if level > current:
                        res.append(level)
                    break
        if l[i] < l[i-1] and l[i] < l[i+1]:
            for j in range(i+2, min(i+40, len(l))):
                if abs(l[j]-l[i]) < tolerance:
                    level = round((l[i]+l[j])/2, 5)
                    if level < current:
                        sup.append(level)
                    break

    return {
        "resistance": sorted(list(set([round(r,3) for r in res if r > current])))[:3],
        "support":    sorted(list(set([round(s,3) for s in sup if s < current])), reverse=True)[:3],
    }

def _structure(df) -> str:
    recent = df.tail(30)
    highs, lows = [], []
    for i in range(2, len(recent)-2):
        h = recent["high"].iloc
        l = recent["low"].iloc
        if h[i] > h[i-1] and h[i] > h[i-2] and h[i] > h[i+1] and h[i] > h[i+2]:
            highs.append(float(h[i]))
        if l[i] < l[i-1] and l[i] < l[i-2] and l[i] < l[i+1] and l[i] < l[i+2]:
            lows.append(float(l[i]))

    if len(highs) >= 2 and len(lows) >= 2:
        if highs[-1] > highs[-2] and lows[-1] > lows[-2]:
            return "bullish"
        if highs[-1] < highs[-2] and lows[-1] < lows[-2]:
            return "bearish"
        if highs[-1] > highs[-2] and lows[-1] < lows[-2]:
            return "choch_bearish"
        if highs[-1] < highs[-2] and lows[-1] > lows[-2]:
            return "choch_bullish"
    return "neutral"

def _momentum(df) -> dict:
    close     = df["close"]
    rsi_val   = round(float(_rsi(close).iloc[-1]), 1)
    macd_line = _ema(close, 12) - _ema(close, 26)
    signal    = _ema(macd_line, 9)
    macd_cross= "bullish" if float(macd_line.iloc[-1]) > float(signal.iloc[-1]) else "bearish"
    return {"rsi": rsi_val, "macd": macd_cross}

def _entry_quality(df) -> dict:
    o = df["open"].values
    h = df["high"].values
    l = df["low"].values
    c = df["close"].values

    total_range = h - l + 1e-10
    body        = np.abs(c - o)
    upper_wick  = h - np.maximum(c, o)
    lower_wick  = np.minimum(c, o) - l

    avg20      = np.mean(total_range[-20:])
    avg5       = np.mean(total_range[-5:])
    is_squeeze = (avg5 / avg20) < 0.6

    last_upper = upper_wick[-1] / total_range[-1]
    last_lower = lower_wick[-1] / total_range[-1]
    rejection  = None
    if last_upper > 0.6:
        rejection = "bearish"
    elif last_lower > 0.6:
        rejection = "bullish"

    immediate = "bullish" if c[-1] > c[-3] else "bearish"

    return {
        "is_squeeze": is_squeeze,
        "rejection":  rejection,
        "immediate":  immediate,
        "efficiency": round(float(body[-1] / total_range[-1]), 2),
    }


def compute_indicators(frames: dict) -> dict:
    df_trend     = frames["trend"]
    df_structure = frames["structure"]
    df_entry     = frames["entry"]

    current = round(float(df_entry["close"].iloc[-1]), 5)
    atr_val = round(float(_atr(df_entry).iloc[-1]), 5)

    trend_dir     = _trend_direction(df_trend)
    struct_dir    = _structure(df_structure)
    struct_levels = _key_levels(df_structure)
    entry_mom     = _momentum(df_entry)
    entry_q       = _entry_quality(df_entry)
    entry_levels  = _key_levels(df_entry)

    signals = []
    if trend_dir == "bullish":       signals.append("bullish")
    elif trend_dir == "bearish":     signals.append("bearish")
    if struct_dir in ("bullish","choch_bullish"):   signals.append("bullish")
    elif struct_dir in ("bearish","choch_bearish"): signals.append("bearish")
    if entry_mom["rsi"] < 40:        signals.append("bullish")
    elif entry_mom["rsi"] > 60:      signals.append("bearish")
    if entry_mom["macd"] == "bullish": signals.append("bullish")
    else:                              signals.append("bearish")
    if entry_q["immediate"] == "bullish": signals.append("bullish")
    else:                                 signals.append("bearish")

    bull_count = signals.count("bullish")
    bear_count = signals.count("bearish")

    if bull_count >= 4:   confluence = "strong_bullish"
    elif bull_count == 3: confluence = "bullish"
    elif bear_count >= 4: confluence = "strong_bearish"
    elif bear_count == 3: confluence = "bearish"
    else:                 confluence = "neutral"

    all_res = sorted(list(set(struct_levels["resistance"] + entry_levels["resistance"])))[:3]
    all_sup = sorted(list(set(struct_levels["support"]    + entry_levels["support"])),   reverse=True)[:3]

    hour = datetime.now(timezone.utc).hour
    if 8 <= hour < 13:
        session, liquidity = "لندن 🇬🇧", "عالية"
    elif 13 <= hour < 17:
        session, liquidity = "تداخل لندن-نيويورك 🔥", "أعلى سيولة"
    elif 17 <= hour < 22:
        session, liquidity = "نيويورك 🇺🇸", "عالية"
    else:
        session, liquidity = "آسيا 🌏", "منخفضة"

    return {
        "current_price": current,
        "atr":           atr_val,
        "session":       session,
        "liquidity":     liquidity,
        "confluence":    confluence,
        "bull_count":    bull_count,
        "bear_count":    bear_count,
        "trend":         trend_dir,
        "structure":     struct_dir,
        "momentum":      entry_mom,
        "entry_quality": entry_q,
        "resistance":    all_res,
        "support":       all_sup,
    }
