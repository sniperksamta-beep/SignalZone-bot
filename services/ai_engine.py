import aiohttp
from config import GROQ_KEY, PAIRS, TIMEFRAMES

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

MTF_MAP_AR = {
    "5m":  {"trend": "1H",    "structure": "15M", "entry": "5M"},
    "15m": {"trend": "4H",    "structure": "1H",  "entry": "15M"},
    "1h":  {"trend": "يومي",  "structure": "4H",  "entry": "1H"},
    "4h":  {"trend": "يومي",  "structure": "4H",  "entry": "4H"},
    "1d":  {"trend": "أسبوعي","structure": "يومي","entry": "يومي"},
}
MTF_MAP_EN = {
    "5m":  {"trend": "1H",    "structure": "15M", "entry": "5M"},
    "15m": {"trend": "4H",    "structure": "1H",  "entry": "15M"},
    "1h":  {"trend": "Daily", "structure": "4H",  "entry": "1H"},
    "4h":  {"trend": "Daily", "structure": "4H",  "entry": "4H"},
    "1d":  {"trend": "Weekly","structure": "Daily","entry": "Daily"},
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
    "bullish": "هيكل صاعد (HH+HL)", "bearish": "هيكل هابط (LH+LL)",
    "choch_bullish": "انعكاس صاعد (CHoCH)", "choch_bearish": "انعكاس هابط (CHoCH)",
    "neutral": "محايد",
}
STRUCTURE_EN = {
    "bullish": "Bullish (HH+HL)", "bearish": "Bearish (LH+LL)",
    "choch_bullish": "Bullish reversal (CHoCH)", "choch_bearish": "Bearish reversal (CHoCH)",
    "neutral": "Neutral",
}
MAGNET_AR = {
    "resistance_near": "قريب من المقاومة ⚠️ احذر",
    "support_near":    "قريب من الدعم 💚 فرصة",
    "pulling_to_high": "يشد نحو الأعلى ↑",
    "pulling_to_low":  "يشد نحو الأسفل ↓",
}
MAGNET_EN = {
    "resistance_near": "Near resistance ⚠️ caution",
    "support_near":    "Near support 💚 opportunity",
    "pulling_to_high": "Pulling to high ↑",
    "pulling_to_low":  "Pulling to low ↓",
}
DIVERGENCE_AR = {
    "bullish_div": "تباعد صاعد — هبوط يضعف 🔄",
    "bearish_div": "تباعد هابط — صعود يضعف 🔄",
    "none":        "لا تباعد",
}
DIVERGENCE_EN = {
    "bullish_div": "Bullish divergence — downmove weakening 🔄",
    "bearish_div": "Bearish divergence — upmove weakening 🔄",
    "none":        "No divergence",
}
ABSORPTION_AR = {
    "bullish_absorption": "امتصاص بيع 🟢 (لاعب كبير يشتري)",
    "bearish_absorption": "امتصاص شراء 🔴 (لاعب كبير يبيع)",
    "none": "لا امتصاص",
}
ABSORPTION_EN = {
    "bullish_absorption": "Buy absorption 🟢 (big player buying)",
    "bearish_absorption": "Sell absorption 🔴 (big player selling)",
    "none": "No absorption",
}
BREAKOUT_AR = {
    "bullish_breakout": "كسر صاعد لنطاق 10 شمعات ⚡",
    "bearish_breakout": "كسر هابط لنطاق 10 شمعات ⚡",
    "none": "لا كسر",
}
BREAKOUT_EN = {
    "bullish_breakout": "Bullish breakout of 10-candle range ⚡",
    "bearish_breakout": "Bearish breakout of 10-candle range ⚡",
    "none": "No breakout",
}

SYSTEM_AR = """أنت محلل تداول متخصص في Multi-Timeframe Confluence + Micro-Structure.
قواعدك:
- توافق 4+ = إشارة قوية جداً — ادخل
- توافق 3 = إشارة متوسطة — ادخل بحذر
- أقل من 3 = انتظار
- وقف الخسارة: استخدم القيم المحسوبة مسبقاً بالضبط — لا تبدّلها
- الدخول: أقرب دعم/مقاومة أو السعر الحالي مباشرة
- اكتب كل شيء بالعربية"""

