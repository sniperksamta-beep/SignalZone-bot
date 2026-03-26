"""
market_data.py — Multi-Timeframe Confluence + Scalping Layer
"""
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

# دقائق كل فريم — لحساب مدة الصلاحية
TF_MINUTES = {"5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}


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
    sym  = TWELVE_SYMBOLS.get(pair, pair)
    mtf  = MTF_MAP.get(timeframe, MTF_MAP["1h"])
    frames = {}
    for role, tf in mtf.items():
        frames[role] = await _fetch(sym, TWELVE_INTERVALS.get(tf, "1h"))
    return frames


# ── مؤشرات أساسية ─────────────────────────────────────────────────

def _ema(s, span):
    return s.ewm(span=span, adjust=False).mean()

def _rsi(s, period=14):
    d  = s.diff()
    g  = d.clip(lower=0).rolling(period).mean()
    l  = (-d.clip(upper=0)).rolling(period).mean()
    return 100 - (100 / (1 + g / l.replace(0, np.nan)))

def _atr(df, period=14):
    h, l, c = df["high"], df["low"], df["close"]
    tr = pd.concat([(h-l),(h-c.shift()).abs(),(l-c.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def _trend_direction(df) -> str:
    c    = df["close"]
    e50  = float(_ema(c, 50).iloc[-1])
    e200 = float(_ema(c, 200).iloc[-1])
    if   e50 > e200 * 1.001: return "bullish"
    elif e50 < e200 * 0.999: return "bearish"
    return "neutral"

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
        if   highs[-1] > highs[-2] and lows[-1] > lows[-2]: return "bullish"
        elif highs[-1] < highs[-2] and lows[-1] < lows[-2]: return "bearish"
        elif highs[-1] > highs[-2] and lows[-1] < lows[-2]: return "choch_bearish"
        elif highs[-1] < highs[-2] and lows[-1] > lows[-2]: return "choch_bullish"
    return "neutral"

def _momentum(df) -> dict:
    c         = df["close"]
    rsi_val   = round(float(_rsi(c).iloc[-1]), 1)
    macd_line = _ema(c, 12) - _ema(c, 26)
    signal    = _ema(macd_line, 9)
    return {
        "rsi":  rsi_val,
        "macd": "bullish" if float(macd_line.iloc[-1]) > float(signal.iloc[-1]) else "bearish"
    }

def _key_levels(df) -> dict:
    current   = float(df["close"].iloc[-1])
    h         = df["high"].values
    l         = df["low"].values
    tolerance = current * 0.0015
    res, sup  = [], []

    for i in range(2, len(h)-2):
        if h[i] > h[i-1] and h[i] > h[i+1]:
            for j in range(i+2, min(i+40, len(h))):
                if abs(h[j]-h[i]) < tolerance and h[j] > current:
                    res.append(round((h[i]+h[j])/2, 5))
                    break
        if l[i] < l[i-1] and l[i] < l[i+1]:
            for j in range(i+2, min(i+40, len(l))):
                if abs(l[j]-l[i]) < tolerance and l[j] < current:
                    sup.append(round((l[i]+l[j])/2, 5))
                    break

    return {
        "resistance": sorted(list(set([round(r,3) for r in res if r > current])))[:3],
        "support":    sorted(list(set([round(s,3) for s in sup if s < current])), reverse=True)[:3],
    }

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

    rejection = None
    if upper_wick[-1] / total_range[-1] > 0.6: rejection = "bearish"
    elif lower_wick[-1] / total_range[-1] > 0.6: rejection = "bullish"

    return {
        "is_squeeze": is_squeeze,
        "rejection":  rejection,
        "immediate":  "bullish" if c[-1] > c[-3] else "bearish",
    }


# ── طبقة المضاربة (Scalping Layer) — للفريمات الصغيرة ─────────────

def _candle_pattern(df) -> str:
    """
    اكتشاف أنماط الشمعات اللحظية:
    - Bullish Engulfing: شمعة خضراء تبتلع الحمراء قبلها
    - Bearish Engulfing: شمعة حمراء تبتلع الخضراء قبلها
    - Pin Bar: فتيل طويل جداً = رفض قوي
    - Inside Bar: شمعة داخل السابقة = ضغط قبل انفجار
    - Doji: جسم صغير جداً = تردد في لحظة قرار
    """
    o = df["open"].values
    h = df["high"].values
    l = df["low"].values
    c = df["close"].values

    if len(c) < 3:
        return "none"

    total_range = h - l + 1e-10
    body        = np.abs(c - o)
    upper_wick  = h - np.maximum(c, o)
    lower_wick  = np.minimum(c, o) - l

    # آخر 3 شمعات
    prev2, prev1, last = -3, -2, -1

    # Bullish Engulfing
    if (c[prev1] < o[prev1] and  # الشمعة السابقة حمراء
        c[last] > o[last] and    # الأخيرة خضراء
        o[last] <= c[prev1] and  # تفتح عند أو تحت إغلاق السابقة
        c[last] >= o[prev1]):    # تغلق عند أو فوق فتح السابقة
        return "bullish_engulfing"

    # Bearish Engulfing
    if (c[prev1] > o[prev1] and
        c[last] < o[last] and
        o[last] >= c[prev1] and
        c[last] <= o[prev1]):
        return "bearish_engulfing"

    # Bullish Pin Bar (hammer)
    if (lower_wick[last] > body[last] * 2 and
        lower_wick[last] > upper_wick[last] * 3):
        return "bullish_pin_bar"

    # Bearish Pin Bar (shooting star)
    if (upper_wick[last] > body[last] * 2 and
        upper_wick[last] > lower_wick[last] * 3):
        return "bearish_pin_bar"

    # Inside Bar
    if (h[last] <= h[prev1] and l[last] >= l[prev1]):
        return "inside_bar"

    # Doji
    if body[last] / total_range[last] < 0.1:
        return "doji"

    return "none"


def _price_velocity(df) -> dict:
    """
    سرعة تحرك السعر — كم نقطة لكل شمعة مقارنة بالمتوسط.
    يكشف تسارع أو تباطؤ الحركة.
    """
    c = df["close"].values
    h = df["high"].values
    l = df["low"].values

    # تحرك كل شمعة
    moves     = np.abs(np.diff(c))
    avg_move  = float(np.mean(moves[-20:]))  # متوسط 20 شمعة
    last_move = float(moves[-1]) if len(moves) > 0 else 0

    # هل السرعة تتسارع؟
    velocity_ratio = round(last_move / avg_move, 2) if avg_move > 0 else 1.0
    is_accelerating = velocity_ratio > 1.5

    # اتجاه الزخم (آخر 3 شمعات)
    if len(c) >= 4:
        recent_move = c[-1] - c[-4]
        momentum_dir = "bullish" if recent_move > 0 else "bearish"
    else:
        momentum_dir = "neutral"

    return {
        "velocity_ratio":    velocity_ratio,
        "is_accelerating":   is_accelerating,
        "momentum_direction": momentum_dir,
        "avg_move":          round(avg_move, 5),
        "last_move":         round(last_move, 5),
    }


def _compute_sl_and_validity(df, timeframe: str, levels: dict) -> dict:
    """
    يحسب وقف الخسارة ومدة الصلاحية برمجياً بدقة.

    وقف الخسارة:
    - للشراء: أقرب دعم تحت السعر - هامش أمان (ATR × 0.3)
              إذا لم يوجد دعم → السعر - ATR × 1.5
    - للبيع: أقرب مقاومة فوق السعر + هامش أمان (ATR × 0.3)
             إذا لم توجد مقاومة → السعر + ATR × 1.5

    مدة الصلاحية:
    - تُحسب من: (مسافة الهدف المتوقعة / متوسط حجم الشمعة) × دقائق الفريم
    - الهدف المتوقع = ATR × 2 (هدف أول واقعي)
    """
    current = float(df["close"].iloc[-1])
    atr_val = float(_atr(df).iloc[-1])
    tf_min  = TF_MINUTES.get(timeframe, 60)

    # ── وقف الخسارة للشراء ───────────────────────────────────────
    safety_margin = atr_val * 0.3
    supports      = levels.get("support", [])
    resistances   = levels.get("resistance", [])

    if supports:
        # أقرب دعم تحت السعر
        nearest_sup = supports[0]  # مرتبة تنازلياً (الأقرب أولاً)
        sl_buy      = round(nearest_sup - safety_margin, 5)
    else:
        sl_buy = round(current - atr_val * 1.5, 5)

    # تأكد أن SL أبعد من ATR × 0.8 على الأقل
    min_sl_distance = atr_val * 0.8
    if current - sl_buy < min_sl_distance:
        sl_buy = round(current - min_sl_distance, 5)

    # ── وقف الخسارة للبيع ────────────────────────────────────────
    if resistances:
        nearest_res = resistances[0]
        sl_sell     = round(nearest_res + safety_margin, 5)
    else:
        sl_sell = round(current + atr_val * 1.5, 5)

    if sl_sell - current < min_sl_distance:
        sl_sell = round(current + min_sl_distance, 5)

    # ── مدة الصلاحية ─────────────────────────────────────────────
    # متوسط حركة كل شمعة
    moves     = np.abs(np.diff(df["close"].values[-20:]))
    avg_move  = float(np.mean(moves)) if len(moves) > 0 else atr_val * 0.3

    # الهدف الأول = ATR × 1.5
    target_distance = atr_val * 1.5

    # عدد الشمعات المتوقعة للوصول للهدف
    expected_candles = max(3, int(target_distance / avg_move)) if avg_move > 0 else 5

    # ضرب في 1.5 لإعطاء هامش وقت
    validity_minutes = int(expected_candles * tf_min * 1.5)

    # حد أدنى وأقصى
    min_validity = tf_min * 3
    max_validity = tf_min * 20
    validity_minutes = max(min_validity, min(validity_minutes, max_validity))

    return {
        "sl_buy":          sl_buy,
        "sl_sell":         sl_sell,
        "sl_distance_buy": round(current - sl_buy,  5),
        "sl_distance_sell":round(sl_sell - current, 5),
        "validity_minutes": validity_minutes,
        "atr":             round(atr_val, 5),
    }


def compute_indicators(frames: dict, timeframe: str = "1h") -> dict:
    df_trend     = frames["trend"]
    df_structure = frames["structure"]
    df_entry     = frames["entry"]

    current = round(float(df_entry["close"].iloc[-1]), 5)

    trend_dir     = _trend_direction(df_trend)
    struct_dir    = _structure(df_structure)
    struct_levels = _key_levels(df_structure)
    entry_mom     = _momentum(df_entry)
    entry_q       = _entry_quality(df_entry)
    entry_levels  = _key_levels(df_entry)

    # دمج المستويات
    all_res = sorted(list(set(struct_levels["resistance"] + entry_levels["resistance"])))[:3]
    all_sup = sorted(list(set(struct_levels["support"]    + entry_levels["support"])), reverse=True)[:3]
    combined_levels = {"resistance": all_res, "support": all_sup}

    # حساب SL ومدة الصلاحية برمجياً
    sl_data = _compute_sl_and_validity(df_entry, timeframe, combined_levels)

    # Scalping Layer — للفريمات الصغيرة
    is_scalping = timeframe in ("5m", "15m")
    scalping_data = None
    if is_scalping:
        scalping_data = {
            "candle_pattern": _candle_pattern(df_entry),
            "velocity":       _price_velocity(df_entry),
        }

    # حساب التوافق
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

    # للمضاربة: أضف وزن إضافي لأنماط الشمعات
    if is_scalping and scalping_data:
        pattern = scalping_data["candle_pattern"]
        if pattern in ("bullish_engulfing", "bullish_pin_bar"):
            signals.append("bullish")
        elif pattern in ("bearish_engulfing", "bearish_pin_bar"):
            signals.append("bearish")

    bull_count = signals.count("bullish")
    bear_count = signals.count("bearish")
    total      = len(signals)

    if bull_count >= 4:   confluence = "strong_bullish"
    elif bull_count >= 3: confluence = "bullish"
    elif bear_count >= 4: confluence = "strong_bearish"
    elif bear_count >= 3: confluence = "bearish"
    else:                 confluence = "neutral"

    # جلسة التداول
    hour = datetime.now(timezone.utc).hour
    if   8  <= hour < 13: session, liquidity = "لندن 🇬🇧",            "عالية"
    elif 13 <= hour < 17: session, liquidity = "تداخل لندن-نيويورك 🔥", "أعلى سيولة"
    elif 17 <= hour < 22: session, liquidity = "نيويورك 🇺🇸",          "عالية"
    else:                 session, liquidity = "آسيا 🌏",               "منخفضة"

    return {
        "current_price":   current,
        "atr":             sl_data["atr"],
        "session":         session,
        "liquidity":       liquidity,
        "confluence":      confluence,
        "bull_count":      bull_count,
        "bear_count":      bear_count,
        "trend":           trend_dir,
        "structure":       struct_dir,
        "momentum":        entry_mom,
        "entry_quality":   entry_q,
        "resistance":      all_res,
        "support":         all_sup,
        "sl_buy":          sl_data["sl_buy"],
        "sl_sell":         sl_data["sl_sell"],
        "sl_distance_buy": sl_data["sl_distance_buy"],
        "sl_distance_sell":sl_data["sl_distance_sell"],
        "validity_minutes":sl_data["validity_minutes"],
        "is_scalping":     is_scalping,
        "scalping":        scalping_data,
    }
