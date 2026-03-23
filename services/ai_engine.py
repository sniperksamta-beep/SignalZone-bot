import aiohttp
from config import GROQ_KEY, PAIRS, TIMEFRAMES
from services.market_data import detect_session

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_AR = """أنت محلل تداول يقرأ الأسواق بطريقة مختلفة تماماً عن البشر العاديين.
منهجيتك: قراءة الحمض النووي للشمعات (Candle DNA) لفهم الضغط الحقيقي خلف السعر.

ما تقرأه:
- كفاءة الحركة: قريبة من 1 = حركة نظيفة قوية. منخفضة = تردد وضعف
- ضغط الشراء/البيع: مشتق من نسب الفتائل — يكشف من يتحكم فعلاً
- Delta التقديري: موجب = المشترون يضغطون، سالب = البائعون يضغطون
- الانهاك: شمعات تكبر ثم تصغر = الاتجاه على وشك الانعكاس
- Squeeze: حركة ضيقة جداً = طاقة مضغوطة ستنفجر قريباً
- الرفض: فتيل أكبر من 60% = رفض حقيقي قوي

قواعدك:
- لا تدخل ضد رفض قوي في الشمعة الأخيرة
- Squeeze + Delta قوي = دخول مثالي
- انهاك + رفض = انعكاس وشيك
- سيولة منخفضة؟ قل انتظار بلا تردد
- وقف الخسارة: ATR × 1.5 من نقطة الدخول
- الهدف: أقرب مستوى رفض تاريخي
- اكتب كل شيء بالعربية"""

SYSTEM_EN = """You are a trading analyst who reads markets differently from ordinary humans.
Your methodology: reading Candle DNA to understand the real pressure behind price.

What you read:
- Movement efficiency: close to 1 = clean strong move. Low = hesitation/weakness
- Buy/Sell pressure: derived from wick ratios — reveals who's really in control
- Estimated Delta: positive = buyers pushing, negative = sellers pushing
- Exhaustion: candles growing then shrinking = trend about to reverse
- Squeeze: very tight movement = compressed energy about to explode
- Rejection: wick > 60% of range = strong real rejection

Rules:
- Don't enter against strong rejection on last candle
- Squeeze + strong Delta = ideal entry
- Exhaustion + rejection = imminent reversal
- Low liquidity session? Say WAIT without hesitation
- Stop loss: ATR × 1.5 from entry point
- Target: nearest historical rejection level
- Be concise — numbers only"""

PROMPT_AR = """تحليل Candle DNA لزوج {pair_name} على {timeframe_name}:

السعر الحالي: {current_price} | ATR: {atr} | الاتجاه العام: {trend}
الجلسة: {session} | السيولة: {liquidity}
{session_warning}

━━ الحمض النووي للشمعة الأخيرة ━━
كفاءة الحركة: {efficiency} (1 = مثالي)
ضغط الشراء: {buy_pressure} | ضغط البيع: {sell_pressure}
Delta التقديري: {delta} (موجب = مشترون، سالب = بائعون)
نمط الرفض: {rejection}

━━ آخر 5 شمعات ━━
{candles_detail}

━━ حالة السوق ━━
زخم الشمعات: {consecutive} شمعة متتالية في نفس الاتجاه
اتساق الاتجاه: {consistency}
متوسط Delta لآخر 5 شمعات: {avg_delta}
حالة الزخم: {exhaustion}
Volatility Squeeze: {squeeze}

━━ مستويات الرفض التاريخية ━━
مقاومات مؤكدة: {resistance}
دعوم مؤكدة: {support}

بناءً على Candle DNA فقط، أعطني التوصية بهذا التنسيق:

⚡ الإشارة: [شراء 🟢 / بيع 🔴 / انتظار ⚪]
📍 المحرك: [Squeeze انفجار / رفض انعكاس / زخم قوي / انهاك / سيولة منخفضة]
💰 الدخول: [سعر قريب جداً من {current_price}]
🛡 وقف الخسارة: [السعر ± {sl_distance}]
🎯 الهدف الأول: [أقرب مستوى رفض]
🎯 الهدف الثاني: [المستوى التالي]
📊 نسبة المخاطرة/المكافأة: [مثال 1:2]
💪 قوة التوصية: [ضعيفة / متوسطة / قوية / قوية جداً]
📝 القراءة: [جملة واحدة تشرح ما تقرأه من الشمعات]
⚠️ تحذير: [جملة واحدة أو لا يوجد]"""

PROMPT_EN = """Candle DNA Analysis for {pair_name} on {timeframe_name}:

Current Price: {current_price} | ATR: {atr} | Trend: {trend}
Session: {session} | Liquidity: {liquidity}
{session_warning}

━━ Last Candle DNA ━━
Movement Efficiency: {efficiency} (1 = perfect)
Buy Pressure: {buy_pressure} | Sell Pressure: {sell_pressure}
Estimated Delta: {delta} (positive = buyers, negative = sellers)
Rejection Pattern: {rejection}

━━ Last 5 Candles ━━
{candles_detail}

━━ Market State ━━
Momentum: {consecutive} consecutive candles same direction
Trend Consistency: {consistency}
Avg Delta last 5: {avg_delta}
Momentum State: {exhaustion}
Volatility Squeeze: {squeeze}

━━ Historical Rejection Levels ━━
Confirmed Resistance: {resistance}
Confirmed Support: {support}

Based on Candle DNA only, give signal in this format:

⚡ Signal: [BUY 🟢 / SELL 🔴 / WAIT ⚪]
📍 Driver: [Squeeze explosion / Rejection reversal / Strong momentum / Exhaustion / Low liquidity]
💰 Entry: [price very close to {current_price}]
🛡 Stop Loss: [price ± {sl_distance}]
🎯 TP1: [nearest rejection level]
🎯 TP2: [next level]
📊 R/R Ratio: [e.g. 1:2]
💪 Signal Strength: [Weak / Medium / Strong / Very Strong]
📝 Reading: [one sentence explaining what you read from the candles]
⚠️ Warning: [one sentence or N/A]"""


