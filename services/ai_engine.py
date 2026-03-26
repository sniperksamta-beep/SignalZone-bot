import aiohttp
from config import GROQ_KEY, PAIRS, TIMEFRAMES

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

MTF_MAP_AR = {
    "5m":  {"trend": "1H",   "structure": "15M", "entry": "5M"},
    "15m": {"trend": "4H",   "structure": "1H",  "entry": "15M"},
    "1h":  {"trend": "يومي", "structure": "4H",  "entry": "1H"},
    "4h":  {"trend": "يومي", "structure": "4H",  "entry": "4H"},
    "1d":  {"trend": "أسبوعي","structure":"يومي","entry": "يومي"},
}
MTF_MAP_EN = {
    "5m":  {"trend": "1H",    "structure": "15M", "entry": "5M"},
    "15m": {"trend": "4H",    "structure": "1H",  "entry": "15M"},
    "1h":  {"trend": "Daily", "structure": "4H",  "entry": "1H"},
    "4h":  {"trend": "Daily", "structure": "4H",  "entry": "4H"},
    "1d":  {"trend": "Weekly","structure":"Daily","entry": "Daily"},
}

CONFLUENCE_AR = {
    "strong_bullish": "توافق شراء قوي جداً ✅✅",
    "bullish":        "توافق شراء ✅",
    "strong_bearish": "توافق بيع قوي جداً 🔴🔴",
    "bearish":        "توافق بيع 🔴",
    "neutral":        "لا توافق ⚪",
}
CONFLUENCE_EN = {
    "strong_bullish": "Strong BUY confluence ✅✅",
    "bullish":        "BUY confluence ✅",
    "strong_bearish": "Strong SELL confluence 🔴🔴",
    "bearish":        "SELL confluence 🔴",
    "neutral":        "No confluence ⚪",
}
STRUCTURE_AR = {
    "bullish":       "هيكل صاعد (HH+HL)",
    "bearish":       "هيكل هابط (LH+LL)",
    "choch_bullish": "انعكاس صاعد (CHoCH)",
    "choch_bearish": "انعكاس هابط (CHoCH)",
    "neutral":       "محايد",
}
STRUCTURE_EN = {
    "bullish":       "Bullish (HH+HL)",
    "bearish":       "Bearish (LH+LL)",
    "choch_bullish": "Bullish reversal (CHoCH)",
    "choch_bearish": "Bearish reversal (CHoCH)",
    "neutral":       "Neutral",
}
PATTERN_AR = {
    "bullish_engulfing": "ابتلاع صاعد 🟢🟢",
    "bearish_engulfing": "ابتلاع هابط 🔴🔴",
    "bullish_pin_bar":   "Pin Bar صاعد (مطرقة) 🟢",
    "bearish_pin_bar":   "Pin Bar هابط (نجمة) 🔴",
    "inside_bar":        "Inside Bar — ضغط قبل انفجار ⚡",
    "doji":              "Doji — تردد في لحظة قرار ⚖️",
    "none":              "لا نمط واضح",
}
PATTERN_EN = {
    "bullish_engulfing": "Bullish Engulfing 🟢🟢",
    "bearish_engulfing": "Bearish Engulfing 🔴🔴",
    "bullish_pin_bar":   "Bullish Pin Bar (Hammer) 🟢",
    "bearish_pin_bar":   "Bearish Pin Bar (Shooting Star) 🔴",
    "inside_bar":        "Inside Bar — pressure before explosion ⚡",
    "doji":              "Doji — decision moment ⚖️",
    "none":              "No clear pattern",
}

SYSTEM_AR = """أنت محلل تداول متخصص في Multi-Timeframe Confluence.
قواعدك الصارمة:
- توافق 4+ من 5 (أو 6 للفريمات الصغيرة) = إشارة قوية جداً
- توافق 3 = إشارة متوسطة
- أقل من 3 = انتظار — لا تدخل
- وقف الخسارة: استخدم القيم المحسوبة بدقة المُمررة إليك — لا تغيرها
- الدخول: أقرب دعم (شراء) أو مقاومة (بيع) أو السعر الحالي مباشرة
- اكتب كل شيء بالعربية"""

