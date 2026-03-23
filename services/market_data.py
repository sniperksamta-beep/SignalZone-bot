import os
import pandas as pd
import numpy as np
import aiohttp
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


def detect_order_blocks(df: pd.DataFrame) -> dict:
    """
    Order Block: آخر شمعة هابطة قبل حركة صاعدة قوية (Bullish OB)
                 أو آخر شمعة صاعدة قبل حركة هابطة قوية (Bearish OB)
    """
    bullish_obs = []
    bearish_obs = []

    for i in range(2, len(df) - 3):
        candle    = df.iloc[i]
        next1     = df.iloc[i+1]
        next2     = df.iloc[i+2]
        next3     = df.iloc[i+3]

        # Bullish OB: شمعة حمراء يعقبها 3 شمعات خضراء قوية
        if (candle["close"] < candle["open"] and
            next1["close"] > next1["open"] and
            next2["close"] > next2["open"] and
            next3["high"] > candle["high"]):
            bullish_obs.append({
                "top":    round(float(candle["open"]), 5),
                "bottom": round(float(candle["low"]),  5),
                "index":  i,
            })

        # Bearish OB: شمعة خضراء يعقبها 3 شمعات حمراء قوية
        if (candle["close"] > candle["open"] and
            next1["close"] < next1["open"] and
            next2["close"] < next2["open"] and
            next3["low"] < candle["low"]):
            bearish_obs.append({
                "top":    round(float(candle["high"]), 5),
                "bottom": round(float(candle["close"]),5),
                "index":  i,
            })

    current = float(df["close"].iloc[-1])

    # أقرب OB للسعر الحالي
    nearest_bullish = sorted(
        [ob for ob in bullish_obs if ob["top"] < current],
        key=lambda x: current - x["top"]
    )[:2]

    nearest_bearish = sorted(
        [ob for ob in bearish_obs if ob["bottom"] > current],
        key=lambda x: x["bottom"] - current
    )[:2]

    return {"bullish": nearest_bullish, "bearish": nearest_bearish}


def detect_fvg(df: pd.DataFrame) -> dict:
    """
    Fair Value Gap: فجوة بين شمعتين لم يتم ملؤها
    Bullish FVG: low[i+2] > high[i]
    Bearish FVG: high[i+2] < low[i]
    """
    bullish_fvgs = []
    bearish_fvgs = []
    current = float(df["close"].iloc[-1])

    for i in range(len(df) - 3, max(len(df) - 50, 0), -1):
        c1 = df.iloc[i]
        c3 = df.iloc[i+2]

        # Bullish FVG
        if float(c3["low"]) > float(c1["high"]):
            fvg_top    = round(float(c3["low"]),  5)
            fvg_bottom = round(float(c1["high"]), 5)
            fvg_mid    = round((fvg_top + fvg_bottom) / 2, 5)
            if fvg_bottom < current:
                bullish_fvgs.append({"top": fvg_top, "bottom": fvg_bottom, "mid": fvg_mid})

        # Bearish FVG
        if float(c3["high"]) < float(c1["low"]):
            fvg_top    = round(float(c1["low"]),   5)
            fvg_bottom = round(float(c3["high"]),  5)
            fvg_mid    = round((fvg_top + fvg_bottom) / 2, 5)
            if fvg_top > current:
                bearish_fvgs.append({"top": fvg_top, "bottom": fvg_bottom, "mid": fvg_mid})

    return {
        "bullish": bullish_fvgs[:2],
        "bearish": bearish_fvgs[:2],
    }


def detect_liquidity(df: pd.DataFrame) -> dict:
    """
    مناطق السيولة: Equal Highs / Equal Lows
    هذه المناطق تجذب السعر لأنها تجمع وقوف الخسارة
    """
    recent  = df.tail(50)
    highs   = recent["high"].values
    lows    = recent["low"].values
    current = float(df["close"].iloc[-1])

    tolerance = current * 0.0005  # 0.05% tolerance

    eq_highs = []
    eq_lows  = []

    for i in range(len(highs)):
        for j in range(i+3, len(highs)):
            if abs(highs[i] - highs[j]) <= tolerance:
                eq_highs.append(round(float((highs[i] + highs[j]) / 2), 5))

    for i in range(len(lows)):
        for j in range(i+3, len(lows)):
            if abs(lows[i] - lows[j]) <= tolerance:
                eq_lows.append(round(float((lows[i] + lows[j]) / 2), 5))

    # فلترة وإزالة التكرار
    eq_highs = list(set([round(h, 3) for h in eq_highs if h > current]))[:3]
    eq_lows  = list(set([round(l, 3) for l in eq_lows  if l < current]))[:3]

    return {
        "equal_highs": sorted(eq_highs),
        "equal_lows":  sorted(eq_lows, reverse=True),
    }


