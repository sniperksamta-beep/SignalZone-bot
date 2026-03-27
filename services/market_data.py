"""
market_data.py — Multi-Timeframe Confluence + Micro-Structure Scalping
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
    "5m": "5min", "15m": "15min",
    "1h": "1h",   "4h":  "4h",   "1d": "1day",
}

TF_MINUTES = {"5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}


async def _fetch(symbol: str, interval: str, size: int = 150) -> pd.DataFrame:
    """جلب البيانات مع معالجة صحيحة للأخطاء."""
    params = {
        "symbol":     symbol,
        "interval":   interval,
        "outputsize": size,
        "apikey":     TWELVE_KEY,
        "format":     "JSON",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                TWELVE_URL, params=params,
                timeout=aiohttp.ClientTimeout(total=25),
                headers={"Accept": "application/json"}
            ) as resp:
                # تحقق من نوع المحتوى قبل تحليل JSON
                content_type = resp.headers.get("Content-Type", "")
                if "html" in content_type.lower():
                    raise ValueError(f"Twelve Data rate limit أو مشكلة في الـ API key — تحقق من الـ key وحاول لاحقاً")

                if resp.status != 200:
                    raise ValueError(f"Twelve Data HTTP {resp.status}")

                text = await resp.text()
                if not text.strip().startswith("{"):
                    raise ValueError("Twelve Data أعاد استجابة غير صالحة — ربما rate limit")

                import json
                data = json.loads(text)

    except aiohttp.ClientError as e:
        raise ValueError(f"خطأ في الاتصال بـ Twelve Data: {str(e)[:100]}")

    if data.get("status") == "error":
        msg = data.get("message", "unknown")
        if "api key" in msg.lower() or "unauthorized" in msg.lower():
            raise ValueError("مفتاح Twelve Data غير صالح — تحقق من TWELVE_DATA_KEY في Railway")
        raise ValueError(f"Twelve Data: {msg[:150]}")

    values = data.get("values", [])
    if not values:
        raise ValueError(f"لا توجد بيانات لهذا الزوج — جرّب فريماً آخر")

    df = pd.DataFrame(values)
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0) if "volume" in df.columns else 0
    df = df[["open", "high", "low", "close", "volume"]].dropna()
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
    d = s.diff()
    g = d.clip(lower=0).rolling(period).mean()
    l = (-d.clip(upper=0)).rolling(period).mean()
    return 100 - (100 / (1 + g / l.replace(0, np.nan)))

def _atr(df, period=14):
    h, l, c = df["high"], df["low"], df["close"]
    tr = pd.concat([(h-l), (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def _trend_direction(df) -> str:
    c = df["close"]
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
    avg20 = np.mean(total_range[-20:])
    avg5  = np.mean(total_range[-5:])
    upper_wick = h - np.maximum(c, o)
    lower_wick = np.minimum(c, o) - l
    rejection = None
    if upper_wick[-1] / total_range[-1] > 0.6: rejection = "bearish"
    elif lower_wick[-1] / total_range[-1] > 0.6: rejection = "bullish"
    return {
        "is_squeeze": (avg5 / avg20) < 0.6,
        "rejection":  rejection,
        "immediate":  "bullish" if c[-1] > c[-3] else "bearish",
    }


# ── Micro-Structure Analysis (نظام المضاربة الجديد) ──────────────

def micro_structure_analysis(df: pd.DataFrame) -> dict:
    """
    تحليل البنية المصغّرة لاكتشاف لحظات الدخول الدقيقة.

    يقيس 4 أشياء حقيقية تحدث قبل الحركة:

    1. PRICE MAGNET: هل السعر ينجذب نحو مستوى قريب؟
       الأسواق تتحرك من مستوى إلى مستوى — اكتشف الوجهة التالية.

    2. MOMENTUM DIVERGENCE: هل السعر يرتفع لكن زخم الشمعات يضعف؟
       هذا يسبق الانعكاس بشمعات.

    3. ABSORPTION: هل هناك شمعات كبيرة تُمتص بلا تحرك؟
       مثل لاعب كبير يشتري كل ما يُباع — يسبق الصعود.

    4. MICRO BREAKOUT: هل كسر السعر نطاق الـ 10 شمعات الأخيرة؟
       أول كسر حقيقي = دخول مبكر في الاتجاه.
    """
    c = df["close"].values
    h = df["high"].values
    l = df["low"].values
    o = df["open"].values
    total_range = h - l + 1e-10
    body        = np.abs(c - o)

    results = {}

    # ── 1. PRICE MAGNET ────────────────────────────────────────────
    # أقرب قمة وقاع في آخر 20 شمعة
    recent_h = np.max(h[-20:])
    recent_l = np.min(l[-20:])
    current  = c[-1]
    mid      = (recent_h + recent_l) / 2

    dist_to_high = recent_h - current
    dist_to_low  = current - recent_l

    if dist_to_high < dist_to_low * 0.4:
        magnet = "resistance_near"   # قريب جداً من المقاومة — خطر
        magnet_level = round(float(recent_h), 5)
    elif dist_to_low < dist_to_high * 0.4:
        magnet = "support_near"      # قريب جداً من الدعم — فرصة
        magnet_level = round(float(recent_l), 5)
    elif current > mid:
        magnet = "pulling_to_high"   # السعر فوق المنتصف — يشد للأعلى
        magnet_level = round(float(recent_h), 5)
    else:
        magnet = "pulling_to_low"    # السعر تحت المنتصف — يشد للأسفل
        magnet_level = round(float(recent_l), 5)

    results["magnet"] = magnet
    results["magnet_level"] = magnet_level

    # ── 2. MOMENTUM DIVERGENCE ─────────────────────────────────────
    # قارن اتجاه السعر مع قوة الشمعات
    price_slope_3 = c[-1] - c[-4]   # اتجاه السعر (آخر 3)
    body_avg_3    = np.mean(body[-3:])
    body_avg_prev = np.mean(body[-6:-3])

    if price_slope_3 > 0 and body_avg_3 < body_avg_prev * 0.6:
        divergence = "bearish_div"   # صعود مع ضعف — انعكاس محتمل
    elif price_slope_3 < 0 and body_avg_3 < body_avg_prev * 0.6:
        divergence = "bullish_div"   # هبوط مع ضعف — انتعاش محتمل
    else:
        divergence = "none"

    results["divergence"] = divergence

    # ── 3. ABSORPTION ──────────────────────────────────────────────
    # شمعة كبيرة جسمها صغير = امتصاص
    # (شمعة كبيرة المدى لكن السعر لم يتحرك كثيراً)
    last_range = total_range[-1]
    last_body  = body[-1]
    absorption_ratio = last_body / last_range

    avg_range = np.mean(total_range[-10:])
    is_large_candle = last_range > avg_range * 1.5

    if is_large_candle and absorption_ratio < 0.25:
        # شمعة كبيرة لكن جسمها صغير = امتصاص
        if c[-1] > o[-1]:
            absorption = "bullish_absorption"   # امتصاص البيع
        else:
            absorption = "bearish_absorption"   # امتصاص الشراء
    else:
        absorption = "none"

    results["absorption"] = absorption

    # ── 4. MICRO BREAKOUT ──────────────────────────────────────────
    # هل كسر السعر نطاق آخر 10 شمعات؟
    range_10_high = np.max(h[-11:-1])   # أعلى نقطة قبل الشمعة الأخيرة
    range_10_low  = np.min(l[-11:-1])   # أدنى نقطة قبل الشمعة الأخيرة

    if c[-1] > range_10_high and body[-1] / total_range[-1] > 0.5:
        breakout = "bullish_breakout"   # كسر صاعد حقيقي
    elif c[-1] < range_10_low and body[-1] / total_range[-1] > 0.5:
        breakout = "bearish_breakout"   # كسر هابط حقيقي
    else:
        breakout = "none"

    results["breakout"] = breakout

    # ── النتيجة المركّبة ────────────────────────────────────────────
    bullish_signals = 0
    bearish_signals = 0

    if magnet in ("support_near", "pulling_to_high"):    bullish_signals += 1
    if magnet in ("resistance_near", "pulling_to_low"):  bearish_signals += 1
    if divergence == "bullish_div":  bullish_signals += 1
    if divergence == "bearish_div":  bearish_signals += 1
    if absorption == "bullish_absorption": bullish_signals += 1
    if absorption == "bearish_absorption": bearish_signals += 1
    if breakout == "bullish_breakout": bullish_signals += 2  # وزن مضاعف
    if breakout == "bearish_breakout": bearish_signals += 2

    if bullish_signals >= 3:   micro_bias = "strong_bullish"
    elif bullish_signals >= 2: micro_bias = "bullish"
    elif bearish_signals >= 3: micro_bias = "strong_bearish"
    elif bearish_signals >= 2: micro_bias = "bearish"
    else:                      micro_bias = "neutral"

    results["micro_bias"]     = micro_bias
    results["bull_micro"]     = bullish_signals
    results["bear_micro"]     = bearish_signals
    results["range_10_high"]  = round(float(range_10_high), 5)
    results["range_10_low"]   = round(float(range_10_low), 5)

    return results


def _compute_precise_sl(df, timeframe: str, levels: dict) -> dict:
    """
    وقف خسارة دقيق مبني على البنية الفعلية.

    للشراء:
      1. آخر قاع محلي في آخر 5 شمعات - هامش صغير
      2. إذا لم يوجد → أقرب دعم - هامش
      3. الحد الأدنى: ATR × 0.5 عن السعر الحالي

    للبيع:
      1. آخر قمة محلية في آخر 5 شمعات + هامش صغير
      2. إذا لم توجد → أقرب مقاومة + هامش
      3. الحد الأدنى: ATR × 0.5 عن السعر الحالي
    """
    current  = float(df["close"].iloc[-1])
    atr_val  = float(_atr(df).iloc[-1])
    tf_min   = TF_MINUTES.get(timeframe, 60)
    margin   = atr_val * 0.25   # هامش أمان صغير

    # ── آخر قاع/قمة محلية في آخر 8 شمعات ─────────────────────────
    recent_lows  = df["low"].values[-8:]
    recent_highs = df["high"].values[-8:]
    local_low    = float(np.min(recent_lows))
    local_high   = float(np.max(recent_highs))

    # ── SL للشراء ─────────────────────────────────────────────────
    sl_buy = round(local_low - margin, 5)

    # تأكد من حد أدنى ATR × 0.5 وحد أقصى ATR × 2
    min_dist = atr_val * 0.5
    max_dist = atr_val * 2.0

    sl_buy_dist = current - sl_buy
    if sl_buy_dist < min_dist:
        sl_buy = round(current - min_dist, 5)
    elif sl_buy_dist > max_dist:
        # استخدم الدعم القريب إذا كان الـ SL بعيداً جداً
        supports = levels.get("support", [])
        if supports:
            sl_buy = round(supports[0] - margin, 5)
        else:
            sl_buy = round(current - max_dist, 5)

    # ── SL للبيع ──────────────────────────────────────────────────
    sl_sell = round(local_high + margin, 5)

    sl_sell_dist = sl_sell - current
    if sl_sell_dist < min_dist:
        sl_sell = round(current + min_dist, 5)
    elif sl_sell_dist > max_dist:
        resistances = levels.get("resistance", [])
        if resistances:
            sl_sell = round(resistances[0] + margin, 5)
        else:
            sl_sell = round(current + max_dist, 5)

    # ── مدة الصلاحية من ATR ───────────────────────────────────────
    moves    = np.abs(np.diff(df["close"].values[-20:]))
    avg_move = float(np.mean(moves)) if len(moves) > 0 else atr_val * 0.3

    target_dist      = atr_val * 1.5
    expected_candles = max(3, int(target_dist / avg_move)) if avg_move > 0 else 5
    validity_minutes = int(expected_candles * tf_min * 1.5)
    validity_minutes = max(tf_min * 3, min(validity_minutes, tf_min * 20))

    return {
        "sl_buy":           sl_buy,
        "sl_sell":          sl_sell,
        "sl_distance_buy":  round(current - sl_buy,   5),
        "sl_distance_sell": round(sl_sell - current,  5),
        "validity_minutes": validity_minutes,
        "atr":              round(atr_val, 5),
        "local_low":        round(local_low, 5),
        "local_high":       round(local_high, 5),
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

    all_res = sorted(list(set(struct_levels["resistance"] + entry_levels["resistance"])))[:3]
    all_sup = sorted(list(set(struct_levels["support"]    + entry_levels["support"])), reverse=True)[:3]
    combined = {"resistance": all_res, "support": all_sup}

    sl_data = _compute_precise_sl(df_entry, timeframe, combined)

    # Micro-Structure للفريمات الصغيرة
    is_scalping   = timeframe in ("5m", "15m")
    micro_data    = micro_structure_analysis(df_entry) if is_scalping else None

    # حساب التوافق
    signals = []
    if trend_dir == "bullish":                         signals.append("bullish")
    elif trend_dir == "bearish":                       signals.append("bearish")
    if struct_dir in ("bullish","choch_bullish"):      signals.append("bullish")
    elif struct_dir in ("bearish","choch_bearish"):    signals.append("bearish")
    if entry_mom["rsi"] < 40:                          signals.append("bullish")
    elif entry_mom["rsi"] > 60:                        signals.append("bearish")
    if entry_mom["macd"] == "bullish":                 signals.append("bullish")
    else:                                              signals.append("bearish")
    if entry_q["immediate"] == "bullish":              signals.append("bullish")
    else:                                              signals.append("bearish")

    # أضف وزن الـ Micro-Structure
    if micro_data:
        if micro_data["micro_bias"] in ("strong_bullish","bullish"):
            signals.append("bullish")
        elif micro_data["micro_bias"] in ("strong_bearish","bearish"):
            signals.append("bearish")

    bull_count = signals.count("bullish")
    bear_count = signals.count("bearish")

    if bull_count >= 4:   confluence = "strong_bullish"
    elif bull_count >= 3: confluence = "bullish"
    elif bear_count >= 4: confluence = "strong_bearish"
    elif bear_count >= 3: confluence = "bearish"
    else:                 confluence = "neutral"

    hour = datetime.now(timezone.utc).hour
    if   8  <= hour < 13: session, liquidity = "لندن 🇬🇧",             "عالية"
    elif 13 <= hour < 17: session, liquidity = "تداخل لندن-نيويورك 🔥", "أعلى سيولة"
    elif 17 <= hour < 22: session, liquidity = "نيويورك 🇺🇸",           "عالية"
    else:                 session, liquidity = "آسيا 🌏",                "منخفضة"

    return {
        "current_price":    current,
        "atr":              sl_data["atr"],
        "session":          session,
        "liquidity":        liquidity,
        "confluence":       confluence,
        "bull_count":       bull_count,
        "bear_count":       bear_count,
        "trend":            trend_dir,
        "structure":        struct_dir,
        "momentum":         entry_mom,
        "entry_quality":    entry_q,
        "resistance":       all_res,
        "support":          all_sup,
        "sl_buy":           sl_data["sl_buy"],
        "sl_sell":          sl_data["sl_sell"],
        "sl_distance_buy":  sl_data["sl_distance_buy"],
        "sl_distance_sell": sl_data["sl_distance_sell"],
        "validity_minutes": sl_data["validity_minutes"],
        "local_low":        sl_data["local_low"],
        "local_high":       sl_data["local_high"],
        "is_scalping":      is_scalping,
        "micro":            micro_data,
    }