SYSTEM_EN = """You are a Multi-Timeframe Confluence trading analyst.
Strict rules:
- 4+ of 5 (or 6 for small TFs) confluence = very strong signal
- 3 confluence = medium signal
- Less than 3 = WAIT
- Stop loss: use the pre-calculated values provided — do not change them
- Entry: nearest support (BUY) or resistance (SELL) or current price directly
- Numbers only, be concise"""

PROMPT_AR = """تحليل Multi-Timeframe لزوج {pair_name}:
الفريمات: {trend_tf} اتجاه | {struct_tf} بنية | {entry_tf} دخول

السعر الحالي: {current_price} | ATR: {atr}
الجلسة: {session} | السيولة: {liquidity}

━━ التوافق ({bull_count}/{total} شراء) ━━
{confluence_text}

━━ التحليل ━━
الاتجاه ({trend_tf}): {trend}
البنية ({struct_tf}): {structure}
RSI: {rsi} | MACD: {macd}
Squeeze: {squeeze}
{scalping_section}
━━ المستويات ━━
مقاومات: {resistance}
دعوم: {support}

━━ وقف الخسارة المحسوب (استخدمه كما هو) ━━
للشراء: {sl_buy} (مسافة: {sl_dist_buy} نقطة)
للبيع: {sl_sell} (مسافة: {sl_dist_sell} نقطة)

التنسيق المطلوب فقط:

⚡ الإشارة: [شراء 🟢 / بيع 🔴 / انتظار ⚪]
📊 التوافق: [{bull_count} شراء vs {bear_count} بيع]
💰 الدخول: [سعر محدد]
🛡 وقف الخسارة: [للشراء: {sl_buy} | للبيع: {sl_sell}]
🎯 الهدف الأول: [سعر محدد]
🎯 الهدف الثاني: [سعر محدد]
📈 نسبة R/R: [مثال 1:2]
💪 قوة التوصية: [ضعيفة/متوسطة/قوية/قوية جداً]
📝 الملخص: [جملة واحدة]
⚠️ تحذير: [جملة واحدة أو لا يوجد]"""

PROMPT_EN = """Multi-Timeframe Analysis for {pair_name}:
Timeframes: {trend_tf} trend | {struct_tf} structure | {entry_tf} entry

Current Price: {current_price} | ATR: {atr}
Session: {session} | Liquidity: {liquidity}

━━ Confluence ({bull_count}/{total} BUY) ━━
{confluence_text}

━━ Analysis ━━
Trend ({trend_tf}): {trend}
Structure ({struct_tf}): {structure}
RSI: {rsi} | MACD: {macd}
Squeeze: {squeeze}
{scalping_section}
━━ Key Levels ━━
Resistance: {resistance}
Support: {support}

━━ Pre-calculated Stop Loss (use as-is) ━━
For BUY: {sl_buy} (distance: {sl_dist_buy} pts)
For SELL: {sl_sell} (distance: {sl_dist_sell} pts)

Required format only:

⚡ Signal: [BUY 🟢 / SELL 🔴 / WAIT ⚪]
📊 Confluence: [{bull_count} BUY vs {bear_count} SELL]
💰 Entry: [specific price]
🛡 Stop Loss: [BUY: {sl_buy} | SELL: {sl_sell}]
🎯 TP1: [specific price]
🎯 TP2: [specific price]
📈 R/R Ratio: [e.g. 1:2]
💪 Signal Strength: [Weak/Medium/Strong/Very Strong]
📝 Summary: [one sentence]
⚠️ Warning: [one sentence or N/A]"""


