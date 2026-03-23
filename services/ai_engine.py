"""
services/ai_engine.py
يأخذ المؤشرات التقنية الحقيقية ويولّد توصية تداول دقيقة.
"""

import json
import aiohttp
from config import GROQ_KEY, PAIRS, TIMEFRAMES

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_AR = """أنت محلل تقني محترف متخصص في أسواق الفوركس والذهب والعملات الرقمية.
تحلل البيانات التقنية الحقيقية وتعطي توصيات دقيقة بناءً على التقاطع بين عدة مؤشرات.
أهم معاييرك:
- تعطي الأولوية لنقطة الدخول القريبة من السعر الحالي (لا تعطي دخولاً بعيداً)
- وقف الخسارة يكون خلف أقرب مستوى دعم/مقاومة بهامش أمان صغير
- هدفا الربح يستندان إلى مستويات فيبوناتشي أو مقاومات/دعوم حقيقية
- تحدد قوة التوصية ونسبة المخاطرة/المكافأة
- لا تعطي توصية إذا كان السوق متذبذباً بدون اتجاه واضح"""

SYSTEM_EN = """You are a professional technical analyst specializing in forex, gold, and crypto markets.
You analyze real technical data and give precise trading signals based on confluence of multiple indicators.
Your key principles:
- Entry price must be CLOSE to current price (not far away)
- Stop loss is placed behind the nearest support/resistance with a small safety margin
- Two take profit targets based on real fibonacci levels or S&R zones
- You specify signal strength and risk/reward ratio
- You do NOT give a signal if the market is ranging/choppy without clear direction"""

PROMPT_AR = """حلل البيانات التقنية التالية لزوج {pair_name} على إطار {timeframe_name}:

{data}

بناءً على هذه البيانات، قدّم توصية تداول بالتنسيق التالي بالضبط:

🔍 **التحليل:**
[3-5 جمل تشرح ما تراه في المؤشرات — اذكر الأرقام الحقيقية من البيانات]

📊 **التقاطعات:**
[اذكر المؤشرات التي تتفق على نفس الاتجاه]

⚡ **الإشارة:** BUY أو SELL أو WAIT (إذا لا توجد فرصة واضحة)

💰 **نقطة الدخول:** [سعر قريب من الحالي مع شرح]
🛡️ **وقف الخسارة:** [سعر + عدد النقاط/البيبس]
🎯 **هدف الربح 1:** [سعر + عدد النقاط/البيبس]
🎯 **هدف الربح 2:** [سعر + عدد النقاط/البيبس]

📈 **نسبة المخاطرة/المكافأة:** [مثال 1:2.5]
💪 **قوة التوصية:** [ضعيفة / متوسطة / قوية / قوية جداً]
⚠️ **تحذير:** [أي ملاحظات مهمة]"""

PROMPT_EN = """Analyze the following technical data for {pair_name} on {timeframe_name} timeframe:

{data}

Based on this data, provide a trading signal in this EXACT format:

🔍 **Analysis:**
[3-5 sentences explaining what you see in the indicators — mention real numbers from data]

📊 **Confluences:**
[List the indicators that agree on the same direction]

⚡ **Signal:** BUY or SELL or WAIT (if no clear opportunity)

💰 **Entry Price:** [Price close to current with explanation]
🛡️ **Stop Loss:** [Price + pips/points]
🎯 **Take Profit 1:** [Price + pips/points]
🎯 **Take Profit 2:** [Price + pips/points]

📈 **Risk/Reward Ratio:** [Example 1:2.5]
💪 **Signal Strength:** [Weak / Medium / Strong / Very Strong]
⚠️ **Warning:** [Any important notes]"""


async def analyze_and_signal(pair: str, timeframe: str, indicators: dict, lang: str = "ar") -> str:
    """
    يأخذ نتائج المؤشرات ويولّد توصية تداول.
    """
    pair_info = PAIRS[pair]
    tf_info   = TIMEFRAMES[timeframe]

    pair_name = pair_info["name_ar"] if lang == "ar" else f"{pair}"
    tf_name   = tf_info["label_ar"]  if lang == "ar" else tf_info["label_en"]

    # نظّف البيانات للـ prompt
    data_str = json.dumps(indicators, ensure_ascii=False, indent=2)

    system = SYSTEM_AR if lang == "ar" else SYSTEM_EN
    prompt = (PROMPT_AR if lang == "ar" else PROMPT_EN).format(
        pair_name=pair_name,
        timeframe_name=tf_name,
        data=data_str
    )

    headers = {
        "Authorization": f"Bearer {GROQ_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt}
        ],
        "max_tokens": 1500,
        "temperature": 0.3,  # منخفض لتوصيات أكثر دقة واتساقاً
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            GROQ_URL, json=payload, headers=headers,
            timeout=aiohttp.ClientTimeout(total=90)
        ) as resp:
            if resp.status != 200:
                err = await resp.text()
                raise ValueError(f"Groq error {resp.status}: {err[:200]}")
            data = await resp.json()

    return data["choices"][0]["message"]["content"]