def _format_candles(candles: list, lang: str) -> str:
    lines = []
    for c in candles:
        if lang == "ar":
            lines.append(
                f"{c['direction']} كفاءة:{c['efficiency']} شراء:{c['buy_pressure']} بيع:{c['sell_pressure']} | {c['open']}←{c['close']}"
            )
        else:
            lines.append(
                f"{c['direction']} eff:{c['efficiency']} buy:{c['buy_pressure']} sell:{c['sell_pressure']} | {c['open']}→{c['close']}"
            )
    return "\n".join(lines)


async def analyze_and_signal(pair: str, timeframe: str, indicators: dict, lang: str = "ar") -> tuple:
    pair_info = PAIRS[pair]
    tf_info   = TIMEFRAMES[timeframe]
    pair_name = pair_info["name_ar"] if lang == "ar" else f"{pair}"
    tf_name   = tf_info["label_ar"]  if lang == "ar" else tf_info["label_en"]

    dna     = indicators.get("dna", {})
    levels  = indicators.get("levels", {})
    session = detect_session(timeframe)

    atr         = indicators.get("atr", 0)
    sl_distance = round(atr * 1.5, 5)

    rejection_ar = {
        "bearish_rejection": "رفض هابط قوي (فتيل علوي ضخم)",
        "bullish_rejection": "رفض صاعد قوي (فتيل سفلي ضخم)",
        None:                "لا يوجد رفض واضح",
    }
    rejection_en = {
        "bearish_rejection": "Strong bearish rejection (large upper wick)",
        "bullish_rejection": "Strong bullish rejection (large lower wick)",
        None:                "No clear rejection",
    }
    exhaustion_ar = {
        "expanding": "تمدد — زخم يتسارع",
        "exhausting": "انهاك — الزخم يضعف",
        "normal":    "طبيعي",
    }
    exhaustion_en = {
        "expanding": "Expanding — momentum accelerating",
        "exhausting": "Exhausting — momentum weakening",
        "normal":    "Normal",
    }

    squeeze_ar = f"نعم 🔥 (نسبة {dna.get('squeeze_ratio','N/A')} — انفجار وشيك)" if dna.get("is_squeeze") else f"لا (نسبة {dna.get('squeeze_ratio','N/A')})"
    squeeze_en = f"YES 🔥 (ratio {dna.get('squeeze_ratio','N/A')} — explosion imminent)" if dna.get("is_squeeze") else f"No (ratio {dna.get('squeeze_ratio','N/A')})"

    candles_detail  = _format_candles(dna.get("last_5_candles", []), lang)
    session_warning = session.get("warning") or ""

    prompt = (PROMPT_AR if lang == "ar" else PROMPT_EN).format(
        pair_name      = pair_name,
        timeframe_name = tf_name,
        current_price  = indicators["current_price"],
        atr            = atr,
        sl_distance    = sl_distance,
        trend          = indicators.get("trend", "N/A"),
        session        = session["session"],
        liquidity      = session["liquidity"],
        session_warning= session_warning,
        efficiency     = dna.get("last_efficiency",    "N/A"),
        buy_pressure   = dna.get("last_buy_pressure",  "N/A"),
        sell_pressure  = dna.get("last_sell_pressure", "N/A"),
        delta          = dna.get("last_delta",         "N/A"),
        rejection      = rejection_ar.get(dna.get("strong_rejection")) if lang == "ar" else rejection_en.get(dna.get("strong_rejection")),
        candles_detail = candles_detail,
        consecutive    = dna.get("consecutive_candles","N/A"),
        consistency    = dna.get("trend_consistency",  "N/A"),
        avg_delta      = dna.get("avg_delta_5",        "N/A"),
        exhaustion     = exhaustion_ar.get(dna.get("exhaustion","normal")) if lang=="ar" else exhaustion_en.get(dna.get("exhaustion","normal")),
        squeeze        = squeeze_ar if lang == "ar" else squeeze_en,
        resistance     = levels.get("resistance", []),
        support        = levels.get("support",    []),
    )

    headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": SYSTEM_AR if lang == "ar" else SYSTEM_EN},
            {"role": "user",   "content": prompt}
        ],
        "max_tokens": 500,
        "temperature": 0.2,
    }

    async with aiohttp.ClientSession() as session_http:
        async with session_http.post(GROQ_URL, json=payload, headers=headers,
                                     timeout=aiohttp.ClientTimeout(total=90)) as resp:
            if resp.status != 200:
                err = await resp.text()
                raise ValueError(f"Groq error {resp.status}: {err[:200]}")
            data = await resp.json()

    result  = data["choices"][0]["message"]["content"]
    is_wait = "انتظار" in result or "WAIT" in result.upper()

    if timeframe == "5m" and not is_wait:
        note = "\n\n⚡ _تنبيه: فريم 5 دقائق سريع — ادخل فوراً_" if lang == "ar" else "\n\n⚡ _Note: 5-min frame is fast — enter immediately_"
        result += note

    return result, is_wait
