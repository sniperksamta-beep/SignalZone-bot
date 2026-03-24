import aiohttp
from config import GROQ_KEY, PAIRS, TIMEFRAMES

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

MTF_MAP_AR = {
    "5m":  {"trend": "1H",  "structure": "15M", "entry": "5M"},
    "15m": {"trend": "4H",  "structure": "1H",  "entry": "15M"},
    "1h":  {"trend": "يومي","structure": "4H",  "entry": "1H"},
    "4h":  {"trend": "يومي","structure": "4H",  "entry": "4H"},
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
    "strong_bullish": "توافق شراء قوي جداً ✅✅ (4-5 من 5)",
    "bullish":        "توافق شراء ✅ (3 من 5)",
    "strong_bearish": "توافق بيع قوي جداً 🔴🔴 (4-5 من 5)",
    "bearish":        "توافق بيع 🔴 (3 من 5)",
    "neutral":        "لا توافق — سوق متذبذب ⚪",
}
CONFLUENCE_EN = {
    "strong_bullish": "Strong BUY confluence ✅✅ (4-5 of 5)",
    "bullish":        "BUY confluence ✅ (3 of 5)",
    "strong_bearish": "Strong SELL confluence 🔴🔴 (4-5 of 5)",
    "bearish":        "SELL confluence 🔴 (3 of 5)",
    "neutral":        "No confluence — choppy market ⚪",
}
STRUCTURE_AR = {
    "bullish":       "هيكل صاعد (HH + HL)",
    "bearish":       "هيكل هابط (LH + LL)",
    "choch_bullish": "انعكاس صاعد (CHoCH)",
    "choch_bearish": "انعكاس هابط (CHoCH)",
    "neutral":       "محايد",
}
STRUCTURE_EN = {
    "bullish":       "Bullish structure (HH+HL)",
    "bearish":       "Bearish structure (LH+LL)",
    "choch_bullish": "Bullish reversal (CHoCH)",
    "choch_bearish": "Bearish reversal (CHoCH)",
    "neutral":       "Neutral",
}

SYSTEM_AR = """أنت محلل تداول متخصص في Multi-Timeframe Confluence.
قواعدك الصارمة:
- توافق 4-5 من 5 = إشارة قوية جداً — ادخل
- توافق 3 من 5 = إشارة متوسطة — ادخل بحذر
- توافق أقل من 3 = انتظار — لا تدخل أبداً
- الدخول عند أقرب دعم (شراء) أو مقاومة (بيع)
- وقف الخسارة للشراء: تحت أقرب دعم. للبيع: فوق أقرب مقاومة
- الهدف الأول: المستوى التالي. الثاني: المستوى بعده
- اكتب كل شيء بالعربية"""

SYSTEM_EN = """You are a trading analyst specialized in Multi-Timeframe Confluence.
Strict rules:
- 4-5 of 5 confluence = very strong signal — enter
- 3 of 5 confluence = medium signal — enter cautiously
- Less than 3 = WAIT — never enter
- Entry at nearest support (BUY) or resistance (SELL)
- Stop loss BUY: below nearest support | SELL: above nearest resistance
- TP1: next level. TP2: level after that
- Numbers only, be concise"""

PROMPT_AR = """تحليل Multi-Timeframe لزوج {pair_name}:

الفريم المطلوب: {tf_name}
الفريمات المحللة: {trend_tf} (اتجاه) | {struct_tf} (بنية) | {entry_tf} (دخول)

السعر الحالي: {current_price} | ATR: {atr}
الجلسة: {session} | السيولة: {liquidity}

━━ نتائج التوافق ━━
{confluence_text}
🟢 إشارات شراء: {bull_count}/5
🔴 إشارات بيع: {bear_count}/5

━━ تفاصيل الفريمات ━━
{trend_tf} — الاتجاه العام: {trend}
{struct_tf} — هيكل السوق: {structure}
{entry_tf} — RSI: {rsi} | MACD: {macd}
Squeeze: {squeeze} | رفض الشمعة: {rejection}

━━ المستويات المفتاحية ━━
مقاومات: {resistance}
دعوم: {support}

أعطني التوصية بهذا التنسيق فقط:

⚡ الإشارة: [شراء 🟢 / بيع 🔴 / انتظار ⚪]
📊 التوافق: [{bull_count} شراء vs {bear_count} بيع من 5]
💰 الدخول: [سعر عند أقرب دعم أو مقاومة]
🛡 وقف الخسارة: [للشراء: تحت الدعم | للبيع: فوق المقاومة — سعر محدد]
🎯 الهدف الأول: [سعر محدد]
🎯 الهدف الثاني: [سعر محدد]
📈 نسبة R/R: [مثال 1:2.5]
💪 قوة التوصية: [ضعيفة / متوسطة / قوية / قوية جداً]
📝 الملخص: [جملة واحدة أهم 2-3 مؤشرات متوافقة]
⚠️ تحذير: [جملة واحدة أو لا يوجد]"""

