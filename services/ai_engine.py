import aiohttp
from config import GROQ_KEY, PAIRS, TIMEFRAMES

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_AR = """أنت محلل تداول متخصص في منهجية Smart Money Concepts (SMC).
تحلل حركة الأموال الكبيرة وتحدد مناطق السيولة والـ Order Blocks والـ FVG.
قواعدك:
- الدخول يكون من Order Block أو FVG القريب من السعر الحالي
- وقف الخسارة يكون تحت OB أو فوق منطقة سيولة — بعيد عن أماكن اصطياد وقوف الخسارة
- الهدف عند منطقة سيولة عكسية أو OB معاكس
- لا تدخل إذا السعر في منطقة Premium وتريد شراء، أو Discount وتريد بيع
- اكتب كل شيء بالعربية فقط"""

SYSTEM_EN = """You are a trading analyst specialized in Smart Money Concepts (SMC).
You analyze institutional money flow, liquidity zones, Order Blocks, and FVGs.
Rules:
- Entry from nearest Order Block or FVG to current price
- Stop loss below OB or above liquidity pool — away from stop hunt zones
- Target at opposing liquidity zone or OB
- Don't buy in Premium zone or sell in Discount zone
- Be concise — numbers only"""

PROMPT_AR = """بيانات SMC لزوج {pair_name} على {timeframe_name}:

السعر الحالي: {current_price}
اتجاه EMA: {ema_bias} | RSI: {rsi} | ATR: {atr}

هيكل السوق: {structure} | آخر مستوى مكسور: {last_level}
منطقة السعر: {zone} ({zone_pct}% من الـ Range)

Order Blocks صاعدة (Bullish OB): {bullish_obs}
Order Blocks هابطة (Bearish OB): {bearish_obs}

Fair Value Gaps صاعدة: {bullish_fvg}
Fair Value Gaps هابطة: {bearish_fvg}

مناطق السيولة فوق السعر (Equal Highs): {equal_highs}
مناطق السيولة تحت السعر (Equal Lows): {equal_lows}

آخر 5 شمعات: {last_candles}

بناءً على SMC، أعطني التوصية بهذا التنسيق فقط:

⚡ الإشارة: [شراء 🟢 / بيع 🔴 / انتظار ⚪]
📍 سبب الإشارة: [OB / FVG / Liquidity Sweep / CHoCH]
💰 الدخول: [سعر من OB أو FVG القريب]
🛡 وقف الخسارة: [تحت/فوق OB بعيداً عن مناطق الاصطياد]
🎯 الهدف الأول: [منطقة سيولة عكسية أو FVG]
🎯 الهدف الثاني: [OB معاكس أو سيولة أبعد]
📊 نسبة المخاطرة/المكافأة: [مثال 1:3]
💪 قوة التوصية: [ضعيفة / متوسطة / قوية / قوية جداً]
📝 الخلاصة: [جملتان بالعربية تشرح المنطق]
⚠️ تحذير: [إذا كان هناك خطر اصطياد وقف الخسارة أو سيولة في الطريق]"""

PROMPT_EN = """SMC data for {pair_name} on {timeframe_name}:

Current Price: {current_price}
EMA Bias: {ema_bias} | RSI: {rsi} | ATR: {atr}

Market Structure: {structure} | Last broken level: {last_level}
Price Zone: {zone} ({zone_pct}% of Range)

Bullish Order Blocks: {bullish_obs}
Bearish Order Blocks: {bearish_obs}

Bullish FVGs: {bullish_fvg}
Bearish FVGs: {bearish_fvg}

Buy-side Liquidity (Equal Highs): {equal_highs}
Sell-side Liquidity (Equal Lows): {equal_lows}

Last 5 candles: {last_candles}

Based on SMC, give signal in this format only:

⚡ Signal: [BUY 🟢 / SELL 🔴 / WAIT ⚪]
📍 Reason: [OB / FVG / Liquidity Sweep / CHoCH]
💰 Entry: [price from nearest OB or FVG]
🛡 Stop Loss: [below/above OB away from stop hunt zones]
🎯 TP1: [opposing liquidity or FVG]
🎯 TP2: [opposing OB or further liquidity]
📊 R/R Ratio: [e.g. 1:3]
💪 Signal Strength: [Weak / Medium / Strong / Very Strong]
📝 Summary: [2 sentences explaining the logic]
⚠️ Warning: [if there's stop hunt risk or liquidity in the way]"""


async def analyze_and_signal(pair: str, timeframe: str, indicators: dict, lang: str = "ar") -> tuple:
    pair_info = PAIRS[pair]
    tf_info   = TIMEFRAMES[timeframe]
    pair_name = pair_info["name_ar"] if lang == "ar" else f"{pair}"
    tf_name   = tf_info["label_ar"]  if lang == "ar" else tf_info["label_en"]

    smc       = indicators
    structure = smc.get("structure", {})
    pd_zone   = smc.get("premium_discount", {})
    obs       = smc.get("order_blocks", {})
    fvg       = smc.get("fvg", {})
    liq       = smc.get("liquidity", {})

    structure_labels_ar = {
        "bullish":       "صاعد (BOS صاعد)",
        "bearish":       "هابط (BOS هابط)",
        "choch_bullish": "انعكاس صاعد محتمل (CHoCH)",
        "choch_bearish": "انعكاس هابط محتمل (CHoCH)",
        "neutral":       "محايد",
    }
    structure_labels_en = {
        "bullish":       "Bullish (BOS)",
        "bearish":       "Bearish (BOS)",
        "choch_bullish": "Potential Bullish Reversal (CHoCH)",
        "choch_bearish": "Potential Bearish Reversal (CHoCH)",
        "neutral":       "Neutral",
    }
    zone_ar = "منطقة سعر مرتفع (Premium)" if pd_zone.get("zone") == "premium" else "منطقة سعر منخفض (Discount)"
    zone_en = "Premium Zone" if pd_zone.get("zone") == "premium" else "Discount Zone"

    prompt = (PROMPT_AR if lang == "ar" else PROMPT_EN).format(
        pair_name    = pair_name,
        timeframe_name = tf_name,
        current_price= smc["current_price"],
        ema_bias     = smc.get("ema_bias", "N/A"),
        rsi          = smc.get("rsi", "N/A"),
        atr          = smc.get("atr", "N/A"),
        structure    = structure_labels_ar.get(structure.get("structure","neutral"), "محايد") if lang=="ar" else structure_labels_en.get(structure.get("structure","neutral"), "Neutral"),
        last_level   = structure.get("last_level", "N/A"),
        zone         = zone_ar if lang == "ar" else zone_en,
        zone_pct     = pd_zone.get("percentage", "N/A"),
        bullish_obs  = obs.get("bullish", []),
        bearish_obs  = obs.get("bearish", []),
        bullish_fvg  = fvg.get("bullish", []),
        bearish_fvg  = fvg.get("bearish", []),
        equal_highs  = liq.get("equal_highs", []),
        equal_lows   = liq.get("equal_lows",  []),
        last_candles = smc.get("last_5_candles", []),
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

    async with aiohttp.ClientSession() as session:
        async with session.post(GROQ_URL, json=payload, headers=headers,
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