SYSTEM_EN = """You are a Multi-Timeframe Confluence + Micro-Structure analyst.
Rules:
- 4+ confluence = very strong — enter
- 3 confluence = medium — enter cautiously
- Less than 3 = WAIT
- Stop loss: use pre-calculated values exactly — do not change them
- Entry: nearest support/resistance or current price directly
- Numbers only"""

PROMPT_AR = """تحليل {pair_name}:
الفريمات: {trend_tf} | {struct_tf} | {entry_tf}
السعر: {current_price} | ATR: {atr} | الجلسة: {session} ({liquidity})

━━ التوافق الرئيسي ━━
{confluence_text} ({bull_count} شراء vs {bear_count} بيع)
الاتجاه ({trend_tf}): {trend}
البنية ({struct_tf}): {structure}
RSI: {rsi} | MACD: {macd} | Squeeze: {squeeze}

━━ Micro-Structure (تحليل لحظي) ━━
{micro_section}
━━ المستويات ━━
مقاومات: {resistance}
دعوم: {support}
أعلى 10 شمعات: {range_high} | أدنى 10 شمعات: {range_low}

━━ وقف الخسارة المحسوب (استخدمه كما هو بالضبط) ━━
للشراء: {sl_buy} (المسافة: {sl_dist_buy})
للبيع: {sl_sell} (المسافة: {sl_dist_sell})
آخر قاع محلي: {local_low} | آخر قمة محلية: {local_high}

التنسيق المطلوب فقط:

⚡ الإشارة: [شراء 🟢 / بيع 🔴 / انتظار ⚪]
📊 التوافق: [{bull_count} شراء vs {bear_count} بيع من {total}]
💰 الدخول: [سعر محدد]
🛡 إذا كانت الإشارة شراء: وقف الخسارة = {sl_buy} إذا كانت الإشارة بيع: وقف الخسارة = {sl_sell} اكتب فقط وقف الخسارة المناسب للإشارة التي ستعطيها
🎯 الهدف الأول: [سعر محدد]
🎯 الهدف الثاني: [سعر محدد]
📈 نسبة R/R: [مثال 1:2]
💪 قوة التوصية: [ضعيفة/متوسطة/قوية/قوية جداً]
📝 الملخص: [جملة واحدة — اذكر أهم إشارتين]
⚠️ تحذير: [جملة أو لا يوجد]"""

PROMPT_EN = """Analysis for {pair_name}:
TFs: {trend_tf} | {struct_tf} | {entry_tf}
Price: {current_price} | ATR: {atr} | Session: {session} ({liquidity})

━━ Main Confluence ━━
{confluence_text} ({bull_count} BUY vs {bear_count} SELL)
Trend ({trend_tf}): {trend}
Structure ({struct_tf}): {structure}
RSI: {rsi} | MACD: {macd} | Squeeze: {squeeze}

━━ Micro-Structure (live) ━━
{micro_section}
━━ Key Levels ━━
Resistance: {resistance}
Support: {support}
10-candle high: {range_high} | 10-candle low: {range_low}

━━ Pre-calculated Stop Loss (use exactly as-is) ━━
For BUY: {sl_buy} (distance: {sl_dist_buy})
For SELL: {sl_sell} (distance: {sl_dist_sell})
Last local low: {local_low} | Last local high: {local_high}

Required format only:

⚡ Signal: [BUY 🟢 / SELL 🔴 / WAIT ⚪]
📊 Confluence: [{bull_count} BUY vs {bear_count} SELL of {total}]
💰 Entry: [specific price]
🛡 Stop Loss: [BUY: {sl_buy} | SELL: {sl_sell}]
🎯 TP1: [specific price]
🎯 TP2: [specific price]
📈 R/R Ratio: [e.g. 1:2]
💪 Signal Strength: [Weak/Medium/Strong/Very Strong]
📝 Summary: [one sentence — mention 2 key signals]
⚠️ Warning: [one sentence or N/A]"""