PROMPT_EN = """Multi-Timeframe Analysis for {pair_name}:

Requested TF: {tf_name}
Analyzed TFs: {trend_tf} (trend) | {struct_tf} (structure) | {entry_tf} (entry)

Current Price: {current_price} | ATR: {atr}
Session: {session} | Liquidity: {liquidity}

━━ Confluence Results ━━
{confluence_text}
🟢 BUY signals: {bull_count}/5
🔴 SELL signals: {bear_count}/5

━━ Timeframe Details ━━
{trend_tf} — Overall trend: {trend}
{struct_tf} — Market structure: {structure}
{entry_tf} — RSI: {rsi} | MACD: {macd}
Squeeze: {squeeze} | Candle rejection: {rejection}

━━ Key Levels ━━
Resistance: {resistance}
Support: {support}

Give signal in this format only:

⚡ Signal: [BUY 🟢 / SELL 🔴 / WAIT ⚪]
📊 Confluence: [{bull_count} BUY vs {bear_count} SELL of 5]
💰 Entry: [price at nearest support or resistance]
🛡 Stop Loss: [BUY: below support | SELL: above resistance — specific price]
🎯 TP1: [specific price]
🎯 TP2: [specific price]
📈 R/R Ratio: [e.g. 1:2.5]
💪 Signal Strength: [Weak / Medium / Strong / Very Strong]
📝 Summary: [one sentence mentioning 2-3 key confluent indicators]
⚠️ Warning: [one sentence or N/A]"""


async def analyze_and_signal(pair: str, timeframe: str, indicators: dict, lang: str = "ar") -> tuple:
    pair_info  = PAIRS[pair]
    pair_name  = pair_info["name_ar"] if lang=="ar" else pair_info["name_en"]
    tf_name    = {"5m":"5 دقائق","15m":"15 دقيقة","1h":"ساعة","4h":"4 ساعات","1d":"يومي"}.get(timeframe,timeframe) if lang=="ar" else {"5m":"5 Min","15m":"15 Min","1h":"1 Hour","4h":"4 Hours","1d":"Daily"}.get(timeframe,timeframe)
    mtf        = (MTF_MAP_AR if lang=="ar" else MTF_MAP_EN).get(timeframe, MTF_MAP_AR["1h"])
    conf_text  = (CONFLUENCE_AR if lang=="ar" else CONFLUENCE_EN).get(indicators["confluence"], "⚪")
    struct     = (STRUCTURE_AR  if lang=="ar" else STRUCTURE_EN).get(indicators["structure"], "محايد" if lang=="ar" else "Neutral")
    eq         = indicators.get("entry_quality", {})
    mom        = indicators.get("momentum", {})
    squeeze    = ("نعم 🔥" if eq.get("is_squeeze") else "لا") if lang=="ar" else ("YES 🔥" if eq.get("is_squeeze") else "No")
    rejection  = {"bullish":"رفض صاعد","bearish":"رفض هابط",None:"لا يوجد"}.get(eq.get("rejection")) if lang=="ar" else {"bullish":"Bullish rejection","bearish":"Bearish rejection",None:"None"}.get(eq.get("rejection"))
    trend      = {"bullish":"صاعد 📈","bearish":"هابط 📉","neutral":"محايد"}.get(indicators["trend"],"محايد") if lang=="ar" else {"bullish":"Bullish 📈","bearish":"Bearish 📉","neutral":"Neutral"}.get(indicators["trend"],"Neutral")
    macd       = ("صاعد" if mom.get("macd")=="bullish" else "هابط") if lang=="ar" else mom.get("macd","N/A")

    prompt = (PROMPT_AR if lang=="ar" else PROMPT_EN).format(
        pair_name      = pair_name,
        tf_name        = tf_name,
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
        trend          = trend,
        structure      = struct,
        rsi            = mom.get("rsi","N/A"),
        macd           = macd,
        squeeze        = squeeze,
        rejection      = rejection,
        resistance     = indicators["resistance"],
        support        = indicators["support"],
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
