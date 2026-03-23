import json
import aiohttp
from config import GROQ_KEY, PAIRS, TIMEFRAMES

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_AR = """أنت محلل تقني محترف. تعطي توصيات تداول مختصرة ودقيقة.
قواعدك الصارمة:
- نقطة الدخول يجب أن تكون قريبة جداً من السعر الحالي (فرق لا يتجاوز 0.3% للفوركس، 0.5% للذهب، 1% للكريبتو)
- إذا لم يكن هناك فرصة واضحة قل WAIT بوضوح
- لا تكتب شروحات طويلة — فقط الأرقام والمعلومات الضرورية"""

SYSTEM_EN = """You are a professional technical analyst. You give concise, precise trading signals.
Strict rules:
- Entry must be very close to current price (max 0.3% diff for forex, 0.5% for gold, 1% for crypto)
- If no clear opportunity, say WAIT clearly
- No long explanations — only numbers and essential info"""

PROMPT_AR = """بيانات {pair_name} على {timeframe_name}:
السعر الحالي: {current_price}
RSI: {rsi} | MACD: {macd_cross} | EMA: {ema_trend}
Stoch K/D: {stoch_k}/{stoch_d}
BB: {bb_lower} / {bb_mid} / {bb_upper}
ATR: {atr}
دعم: {supports}
مقاومة: {resistances}
فيبوناتشي 0.382: {fib382} | 0.618: {fib618}
آخر 5 شمعات: {last_candles}

أعطني التوصية بهذا التنسيق فقط — لا تضف أي نص خارجه:

⚡ الإشارة: [BUY 🟢 / SELL 🔴 / WAIT ⚪]
💰 الدخول: [سعر قريب من {current_price}]
🛡 وقف الخسارة: [سعر]
🎯 هدف 1: [سعر]
🎯 هدف 2: [سعر]
📊 نسبة R/R: [مثال 1:2.5]
💪 قوة التوصية: [ضعيفة / متوسطة / قوية / قوية جداً]
📝 السبب: [جملة واحدة فقط تذكر أهم مؤشرين]
⚠️ تحذير: [جملة واحدة إن وجد]"""

PROMPT_EN = """Data for {pair_name} on {timeframe_name}:
Current Price: {current_price}
RSI: {rsi} | MACD: {macd_cross} | EMA: {ema_trend}
Stoch K/D: {stoch_k}/{stoch_d}
BB: {bb_lower} / {bb_mid} / {bb_upper}
ATR: {atr}
Support: {supports}
Resistance: {resistances}
Fib 0.382: {fib382} | 0.618: {fib618}
Last 5 candles: {last_candles}

Give the signal in this format ONLY — no extra text:

⚡ Signal: [BUY 🟢 / SELL 🔴 / WAIT ⚪]
💰 Entry: [price close to {current_price}]
🛡 Stop Loss: [price]
🎯 TP1: [price]
🎯 TP2: [price]
📊 R/R Ratio: [e.g. 1:2.5]
💪 Signal Strength: [Weak / Medium / Strong / Very Strong]
📝 Reason: [one sentence mentioning the 2 main indicators]
⚠️ Warning: [one sentence if any]"""


async def analyze_and_signal(pair: str, timeframe: str, indicators: dict, lang: str = "ar") -> str:
    pair_info = PAIRS[pair]
    tf_info   = TIMEFRAMES[timeframe]
    pair_name = pair_info["name_ar"] if lang == "ar" else f"{pair}"
    tf_name   = tf_info["label_ar"]  if lang == "ar" else tf_info["label_en"]
    fib       = indicators.get("fibonacci", {})

    prompt = (PROMPT_AR if lang == "ar" else PROMPT_EN).format(
        pair_name     = pair_name,
        timeframe_name= tf_name,
        current_price = indicators["current_price"],
        rsi           = indicators.get("rsi", "N/A"),
        macd_cross    = indicators.get("macd_cross", "N/A"),
        ema_trend     = indicators.get("ema_trend", "N/A"),
        stoch_k       = indicators.get("stoch_k", "N/A"),
        stoch_d       = indicators.get("stoch_d", "N/A"),
        bb_lower      = indicators.get("bb_lower", "N/A"),
        bb_mid        = indicators.get("bb_mid",   "N/A"),
        bb_upper      = indicators.get("bb_upper", "N/A"),
        atr           = indicators.get("atr", "N/A"),
        supports      = indicators.get("supports", []),
        resistances   = indicators.get("resistances", []),
        fib382        = fib.get("0.382", "N/A"),
        fib618        = fib.get("0.618", "N/A"),
        last_candles  = indicators.get("last_5_candles", []),
    )

    headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": SYSTEM_AR if lang == "ar" else SYSTEM_EN},
            {"role": "user",   "content": prompt}
        ],
        "max_tokens": 400,
        "temperature": 0.2,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(GROQ_URL, json=payload, headers=headers,
                                timeout=aiohttp.ClientTimeout(total=90)) as resp:
            if resp.status != 200:
                err = await resp.text()
                raise ValueError(f"Groq error {resp.status}: {err[:200]}")
            data = await resp.json()

    return data["choices"][0]["message"]["content"]