def _build_micro_section(micro: dict, lang: str) -> str:
    if not micro:
        return ""

    if lang == "ar":
        bias_ar = {
            "strong_bullish": "ميل شراء قوي ✅✅",
            "bullish":        "ميل شراء ✅",
            "strong_bearish": "ميل بيع قوي 🔴🔴",
            "bearish":        "ميل بيع 🔴",
            "neutral":        "محايد ⚪",
        }
        return (
            f"Micro Bias: {bias_ar.get(micro['micro_bias'], '⚪')} "
            f"({micro['bull_micro']} شراء / {micro['bear_micro']} بيع)\n"
            f"مغناطيس السعر: {MAGNET_AR.get(micro['magnet'], '—')} (عند {micro['magnet_level']})\n"
            f"تباعد الزخم: {DIVERGENCE_AR.get(micro['divergence'], '—')}\n"
            f"امتصاص: {ABSORPTION_AR.get(micro['absorption'], '—')}\n"
            f"كسر نطاق: {BREAKOUT_AR.get(micro['breakout'], '—')}\n"
        )
    else:
        bias_en = {
            "strong_bullish": "Strong BUY bias ✅✅",
            "bullish":        "BUY bias ✅",
            "strong_bearish": "Strong SELL bias 🔴🔴",
            "bearish":        "SELL bias 🔴",
            "neutral":        "Neutral ⚪",
        }
        return (
            f"Micro Bias: {bias_en.get(micro['micro_bias'], '⚪')} "
            f"({micro['bull_micro']} buy / {micro['bear_micro']} sell)\n"
            f"Price Magnet: {MAGNET_EN.get(micro['magnet'], '—')} (at {micro['magnet_level']})\n"
            f"Momentum Divergence: {DIVERGENCE_EN.get(micro['divergence'], '—')}\n"
            f"Absorption: {ABSORPTION_EN.get(micro['absorption'], '—')}\n"
            f"Range Breakout: {BREAKOUT_EN.get(micro['breakout'], '—')}\n"
        )


async def analyze_and_signal(pair: str, timeframe: str, indicators: dict, lang: str = "ar") -> tuple:
    pair_info = PAIRS[pair]
    pair_name = pair_info["name_ar"] if lang == "ar" else pair_info["name_en"]
    tf_name   = {"5m":"5 دقائق","15m":"15 دقيقة","1h":"ساعة","4h":"4 ساعات","1d":"يومي"}.get(timeframe,timeframe) if lang=="ar" else {"5m":"5 Min","15m":"15 Min","1h":"1H","4h":"4H","1d":"Daily"}.get(timeframe,timeframe)
    mtf       = (MTF_MAP_AR if lang=="ar" else MTF_MAP_EN).get(timeframe, MTF_MAP_AR["1h"])

    conf_text = (CONFLUENCE_AR if lang=="ar" else CONFLUENCE_EN).get(indicators["confluence"], "⚪")
    struct    = (STRUCTURE_AR  if lang=="ar" else STRUCTURE_EN).get(indicators["structure"],   "محايد" if lang=="ar" else "Neutral")
    eq        = indicators.get("entry_quality", {})
    mom       = indicators.get("momentum", {})
    trend     = {"bullish":"صاعد 📈","bearish":"هابط 📉","neutral":"محايد"}.get(indicators["trend"],"محايد") if lang=="ar" else {"bullish":"Bullish 📈","bearish":"Bearish 📉","neutral":"Neutral"}.get(indicators["trend"],"Neutral")
    macd      = ("صاعد" if mom.get("macd")=="bullish" else "هابط") if lang=="ar" else mom.get("macd","N/A")
    squeeze   = ("نعم 🔥" if eq.get("is_squeeze") else "لا") if lang=="ar" else ("YES 🔥" if eq.get("is_squeeze") else "No")

    micro         = indicators.get("micro")
    micro_section = _build_micro_section(micro, lang)
    range_high    = micro["range_10_high"] if micro else "N/A"
    range_low     = micro["range_10_low"]  if micro else "N/A"

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
        micro_section  = micro_section,
        resistance     = indicators["resistance"],
        support        = indicators["support"],
        range_high     = range_high,
        range_low      = range_low,
        sl_buy         = indicators["sl_buy"],
        sl_sell        = indicators["sl_sell"],
        sl_dist_buy    = indicators["sl_distance_buy"],
        sl_dist_sell   = indicators["sl_distance_sell"],
        local_low      = indicators["local_low"],
        local_high     = indicators["local_high"],
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
