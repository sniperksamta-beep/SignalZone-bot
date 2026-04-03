"""
market_data.py  —  Institutional-Grade Multi-Timeframe Confluence Engine
=========================================================================

Architecture:
  1.  Fetch 3 aligned timeframes per request (trend / structure / entry)
  2.  Compute 15+ weighted indicators across all frames
  3.  Run a deterministic scoring engine (0-100) — NO AI guessing
  4.  Apply multi-layer filters to eliminate false signals
  5.  Calculate precise entry / SL / TP mathematically

The AI receives the DECISION already made — it only formats output.
"""

import os, json
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
    "5m": "5min", "15m": "15min",
    "1h": "1h",   "4h":  "4h",   "1d": "1day",
}

TF_MINUTES = {"5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  DATA FETCHING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _fetch(symbol: str, interval: str, size: int = 200) -> pd.DataFrame:
    params = {
        "symbol": symbol, "interval": interval,
        "outputsize": size, "apikey": TWELVE_KEY, "format": "JSON",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                TWELVE_URL, params=params,
                timeout=aiohttp.ClientTimeout(total=25),
                headers={"Accept": "application/json"}
            ) as resp:
                ct = resp.headers.get("Content-Type", "")
                if "html" in ct.lower():
                    raise ValueError("Twelve Data rate limit — try again later")
                if resp.status != 200:
                    raise ValueError(f"Twelve Data HTTP {resp.status}")
                text = await resp.text()
                if not text.strip().startswith("{"):
                    raise ValueError("Invalid response from Twelve Data")
                data = json.loads(text)
    except aiohttp.ClientError as e:
        raise ValueError(f"Connection error: {str(e)[:100]}")

    if data.get("status") == "error":
        raise ValueError(f"Twelve Data: {data.get('message', 'unknown')[:150]}")
    values = data.get("values", [])
    if not values:
        raise ValueError("No data — try a different timeframe")

    df = pd.DataFrame(values)
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
    else:
        df["volume"] = 0

    df = df[["open", "high", "low", "close", "volume"]].dropna()
    df = df.iloc[::-1].reset_index(drop=True)
    return df



async def fetch_candles(pair: str, timeframe: str) -> dict:
    sym = TWELVE_SYMBOLS.get(pair, pair)
    mtf = MTF_MAP.get(timeframe, MTF_MAP["1h"])
    frames = {}
    for role, tf in mtf.items():
        frames[role] = await _fetch(sym, TWELVE_INTERVALS.get(tf, "1h"))
    return frames


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CORE INDICATORS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _ema(s, span):
    return s.ewm(span=span, adjust=False).mean()

def _sma(s, period):
    return s.rolling(period).mean()

def _rsi(s, period=14):
    d = s.diff()
    g = d.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
    l = (-d.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
    return 100 - (100 / (1 + g / l.replace(0, np.nan)))

def _atr(df, period=14):
    h, l, c = df["high"], df["low"], df["close"]
    tr = pd.concat([(h-l), (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def _stochastic_rsi(s, rsi_period=14, stoch_period=14, k_smooth=3, d_smooth=3):
    rsi = _rsi(s, rsi_period)
    rsi_min = rsi.rolling(stoch_period).min()
    rsi_max = rsi.rolling(stoch_period).max()
    stoch_rsi = (rsi - rsi_min) / (rsi_max - rsi_min + 1e-10) * 100
    k = stoch_rsi.rolling(k_smooth).mean()
    d = k.rolling(d_smooth).mean()
    return k, d

def _adx(df, period=14):
    h, l, c = df["high"], df["low"], df["close"]
    plus_dm  = (h - h.shift(1)).clip(lower=0)
    minus_dm = (l.shift(1) - l).clip(lower=0)
    mask = plus_dm > minus_dm
    plus_dm  = plus_dm.where(mask, 0)
    minus_dm = minus_dm.where(~mask, 0)
    tr = pd.concat([(h-l), (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    atr_s = tr.ewm(alpha=1/period, adjust=False).mean()
    plus_di  = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean()  / (atr_s + 1e-10))
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / (atr_s + 1e-10))
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10)
    adx_val = dx.ewm(alpha=1/period, adjust=False).mean()
    return adx_val, plus_di, minus_di

def _bollinger_bands(s, period=20, std_mult=2.0):
    mid = _sma(s, period)
    std = s.rolling(period).std()
    return mid + std_mult * std, mid, mid - std_mult * std

def _vwap(df):
    typical = (df["high"] + df["low"] + df["close"]) / 3
    cum_tp_vol = (typical * df["volume"]).cumsum()
    cum_vol    = df["volume"].cumsum().replace(0, np.nan)
    return cum_tp_vol / cum_vol

def _choppiness_index(df, period=14):
    atr_sum = _atr(df, 1).rolling(period).sum()
    high_n  = df["high"].rolling(period).max()
    low_n   = df["low"].rolling(period).min()
    return 100 * np.log10(atr_sum / (high_n - low_n + 1e-10)) / np.log10(period)

def _macd_histogram(s, fast=12, slow=26, signal=9):
    macd_line = _ema(s, fast) - _ema(s, slow)
    signal_line = _ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ADVANCED STRUCTURE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _find_swing_points(df, lookback=3):
    highs, lows = [], []
    h = df["high"].values
    l = df["low"].values
    n = len(h)
    for i in range(lookback, n - lookback):
        is_high = all(h[i] > h[i-j] for j in range(1, lookback+1)) and \
                  all(h[i] > h[i+j] for j in range(1, lookback+1))
        is_low  = all(l[i] < l[i-j] for j in range(1, lookback+1)) and \
                  all(l[i] < l[i+j] for j in range(1, lookback+1))
        if is_high:
            highs.append({"index": i, "price": float(h[i])})
        if is_low:
            lows.append({"index": i, "price": float(l[i])})
    return highs, lows

def _market_structure(df):
    highs, lows = _find_swing_points(df.tail(60), lookback=2)
    if len(highs) < 2 or len(lows) < 2:
        return "neutral", 0.3

    hh_count, lh_count, hl_count, ll_count = 0, 0, 0, 0
    for i in range(1, min(len(highs), 4)):
        if highs[-i]["price"] > highs[-(i+1)]["price"]:
            hh_count += 1
        else:
            lh_count += 1
    for i in range(1, min(len(lows), 4)):
        if lows[-i]["price"] > lows[-(i+1)]["price"]:
            hl_count += 1
        else:
            ll_count += 1

    bull_s = hh_count + hl_count
    bear_s = lh_count + ll_count

    last_2h = highs[-2:]
    last_2l = lows[-2:]
    if len(last_2h) == 2 and len(last_2l) == 2:
        if last_2h[-1]["price"] < last_2h[-2]["price"] and last_2l[-1]["price"] > last_2l[-2]["price"]:
            return "choch_bullish", 0.7
        if last_2h[-1]["price"] > last_2h[-2]["price"] and last_2l[-1]["price"] < last_2l[-2]["price"]:
            return "choch_bearish", 0.7

    if bull_s >= 3:   return "bullish", min(0.95, 0.5 + bull_s * 0.15)
    elif bull_s >= 2: return "bullish", 0.65
    elif bear_s >= 3: return "bearish", min(0.95, 0.5 + bear_s * 0.15)
    elif bear_s >= 2: return "bearish", 0.65
    return "neutral", 0.3

def _trend_direction(df):
    c = df["close"]
    e9   = float(_ema(c, 9).iloc[-1])
    e21  = float(_ema(c, 21).iloc[-1])
    e50  = float(_ema(c, 50).iloc[-1])
    ln = min(len(c)-1, 200)
    e200 = float(_ema(c, ln if ln > 50 else 50).iloc[-1])

    if e9 > e21 > e50 > e200:   return "bullish", 1.0
    elif e9 < e21 < e50 < e200: return "bearish", 1.0
    elif e9 > e21 and e50 > e200: return "bullish", 0.7
    elif e9 < e21 and e50 < e200: return "bearish", 0.7
    elif e50 > e200 * 1.001:    return "bullish", 0.4
    elif e50 < e200 * 0.999:    return "bearish", 0.4
    return "neutral", 0.0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SMART MONEY CONCEPTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _detect_order_blocks(df, lookback=30):
    c, o, h, l = df["close"].values, df["open"].values, df["high"].values, df["low"].values
    body = np.abs(c - o)
    avg_body = np.mean(body[-50:]) if len(body) >= 50 else np.mean(body)
    bullish_obs, bearish_obs = [], []
    n = len(c)
    start = max(0, n - lookback)
    for i in range(start + 2, n - 1):
        if c[i-1] < o[i-1] and c[i] > o[i] and body[i] > avg_body * 1.5:
            if c[i] > h[i-1]:
                bullish_obs.append({"top": float(o[i-1]), "bottom": float(l[i-1]),
                                    "index": i-1, "strength": float(body[i] / avg_body)})
        if c[i-1] > o[i-1] and c[i] < o[i] and body[i] > avg_body * 1.5:
            if c[i] < l[i-1]:
                bearish_obs.append({"top": float(h[i-1]), "bottom": float(o[i-1]),
                                    "index": i-1, "strength": float(body[i] / avg_body)})
    return bullish_obs, bearish_obs

def _detect_fvg(df, lookback=20):
    h, l = df["high"].values, df["low"].values
    n = len(h)
    start = max(0, n - lookback)
    bull_fvg, bear_fvg = [], []
    for i in range(start + 2, n):
        if l[i] > h[i-2]:
            bull_fvg.append({"top": float(l[i]), "bottom": float(h[i-2]), "size": float(l[i]-h[i-2])})
        if h[i] < l[i-2]:
            bear_fvg.append({"top": float(l[i-2]), "bottom": float(h[i]), "size": float(l[i-2]-h[i])})
    return bull_fvg, bear_fvg

def _detect_liquidity_sweep(df, lookback=20):
    h, l, c, o = df["high"].values, df["low"].values, df["close"].values, df["open"].values
    n = len(h)
    swing_highs, swing_lows = [], []
    for i in range(2, min(lookback + 2, n - 2)):
        idx = n - 1 - i
        if h[idx] > h[idx-1] and h[idx] > h[idx+1]: swing_highs.append(float(h[idx]))
        if l[idx] < l[idx-1] and l[idx] < l[idx+1]: swing_lows.append(float(l[idx]))

    result = {"bullish_sweep": False, "bearish_sweep": False, "sweep_level": None}
    if swing_lows:
        nearest = min(swing_lows)
        if l[-1] < nearest and c[-1] > o[-1] and c[-1] > nearest:
            result["bullish_sweep"] = True
            result["sweep_level"] = nearest
    if swing_highs:
        nearest = max(swing_highs)
        if h[-1] > nearest and c[-1] < o[-1] and c[-1] < nearest:
            result["bearish_sweep"] = True
            result["sweep_level"] = nearest
    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CANDLESTICK PATTERNS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _candle_patterns(df):
    o, h, l, c = df["open"].values, df["high"].values, df["low"].values, df["close"].values
    body = np.abs(c - o)
    total_range = h - l + 1e-10
    upper_wick  = h - np.maximum(c, o)
    lower_wick  = np.minimum(c, o) - l
    avg_body = np.mean(body[-20:])
    patterns = []

    # Bullish Engulfing
    if (c[-2] < o[-2] and c[-1] > o[-1] and
        o[-1] <= c[-2] and c[-1] >= o[-2] and body[-1] > body[-2]):
        patterns.append(("bullish_engulfing", 0.8))
    # Bearish Engulfing
    if (c[-2] > o[-2] and c[-1] < o[-1] and
        o[-1] >= c[-2] and c[-1] <= o[-2] and body[-1] > body[-2]):
        patterns.append(("bearish_engulfing", 0.8))
    # Bullish Pin Bar
    if (lower_wick[-1] > body[-1] * 2 and upper_wick[-1] < body[-1] * 0.5 and
        lower_wick[-1] / total_range[-1] > 0.6):
        patterns.append(("bullish_pin_bar", 0.75))
    # Bearish Pin Bar
    if (upper_wick[-1] > body[-1] * 2 and lower_wick[-1] < body[-1] * 0.5 and
        upper_wick[-1] / total_range[-1] > 0.6):
        patterns.append(("bearish_pin_bar", 0.75))
    # Morning Star
    if len(c) >= 3:
        if (c[-3] < o[-3] and body[-3] > avg_body and body[-2] < avg_body * 0.4 and
            c[-1] > o[-1] and body[-1] > avg_body and c[-1] > (o[-3] + c[-3]) / 2):
            patterns.append(("morning_star", 0.85))
    # Evening Star
    if len(c) >= 3:
        if (c[-3] > o[-3] and body[-3] > avg_body and body[-2] < avg_body * 0.4 and
            c[-1] < o[-1] and body[-1] > avg_body and c[-1] < (o[-3] + c[-3]) / 2):
            patterns.append(("evening_star", 0.85))
    # Three White Soldiers
    if len(c) >= 3:
        if (c[-3] > o[-3] and c[-2] > o[-2] and c[-1] > o[-1] and
            c[-2] > c[-3] and c[-1] > c[-2] and body[-1] > avg_body * 0.7 and body[-2] > avg_body * 0.7):
            patterns.append(("three_white_soldiers", 0.7))
    # Three Black Crows
    if len(c) >= 3:
        if (c[-3] < o[-3] and c[-2] < o[-2] and c[-1] < o[-1] and
            c[-2] < c[-3] and c[-1] < c[-2] and body[-1] > avg_body * 0.7 and body[-2] > avg_body * 0.7):
            patterns.append(("three_black_crows", 0.7))
    return patterns


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  KEY LEVELS + VOLUME + DIVERGENCE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _key_levels(df):
    current = float(df["close"].iloc[-1])
    tolerance = current * 0.002
    swing_h, swing_l = _find_swing_points(df, lookback=2)

    def cluster(points, is_res):
        if not points:
            return []
        prices = [p["price"] for p in points]
        clusters, used = [], set()
        for i, p in enumerate(prices):
            if i in used: continue
            group = [p]; used.add(i)
            for j, q in enumerate(prices):
                if j not in used and abs(p - q) < tolerance:
                    group.append(q); used.add(j)
            avg = np.mean(group)
            if is_res and avg > current:
                clusters.append({"price": round(float(avg), 5), "touches": len(group)})
            elif not is_res and avg < current:
                clusters.append({"price": round(float(avg), 5), "touches": len(group)})
        clusters.sort(key=lambda x: abs(x["price"] - current))
        return clusters[:4]

    res = cluster(swing_h, True)
    sup = cluster(swing_l, False)
    return {"resistance": [r["price"] for r in res], "support": [s["price"] for s in sup]}

def _volume_analysis(df):
    v, c, o = df["volume"].values, df["close"].values, df["open"].values
    if np.sum(v) == 0:
        return {"vol_confirm": "neutral", "vol_ratio": 1.0, "vol_anomaly": False, "vol_trend": 1.0}
    avg20 = np.mean(v[-20:]) if len(v) >= 20 else np.mean(v)
    avg5  = np.mean(v[-5:])
    ratio = v[-1] / (avg20 + 1e-10)
    trend = avg5 / (avg20 + 1e-10)
    is_bull = c[-1] > o[-1]
    high_vol = ratio > 1.3
    if high_vol and is_bull:     confirm = "bullish"
    elif high_vol and not is_bull: confirm = "bearish"
    elif trend < 0.6:            confirm = "drying_up"
    else:                        confirm = "neutral"
    return {"vol_confirm": confirm, "vol_ratio": round(float(ratio), 2),
            "vol_anomaly": ratio > 2.5, "vol_trend": round(float(trend), 2)}

def _detect_divergence(df, lookback=20):
    c = df["close"]
    rsi = _rsi(c).values
    n = len(c)
    start = max(0, n - lookback)
    plows, phighs = [], []
    for i in range(start + 1, n - 1):
        if c.iloc[i] < c.iloc[i-1] and c.iloc[i] < c.iloc[i+1]: plows.append(i)
        if c.iloc[i] > c.iloc[i-1] and c.iloc[i] > c.iloc[i+1]: phighs.append(i)

    result = {"regular": "none", "hidden": "none"}
    if len(plows) >= 2:
        i1, i2 = plows[-2], plows[-1]
        if not np.isnan(rsi[i2]) and not np.isnan(rsi[i1]):
            if c.iloc[i2] < c.iloc[i1] and rsi[i2] > rsi[i1]: result["regular"] = "bullish"
            if c.iloc[i2] > c.iloc[i1] and rsi[i2] < rsi[i1]: result["hidden"]  = "bullish"
    if len(phighs) >= 2:
        i1, i2 = phighs[-2], phighs[-1]
        if not np.isnan(rsi[i2]) and not np.isnan(rsi[i1]):
            if c.iloc[i2] > c.iloc[i1] and rsi[i2] < rsi[i1]: result["regular"] = "bearish"
            if c.iloc[i2] < c.iloc[i1] and rsi[i2] > rsi[i1]: result["hidden"]  = "bearish"
    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SESSION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _session_info():
    hour = datetime.now(timezone.utc).hour
    if   8  <= hour < 12: return "London", "high", 1.0
    elif 12 <= hour < 17: return "London-NY Overlap", "highest", 1.2
    elif 17 <= hour < 22: return "New York", "high", 1.0
    elif 0  <= hour < 3:  return "Late NY / Early Asia", "low", 0.5
    else:                 return "Asia", "medium-low", 0.6


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TRADE LEVELS (SL / TP)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _compute_levels(df, timeframe, levels, direction):
    current = float(df["close"].iloc[-1])
    atr_val = float(_atr(df).iloc[-1])
    margin  = atr_val * 0.3
    lows    = df["low"].values[-10:]
    highs   = df["high"].values[-10:]
    lo, hi  = float(np.min(lows)), float(np.max(highs))
    min_d, max_d = atr_val * 1.0, atr_val * 3.0

    if direction == "BUY":
        sl = round(lo - margin, 5)
        d = current - sl
        if d < min_d: sl = round(current - min_d, 5)
        elif d > max_d: sl = round(current - max_d, 5)
        d = current - sl
        tp1 = round(current + d * 1.5, 5)
        tp2 = round(current + d * 2.5, 5)
        for r in levels.get("resistance", []):
            if d * 1.2 < (r - current) < d * 3.5:
                tp1 = round(r, 5); break
    else:
        sl = round(hi + margin, 5)
        d = sl - current
        if d < min_d: sl = round(current + min_d, 5)
        elif d > max_d: sl = round(current + max_d, 5)
        d = sl - current
        tp1 = round(current - d * 1.5, 5)
        tp2 = round(current - d * 2.5, 5)
        for s in levels.get("support", []):
            if d * 1.2 < (current - s) < d * 3.5:
                tp1 = round(s, 5); break

    rr = round(d * 1.5 / d, 1) if d > 0 else 0
    avg_move = float(np.mean(np.abs(np.diff(df["close"].values[-20:]))))
    tf_min = TF_MINUTES.get(timeframe, 60)
    ec = max(3, int(atr_val * 1.5 / (avg_move + 1e-10)))
    validity = max(tf_min * 3, min(int(ec * tf_min * 1.5), tf_min * 20))

    return {
        "entry": round(current, 5), "sl": round(sl, 5), "sl_dist": round(d, 5),
        "tp1": tp1, "tp2": tp2, "rr_ratio": f"1:{rr}",
        "atr": round(atr_val, 5), "validity_minutes": validity,
        "local_low": round(lo, 5), "local_high": round(hi, 5),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ███  THE SCORING ENGINE  ███
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _compute_signal_score(a: dict) -> dict:
    """
    Weighted scoring: 0-100. MATH decides, not AI.
      90-100 = VERY STRONG    75-89 = STRONG
      60-74  = MODERATE        <60  = WAIT
    """
    bull, bear, mx = 0.0, 0.0, 0.0
    bd = []

    # 1. TREND (w=20)
    w = 20; mx += w
    td, ts = a["trend_data"]
    if td == "bullish":   bull += w * ts; bd.append(f"Trend: Bullish {ts:.0%} → +{w*ts:.1f}")
    elif td == "bearish": bear += w * ts; bd.append(f"Trend: Bearish {ts:.0%} → +{w*ts:.1f}")
    else: bd.append("Trend: Neutral → 0")

    # 2. STRUCTURE (w=15)
    w = 15; mx += w
    sd, sc = a["structure_data"]
    if sd in ("bullish","choch_bullish"):   bull += w * sc; bd.append(f"Structure: {sd} → +{w*sc:.1f}")
    elif sd in ("bearish","choch_bearish"): bear += w * sc; bd.append(f"Structure: {sd} → +{w*sc:.1f}")
    else: bd.append("Structure: Neutral → 0")

    # 3. RSI (w=8)
    w = 8; mx += w
    rv = a["rsi"]
    if rv < 30:   bull += w; bd.append(f"RSI: {rv:.1f} oversold → +{w}")
    elif rv < 40: bull += w*0.6; bd.append(f"RSI: {rv:.1f} low → +{w*0.6:.1f}")
    elif rv > 70: bear += w; bd.append(f"RSI: {rv:.1f} overbought → +{w}")
    elif rv > 60: bear += w*0.6; bd.append(f"RSI: {rv:.1f} high → +{w*0.6:.1f}")
    else: bd.append(f"RSI: {rv:.1f} neutral → 0")

    # 4. STOCH RSI (w=7)
    w = 7; mx += w
    sk, sd_ = a["stoch_rsi"]
    if sk < 20 and sd_ < 20:       bull += w; bd.append(f"StochRSI oversold → +{w}")
    elif sk < 30 and sk > sd_:     bull += w*0.7; bd.append(f"StochRSI bull cross → +{w*0.7:.1f}")
    elif sk > 80 and sd_ > 80:    bear += w; bd.append(f"StochRSI overbought → +{w}")
    elif sk > 70 and sk < sd_:     bear += w*0.7; bd.append(f"StochRSI bear cross → +{w*0.7:.1f}")
    else: bd.append("StochRSI neutral → 0")

    # 5. MACD (w=8)
    w = 8; mx += w
    ml, ms, mh, mhp = a["macd_line"], a["macd_signal"], a["macd_hist"], a["macd_hist_prev"]
    if ml > ms and mh > mhp:   bull += w*0.9; bd.append(f"MACD bull + rising → +{w*0.9:.1f}")
    elif ml > ms:               bull += w*0.5; bd.append(f"MACD bull → +{w*0.5:.1f}")
    elif ml < ms and mh < mhp: bear += w*0.9; bd.append(f"MACD bear + falling → +{w*0.9:.1f}")
    elif ml < ms:               bear += w*0.5; bd.append(f"MACD bear → +{w*0.5:.1f}")
    else: bd.append("MACD neutral → 0")

    # 6. ADX (w=10)
    w = 10; mx += w
    av, pdi, mdi = a["adx"], a["plus_di"], a["minus_di"]
    if av > 25:
        f = min(1.0, av / 40)
        if pdi > mdi: bull += w*f; bd.append(f"ADX {av:.0f} +DI>{'-'}DI → +{w*f:.1f}")
        else:         bear += w*f; bd.append(f"ADX {av:.0f} {'-'}DI>+DI → +{w*f:.1f}")
    elif av < 20: bd.append(f"ADX {av:.0f} weak ⚠️")
    else: bd.append(f"ADX {av:.0f} borderline → 0")

    # 7. BOLLINGER (w=6)
    w = 6; mx += w
    cur = a["current_price"]
    bbu, bbm, bbl = a["bb_upper"], a["bb_mid"], a["bb_lower"]
    bw = (bbu - bbl) / (bbm + 1e-10)
    if cur <= bbl:   bull += w*0.9; bd.append(f"BB lower band → +{w*0.9:.1f}")
    elif cur >= bbu: bear += w*0.9; bd.append(f"BB upper band → +{w*0.9:.1f}")
    elif bw < 0.015: bd.append(f"BB SQUEEZE 🔥")
    else: bd.append("BB mid → 0")

    # 8. VOLUME (w=8)
    w = 8; mx += w
    vol = a["volume"]
    vr = vol["vol_ratio"]
    if vol["vol_confirm"] == "bullish" and vr > 1.5:
        f = min(1.0, vr/2.5); bull += w*f; bd.append(f"Vol bull x{vr} → +{w*f:.1f}")
    elif vol["vol_confirm"] == "bearish" and vr > 1.5:
        f = min(1.0, vr/2.5); bear += w*f; bd.append(f"Vol bear x{vr} → +{w*f:.1f}")
    elif vol["vol_confirm"] == "drying_up": bd.append("Vol drying up")
    else: bd.append(f"Vol neutral x{vr}")

    # 9. CANDLE PATTERNS (w=7)
    w = 7; mx += w
    for name, st in a["candle_patterns"]:
        if "bullish" in name or "morning" in name or "white" in name:
            bull += w*st; bd.append(f"Pattern: {name} → +{w*st:.1f}")
        elif "bearish" in name or "evening" in name or "black" in name:
            bear += w*st; bd.append(f"Pattern: {name} → +{w*st:.1f}")
    if not a["candle_patterns"]: bd.append("Patterns: none → 0")

    # 10. ORDER BLOCKS (w=5)
    w = 5; mx += w
    for ob in a["bull_obs"][-3:]:
        if ob["bottom"] <= cur <= ob["top"]:
            f = min(1.0, ob["strength"]/2.5)
            bull += w*f; bd.append(f"In bullish OB → +{w*f:.1f}"); break
    for ob in a["bear_obs"][-3:]:
        if ob["bottom"] <= cur <= ob["top"]:
            f = min(1.0, ob["strength"]/2.5)
            bear += w*f; bd.append(f"In bearish OB → +{w*f:.1f}"); break

    # 11. DIVERGENCE (w=6)
    w = 6; mx += w
    dv = a["divergence"]
    if dv["regular"] == "bullish":   bull += w*0.9; bd.append(f"Regular bull divergence → +{w*0.9:.1f}")
    elif dv["regular"] == "bearish": bear += w*0.9; bd.append(f"Regular bear divergence → +{w*0.9:.1f}")
    elif dv["hidden"] == "bullish":  bull += w*0.6; bd.append(f"Hidden bull div → +{w*0.6:.1f}")
    elif dv["hidden"] == "bearish":  bear += w*0.6; bd.append(f"Hidden bear div → +{w*0.6:.1f}")
    else: bd.append("Divergence: none → 0")

    # 12. LIQUIDITY SWEEP (bonus +5)
    sw = a["liquidity_sweep"]
    if sw["bullish_sweep"]: bull += 5; bd.append("Liq sweep bullish 🎯 → +5")
    elif sw["bearish_sweep"]: bear += 5; bd.append("Liq sweep bearish 🎯 → +5")

    # 13. VWAP (w=5)
    w = 5; mx += w
    vw = a.get("vwap")
    if vw and not np.isnan(vw):
        if cur > vw * 1.001:   bull += w*0.7; bd.append(f"Above VWAP → +{w*0.7:.1f}")
        elif cur < vw * 0.999: bear += w*0.7; bd.append(f"Below VWAP → +{w*0.7:.1f}")
        else: bd.append("At VWAP → 0")

    # 14. EMA 9/21 (w=5 scalp, w=2 swing)
    w = 5 if a["is_scalping"] else 2; mx += w
    e9, e21 = a["ema9"], a["ema21"]
    if e9 > e21 * 1.0005:   bull += w*0.8; bd.append(f"EMA 9>21 → +{w*0.8:.1f}")
    elif e9 < e21 * 0.9995: bear += w*0.8; bd.append(f"EMA 9<21 → +{w*0.8:.1f}")
    else: bd.append("EMA 9/21 intertwined → 0")

    # ── FILTERS ──────────────────────────────────────────────────────
    chop = a["choppiness"]
    if chop > 61.8:
        bull *= 0.6; bear *= 0.6; bd.append(f"⚠️ CHOPPY CI={chop:.1f} → -40%")
    elif chop < 38.2:
        bd.append(f"✅ TRENDING CI={chop:.1f}")

    if av < 15:
        bull *= 0.5; bear *= 0.5; bd.append(f"⚠️ WEAK ADX={av:.0f} → -50%")

    sm = a["session_mult"]
    if sm < 0.8:
        bull *= sm; bear *= sm; bd.append(f"⚠️ Low liquidity → ×{sm}")

    # ── FINAL ────────────────────────────────────────────────────────
    if mx == 0: mx = 100
    nb = (bull / mx) * 100
    ne = (bear / mx) * 100

    if nb > ne and nb >= 45:
        d2 = "BUY"; sc = min(100, nb + min(15, (nb - ne) * 0.3))
    elif ne > nb and ne >= 45:
        d2 = "SELL"; sc = min(100, ne + min(15, (ne - nb) * 0.3))
    else:
        d2 = "WAIT"; sc = max(nb, ne)

    # Counter-trend penalty
    if d2 == "BUY" and td == "bearish" and ts > 0.6:
        sc *= 0.6; bd.append("⚠️ COUNTER-TREND → ×0.6")
    elif d2 == "SELL" and td == "bullish" and ts > 0.6:
        sc *= 0.6; bd.append("⚠️ COUNTER-TREND → ×0.6")

    sc = round(sc, 1)
    if sc >= 90:   strength = "VERY_STRONG"
    elif sc >= 75: strength = "STRONG"
    elif sc >= 60: strength = "MODERATE"
    else:
        strength = "WEAK"
        if d2 != "WAIT": d2 = "WAIT"

    return {
        "direction": d2, "score": sc, "strength": strength,
        "bull_score": round(nb, 1), "bear_score": round(ne, 1), "breakdown": bd,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MAIN ENTRY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def compute_indicators(frames: dict, timeframe: str = "1h") -> dict:
    df_trend, df_struct, df_entry = frames["trend"], frames["structure"], frames["entry"]
    current = round(float(df_entry["close"].iloc[-1]), 5)
    is_scalping = timeframe in ("5m", "15m")
    c = df_entry["close"]

    rsi_val = float(_rsi(c).iloc[-1])
    sk, sd = _stochastic_rsi(c)
    skv = float(sk.iloc[-1]) if not np.isnan(sk.iloc[-1]) else 50
    sdv = float(sd.iloc[-1]) if not np.isnan(sd.iloc[-1]) else 50

    ml, ms, mh = _macd_histogram(c)
    mlv, msv, mhv = float(ml.iloc[-1]), float(ms.iloc[-1]), float(mh.iloc[-1])
    mhpv = float(mh.iloc[-2]) if len(mh) >= 2 else 0

    adx_s, pdi_s, mdi_s = _adx(df_entry)
    adxv = float(adx_s.iloc[-1]) if not np.isnan(adx_s.iloc[-1]) else 20
    pdiv = float(pdi_s.iloc[-1]) if not np.isnan(pdi_s.iloc[-1]) else 0
    mdiv = float(mdi_s.iloc[-1]) if not np.isnan(mdi_s.iloc[-1]) else 0

    bbu, bbm, bbl = _bollinger_bands(c)
    bbuv = float(bbu.iloc[-1]) if not np.isnan(bbu.iloc[-1]) else current * 1.02
    bbmv = float(bbm.iloc[-1]) if not np.isnan(bbm.iloc[-1]) else current
    bblv = float(bbl.iloc[-1]) if not np.isnan(bbl.iloc[-1]) else current * 0.98

    chop = _choppiness_index(df_entry)
    chopv = float(chop.iloc[-1]) if not np.isnan(chop.iloc[-1]) else 50

    e9v  = float(_ema(c, 9).iloc[-1])
    e21v = float(_ema(c, 21).iloc[-1])
    vwap_s = _vwap(df_entry)
    vwapv = float(vwap_s.iloc[-1]) if not np.isnan(vwap_s.iloc[-1]) else None
    atr_val = float(_atr(df_entry).iloc[-1])

    trend_data = _trend_direction(df_trend)
    struct_data = _market_structure(df_struct)
    levels = _key_levels(df_entry)
    sl_levels = _key_levels(df_struct)
    volume = _volume_analysis(df_entry)
    patterns = _candle_patterns(df_entry)
    bob, beob = _detect_order_blocks(df_entry)
    bfvg, befvg = _detect_fvg(df_entry)
    sweep = _detect_liquidity_sweep(df_entry)
    div = _detect_divergence(df_entry)

    all_res = sorted(list(set(levels["resistance"] + sl_levels["resistance"])))[:4]
    all_sup = sorted(list(set(levels["support"] + sl_levels["support"])), reverse=True)[:4]
    combined = {"resistance": all_res, "support": all_sup}

    sn, sl_, sm = _session_info()

    analysis = {
        "current_price": current, "is_scalping": is_scalping,
        "trend_data": trend_data, "structure_data": struct_data,
        "rsi": rsi_val, "stoch_rsi": (skv, sdv),
        "macd_line": mlv, "macd_signal": msv, "macd_hist": mhv, "macd_hist_prev": mhpv,
        "adx": adxv, "plus_di": pdiv, "minus_di": mdiv,
        "bb_upper": bbuv, "bb_mid": bbmv, "bb_lower": bblv,
        "choppiness": chopv, "ema9": e9v, "ema21": e21v, "vwap": vwapv,
        "volume": volume, "candle_patterns": patterns,
        "bull_obs": bob, "bear_obs": beob,
        "divergence": div, "liquidity_sweep": sweep, "session_mult": sm,
    }

    signal = _compute_signal_score(analysis)

    if signal["direction"] != "WAIT":
        trade = _compute_levels(df_entry, timeframe, combined, signal["direction"])
    else:
        trade = {
            "entry": current, "sl": 0, "sl_dist": 0, "tp1": 0, "tp2": 0,
            "rr_ratio": "N/A", "atr": atr_val,
            "validity_minutes": TF_MINUTES.get(timeframe, 60) * 3,
            "local_low": float(np.min(df_entry["low"].values[-10:])),
            "local_high": float(np.max(df_entry["high"].values[-10:])),
        }

    return {
        "current_price": current, "atr": round(atr_val, 5),
        "session": sn, "liquidity": sl_, "session_mult": sm,
        "is_scalping": is_scalping,
        "signal": signal, "trade": trade,
        "trend": trend_data[0], "trend_strength": trend_data[1],
        "structure": struct_data[0], "structure_conf": struct_data[1],
        "rsi": round(rsi_val, 1), "stoch_k": round(skv, 1), "stoch_d": round(sdv, 1),
        "macd_direction": "bullish" if mlv > msv else "bearish",
        "macd_hist_val": round(mhv, 5),
        "adx": round(adxv, 1), "plus_di": round(pdiv, 1), "minus_di": round(mdiv, 1),
        "bb_position": "upper" if current >= bbuv else ("lower" if current <= bblv else "mid"),
        "choppiness": round(chopv, 1), "ema9": round(e9v, 5), "ema21": round(e21v, 5),
        "vwap": round(vwapv, 5) if vwapv else None, "volume": volume,
        "resistance": all_res, "support": all_sup,
        "bull_order_blocks": len(bob), "bear_order_blocks": len(beob),
        "bull_fvg_count": len(bfvg), "bear_fvg_count": len(befvg),
        "liquidity_sweep": sweep, "divergence": div,
        "candle_patterns": patterns, "score_breakdown": signal["breakdown"],
    }