async def analyze_and_signal(pair: str, timeframe: str, indicators: dict, lang: str = "ar") -> tuple:
    pair_info  = PAIRS[pair]
    pair_name  = pair_info["name_ar"] if lang=="ar" else pair_info["name_en"]
    tf_name    = {"5m":"5 دقائق","15m":"15 دقيقة","1h":"ساعة","4h":"4 ساعات","1d":"يومي"}.get(timeframe,timeframe) if lang=="ar" else {"5m":"5 Min","15m":"15 Min","1h":"1H","4h":"4H","1d":"Daily"}.get(timeframe,timeframe)
    mtf        = (MTF_MAP_AR if lang=="ar" else MTF_MAP_EN).get(timeframe, MTF_MAP_AR["1h"])

    conf_text  = (CONFLUENCE_AR if lang=="ar" else CONFLUENCE_EN).get(indicators["confluence"], "⚪")
    struct     = (STRUCTURE_AR  if lang=="ar" else STRUCTURE_EN).get(indicators["structure"],  "محايد" if lang=="ar" else "Neutral")
    eq         = indicators.get("entry_quality", {})
    mom        = indicators.get("momentum", {})
    trend      = {"bullish":"صاعد 📈","bearish":"هابط 📉","neutral":"محايد"}.get(indicators["trend"],"محايد") if lang=="ar" else {"bullish":"Bullish 📈","bearish":"Bearish 📉","neutral":"Neutral"}.get(indicators["trend"],"Neutral")
    macd       = ("صاعد" if mom.get("macd")=="bullish" else "هابط") if lang=="ar" else mom.get("macd","N/A")
    squeeze    = ("نعم 🔥" if eq.get("is_squeeze") else "لا") if lang=="ar" else ("YES 🔥" if eq.get("is_squeeze") else "No")

    # قسم المضاربة
    scalping   = indicators.get("scalping")
    if scalping and lang == "ar":
        pattern      = (PATTERN_AR if lang=="ar" else PATTERN_EN).get(scalping.get("candle_pattern","none"), "لا نمط")
        vel          = scalping.get("velocity", {})
        scalping_section = (
            f"━━ طبقة المضاربة (Scalping) ━━\n"
            f"نمط الشمعة: {pattern}\n"
            f"سرعة الحركة: {vel.get('velocity_ratio','N/A')}x المتوسط"
            f"{' ⚡ تسارع!' if vel.get('is_accelerating') else ''}\n"
            f"اتجاه الزخم: {'صاعد' if vel.get('momentum_direction')=='bullish' else 'هابط'}\n"
        )
    elif scalping and lang == "en":
        pattern      = PATTERN_EN.get(scalping.get("candle_pattern","none"), "No pattern")
        vel          = scalping.get("velocity", {})
        scalping_section = (
            f"━━ Scalping Layer ━━\n"
            f"Candle Pattern: {pattern}\n"
            f"Price Velocity: {vel.get('velocity_ratio','N/A')}x avg"
            f"{' ⚡ Accelerating!' if vel.get('is_accelerating') else ''}\n"
            f"Momentum: {vel.get('momentum_direction','N/A')}\n"
        )
    else:
        scalping_section = ""

    total = indicators["bull_count"] + indicators["bear_count"]

    prompt = (PROMPT_AR if lang=="ar" else PROMPT_EN).format(
        pair_name      = pair_name,
        trend_tf       = mtf["trend"],
        struct_tf      = mtf["structure"],
        entry_tf       = mtf["entry"],
        current_price  = indicators["current_price"],
        atr            = indicators["atr"],
        session        = indicators["session"],
        liquidity      = indicators["liquidity"],
        confluence_text= conf_text,
        bull_count     = indicators["bull_count"],
        bear_count     = indicators["bear_count"],
        total          = total,
        trend          = trend,
        structure      = struct,
        rsi            = mom.get("rsi","N/A"),
        macd           = macd,
        squeeze        = squeeze,
        scalping_section=scalping_section,
        resistance     = indicators["resistance"],
        support        = indicators["support"],
        sl_buy         = indicators["sl_buy"],
        sl_sell        = indicators["sl_sell"],
        sl_dist_buy    = indicators["sl_distance_buy"],
        sl_dist_sell   = indicators["sl_distance_sell"],
    )

    headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": SYSTEM_AR if lang=="ar" else SYSTEM_EN},
            {"role": "user",   "content": prompt}
        ],
        "max_tokens": 500,
        "temperature": 0.2,
    }

    async with aiohttp.ClientSession() as s:
        async with s.post(GROQ_URL, json=payload, headers=headers,
                          timeout=aiohttp.ClientTimeout(total=90)) as resp:
            if resp.status != 200:
                err = await resp.text()
                raise ValueError(f"Groq error {resp.status}: {err[:200]}")
            data = await resp.json()

    result  = data["choices"][0]["message"]["content"]
    is_wait = "انتظار" in result or "WAIT" in result.upper() or indicators["confluence"] == "neutral"

    return result, is_wait