def detect_bos_choch(df: pd.DataFrame) -> dict:
    """
    Break of Structure (BOS): استمرار الاتجاه
    Change of Character (CHoCH): انعكاس الاتجاه
    """
    recent = df.tail(30)
    swing_highs = []
    swing_lows  = []

    for i in range(2, len(recent) - 2):
        h = recent["high"].iloc
        l = recent["low"].iloc
        if h[i] > h[i-1] and h[i] > h[i-2] and h[i] > h[i+1] and h[i] > h[i+2]:
            swing_highs.append((i, float(h[i])))
        if l[i] < l[i-1] and l[i] < l[i-2] and l[i] < l[i+1] and l[i] < l[i+2]:
            swing_lows.append((i, float(l[i])))

    structure = "neutral"
    last_bos  = None

    if len(swing_highs) >= 2 and len(swing_lows) >= 2:
        # Bullish: Higher Highs + Higher Lows
        if (swing_highs[-1][1] > swing_highs[-2][1] and
                swing_lows[-1][1] > swing_lows[-2][1]):
            structure = "bullish"
            last_bos  = round(swing_highs[-1][1], 5)

        # Bearish: Lower Highs + Lower Lows
        elif (swing_highs[-1][1] < swing_highs[-2][1] and
              swing_lows[-1][1] < swing_lows[-2][1]):
            structure = "bearish"
            last_bos  = round(swing_lows[-1][1], 5)

        # CHoCH: آخر High أعلى لكن آخر Low كسر للأسفل
        elif (swing_highs[-1][1] > swing_highs[-2][1] and
              swing_lows[-1][1] < swing_lows[-2][1]):
            structure = "choch_bearish"
            last_bos  = round(swing_lows[-1][1], 5)

        elif (swing_highs[-1][1] < swing_highs[-2][1] and
              swing_lows[-1][1] > swing_lows[-2][1]):
            structure = "choch_bullish"
            last_bos  = round(swing_highs[-1][1], 5)

    return {"structure": structure, "last_level": last_bos}


def detect_premium_discount(df: pd.DataFrame) -> dict:
    """
    Premium Zone: فوق 50% من الـ range — منطقة البيع
    Discount Zone: تحت 50% من الـ range — منطقة الشراء
    """
    swing_high = float(df["high"].tail(50).max())
    swing_low  = float(df["low"].tail(50).min())
    current    = float(df["close"].iloc[-1])
    mid        = (swing_high + swing_low) / 2

    zone = "premium" if current > mid else "discount"
    pct  = round((current - swing_low) / (swing_high - swing_low) * 100, 1)

    return {
        "zone":        zone,
        "percentage":  pct,
        "mid":         round(mid, 5),
        "swing_high":  round(swing_high, 5),
        "swing_low":   round(swing_low,  5),
    }


def compute_indicators(df: pd.DataFrame) -> dict:
    """يحسب جميع مؤشرات SMC."""
    current = round(float(df["close"].iloc[-1]), 5)

    # اتجاه EMA البسيط للتأكيد
    close  = df["close"]
    ema50  = close.ewm(span=50,  adjust=False).mean()
    ema200 = close.ewm(span=200, adjust=False).mean()
    ema_bias = "bullish" if float(ema50.iloc[-1]) > float(ema200.iloc[-1]) else "bearish"

    # RSI للتأكيد فقط
    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rsi   = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))
    rsi_val = round(float(rsi.iloc[-1]), 1)

    # ATR للمسافات
    high = df["high"]
    low  = df["low"]
    tr   = pd.concat([(high-low), (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
    atr  = round(float(tr.rolling(14).mean().iloc[-1]), 5)

    return {
        "current_price":   current,
        "ema_bias":        ema_bias,
        "rsi":             rsi_val,
        "atr":             atr,
        "order_blocks":    detect_order_blocks(df),
        "fvg":             detect_fvg(df),
        "liquidity":       detect_liquidity(df),
        "structure":       detect_bos_choch(df),
        "premium_discount": detect_premium_discount(df),
        "last_5_candles": [
            {
                "open":  round(float(df["open"].iloc[i]),  5),
                "high":  round(float(df["high"].iloc[i]),  5),
                "low":   round(float(df["low"].iloc[i]),   5),
                "close": round(float(df["close"].iloc[i]), 5),
            }
            for i in range(-5, 0)
        ],
    }
