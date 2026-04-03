"""
ai_engine.py — Signal Formatter
================================

KEY CHANGE: The scoring engine in market_data.py already decided BUY/SELL/WAIT
with a mathematical confidence score. The AI here ONLY formats the output
into a clean, readable signal. It does NOT decide the direction.
"""

import aiohttp
from config import GROQ_KEY

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

MTF_MAP_AR = {
    "5m":  {"trend": "1H", "structure": "15M", "entry": "5M"},
    "15m": {"trend": "4H", "structure": "1H",  "entry": "15M"},
    "1h":  {"trend": "يومي", "structure": "4H", "entry": "1H"},
    "4h":  {"trend": "يومي", "structure": "4H", "entry": "4H"},
    "1d":  {"trend": "أسبوعي", "structure": "يومي", "entry": "يومي"},
}
MTF_MAP_EN = {
    "5m":  {"trend": "1H", "structure": "15M", "entry": "5M"},
    "15m": {"trend": "4H", "structure": "1H",  "entry": "15M"},
    "1h":  {"trend": "Daily", "structure": "4H", "entry": "1H"},
    "4h":  {"trend": "Daily", "structure": "4H", "entry": "4H"},
    "1d":  {"trend": "Weekly", "structure": "Daily", "entry": "Daily"},
}


def _format_signal_ar(pair_name, timeframe, indicators):
    """Format the signal output in Arabic — decision already made by math."""
    sig = indicators["signal"]
    trade = indicators["trade"]
    mtf = MTF_MAP_AR.get(timeframe, MTF_MAP_AR["1h"])

    direction = sig["direction"]
    score = sig["score"]
    strength = sig["strength"]

    if direction == "BUY":
        dir_text = "شراء 🟢"
        dir_emoji = "🟢"
    elif direction == "SELL":
        dir_text = "بيع 🔴"
        dir_emoji = "🔴"
    else:
        dir_text = "انتظار ⚪"
        dir_emoji = "⚪"

    strength_ar = {
        "VERY_STRONG": "قوية جداً 💪💪",
        "STRONG": "قوية 💪",
        "MODERATE": "متوسطة ⚡",
        "WEAK": "ضعيفة ⚠️",
    }.get(strength, "—")

    trend_ar = {"bullish": "صاعد 📈", "bearish": "هابط 📉", "neutral": "محايد ↔️"}.get(indicators["trend"], "—")
    struct_ar = {"bullish": "صاعد (HH+HL)", "bearish": "هابط (LH+LL)",
                 "choch_bullish": "انعكاس صاعد (CHoCH)", "choch_bearish": "انعكاس هابط (CHoCH)",
                 "neutral": "محايد"}.get(indicators["structure"], "—")
    macd_ar = "صاعد" if indicators["macd_direction"] == "bullish" else "هابط"
    session_ar = {"London": "لندن 🇬🇧", "London-NY Overlap": "تداخل لندن-نيويورك 🔥",
                  "New York": "نيويورك 🇺🇸", "Asia": "آسيا 🌏",
                  "Late NY / Early Asia": "آسيا المبكرة 🌙"}.get(indicators["session"], indicators["session"])

    # Build the top scoring indicators
    bd = indicators.get("score_breakdown", [])
    top_signals = [b for b in bd if "→ +" in b and float(b.split("+")[-1]) > 3][:5]

    # Volume text
    vol = indicators["volume"]
    vol_text = {"bullish": f"شرائي x{vol['vol_ratio']}", "bearish": f"بيعي x{vol['vol_ratio']}",
                "drying_up": "يجف ⚠️", "neutral": f"عادي x{vol['vol_ratio']}"}.get(vol["vol_confirm"], "—")

    # Divergence
    div = indicators["divergence"]
    div_text = "لا يوجد"
    if div["regular"] == "bullish": div_text = "تباعد صاعد 🔄"
    elif div["regular"] == "bearish": div_text = "تباعد هابط 🔄"
    elif div["hidden"] == "bullish": div_text = "تباعد خفي صاعد"
    elif div["hidden"] == "bearish": div_text = "تباعد خفي هابط"

    # Sweep
    sweep = indicators["liquidity_sweep"]
    sweep_text = ""
    if sweep["bullish_sweep"]: sweep_text = "مسح سيولة صاعد 🎯"
    elif sweep["bearish_sweep"]: sweep_text = "مسح سيولة هابط 🎯"

    # Patterns
    pat_texts = []
    for name, _ in indicators.get("candle_patterns", []):
        pat_map = {"bullish_engulfing": "ابتلاع صاعد", "bearish_engulfing": "ابتلاع هابط",
                   "bullish_pin_bar": "بن بار صاعد", "bearish_pin_bar": "بن بار هابط",
                   "morning_star": "نجمة الصباح", "evening_star": "نجمة المساء",
                   "three_white_soldiers": "3 جنود بيض", "three_black_crows": "3 غربان سود"}
        pat_texts.append(pat_map.get(name, name))

    chop_text = "متذبذب ⚠️" if indicators["choppiness"] > 61.8 else ("متجه ✅" if indicators["choppiness"] < 38.2 else "متوسط")

    result = f"""⚡ الإشارة: {dir_text}
📊 الثقة: {score}/100 ({strength_ar})
📈 الاتجاه ({mtf['trend']}): {trend_ar} ({indicators['trend_strength']:.0%})
🏗 البنية ({mtf['structure']}): {struct_ar}

━━ المؤشرات ━━
RSI: {indicators['rsi']} | StochRSI: K={indicators['stoch_k']:.0f} D={indicators['stoch_d']:.0f}
MACD: {macd_ar} | ADX: {indicators['adx']:.0f} (+DI={indicators['plus_di']:.0f} -DI={indicators['minus_di']:.0f})
EMA: 9={'فوق' if indicators['ema9'] > indicators['ema21'] else 'تحت'} 21 | BB: {indicators['bb_position']}
الزخم: {chop_text} (CI={indicators['choppiness']:.0f})
الحجم: {vol_text}"""

    if indicators.get("vwap"):
        result += f"\nVWAP: {indicators['vwap']}"

    result += f"""

━━ التحليل الذكي ━━
التباعد: {div_text}
أوامر مؤسسية: {indicators['bull_order_blocks']} شرائي / {indicators['bear_order_blocks']} بيعي"""

    if sweep_text:
        result += f"\n{sweep_text}"
    if pat_texts:
        result += f"\nنماذج: {', '.join(pat_texts)}"

    if direction != "WAIT":
        res_text = " | ".join([str(r) for r in indicators["resistance"][:3]]) if indicators["resistance"] else "—"
        sup_text = " | ".join([str(s) for s in indicators["support"][:3]]) if indicators["support"] else "—"
        result += f"""

━━ مستويات التداول ━━
💰 الدخول: {trade['entry']}
🛡 وقف الخسارة: {trade['sl']} ({trade['sl_dist']} نقطة)
🎯 الهدف الأول: {trade['tp1']}
🎯 الهدف الثاني: {trade['tp2']}
📈 نسبة R/R: {trade['rr_ratio']}

مقاومات: {res_text}
دعوم: {sup_text}"""

    result += f"""

━━ ملخص القرار ━━
الجلسة: {session_ar} ({indicators['liquidity']})"""

    if direction == "WAIT":
        result += "\n⏳ لا توجد إشارة واضحة — الشروط غير مكتملة. انتظر فرصة أفضل."
    elif score >= 90:
        result += f"\n✅ إشارة {dir_text} قوية جداً — {len([b for b in bd if '→ +' in b])} عوامل متوافقة."
    elif score >= 75:
        result += f"\n✅ إشارة {dir_text} قوية — ادخل بثقة."
    else:
        result += f"\n⚡ إشارة {dir_text} متوسطة — ادخل بحذر مع وقف خسارة محكم."

    # Warnings
    warnings = []
    if indicators["choppiness"] > 61.8: warnings.append("سوق متذبذب")
    if indicators["adx"] < 20: warnings.append("اتجاه ضعيف")
    if indicators["session_mult"] < 0.8: warnings.append("سيولة منخفضة")
    if sig["direction"] == "BUY" and indicators["trend"] == "bearish": warnings.append("عكس الاتجاه")
    if sig["direction"] == "SELL" and indicators["trend"] == "bullish": warnings.append("عكس الاتجاه")
    if warnings:
        result += f"\n⚠️ تحذير: {' | '.join(warnings)}"

    return result


def _format_signal_en(pair_name, timeframe, indicators):
    """Format the signal output in English — decision already made by math."""
    sig = indicators["signal"]
    trade = indicators["trade"]
    mtf = MTF_MAP_EN.get(timeframe, MTF_MAP_EN["1h"])

    direction = sig["direction"]
    score = sig["score"]
    strength = sig["strength"]

    if direction == "BUY":    dir_text = "BUY 🟢"
    elif direction == "SELL": dir_text = "SELL 🔴"
    else:                     dir_text = "WAIT ⚪"

    strength_en = {"VERY_STRONG": "Very Strong 💪💪", "STRONG": "Strong 💪",
                   "MODERATE": "Moderate ⚡", "WEAK": "Weak ⚠️"}.get(strength, "—")
    trend_en = {"bullish": "Bullish 📈", "bearish": "Bearish 📉", "neutral": "Neutral ↔️"}.get(indicators["trend"], "—")
    struct_en = {"bullish": "Bullish (HH+HL)", "bearish": "Bearish (LH+LL)",
                 "choch_bullish": "Bullish reversal (CHoCH)", "choch_bearish": "Bearish reversal (CHoCH)",
                 "neutral": "Neutral"}.get(indicators["structure"], "—")
    macd_en = "Bullish" if indicators["macd_direction"] == "bullish" else "Bearish"

    vol = indicators["volume"]
    vol_text = {"bullish": f"Bullish x{vol['vol_ratio']}", "bearish": f"Bearish x{vol['vol_ratio']}",
                "drying_up": "Drying up ⚠️", "neutral": f"Normal x{vol['vol_ratio']}"}.get(vol["vol_confirm"], "—")

    div = indicators["divergence"]
    div_text = "None"
    if div["regular"] == "bullish": div_text = "Regular bullish 🔄"
    elif div["regular"] == "bearish": div_text = "Regular bearish 🔄"
    elif div["hidden"] == "bullish": div_text = "Hidden bullish"
    elif div["hidden"] == "bearish": div_text = "Hidden bearish"

    sweep = indicators["liquidity_sweep"]
    sweep_text = ""
    if sweep["bullish_sweep"]: sweep_text = "Bullish liquidity sweep 🎯"
    elif sweep["bearish_sweep"]: sweep_text = "Bearish liquidity sweep 🎯"

    pat_texts = [name.replace("_", " ").title() for name, _ in indicators.get("candle_patterns", [])]

    chop_text = "Choppy ⚠️" if indicators["choppiness"] > 61.8 else ("Trending ✅" if indicators["choppiness"] < 38.2 else "Mixed")

    bd = indicators.get("score_breakdown", [])

    result = f"""⚡ Signal: {dir_text}
📊 Confidence: {score}/100 ({strength_en})
📈 Trend ({mtf['trend']}): {trend_en} ({indicators['trend_strength']:.0%})
🏗 Structure ({mtf['structure']}): {struct_en}

━━ Indicators ━━
RSI: {indicators['rsi']} | StochRSI: K={indicators['stoch_k']:.0f} D={indicators['stoch_d']:.0f}
MACD: {macd_en} | ADX: {indicators['adx']:.0f} (+DI={indicators['plus_di']:.0f} -DI={indicators['minus_di']:.0f})
EMA: 9 {'above' if indicators['ema9'] > indicators['ema21'] else 'below'} 21 | BB: {indicators['bb_position']}
Momentum: {chop_text} (CI={indicators['choppiness']:.0f})
Volume: {vol_text}"""

    if indicators.get("vwap"):
        result += f"\nVWAP: {indicators['vwap']}"

    result += f"""

━━ Smart Money ━━
Divergence: {div_text}
Order Blocks: {indicators['bull_order_blocks']} bullish / {indicators['bear_order_blocks']} bearish"""

    if sweep_text:
        result += f"\n{sweep_text}"
    if pat_texts:
        result += f"\nPatterns: {', '.join(pat_texts)}"

    if direction != "WAIT":
        res_text = " | ".join([str(r) for r in indicators["resistance"][:3]]) if indicators["resistance"] else "—"
        sup_text = " | ".join([str(s) for s in indicators["support"][:3]]) if indicators["support"] else "—"
        result += f"""

━━ Trade Levels ━━
💰 Entry: {trade['entry']}
🛡 Stop Loss: {trade['sl']} ({trade['sl_dist']} pts)
🎯 TP1: {trade['tp1']}
🎯 TP2: {trade['tp2']}
📈 R/R: {trade['rr_ratio']}

Resistance: {res_text}
Support: {sup_text}"""

    result += f"""

━━ Decision Summary ━━
Session: {indicators['session']} ({indicators['liquidity']})"""

    if direction == "WAIT":
        result += "\n⏳ No clear setup — conditions not met. Wait for better opportunity."
    elif score >= 90:
        result += f"\n✅ Very strong {dir_text} — {len([b for b in bd if '→ +' in b])} factors aligned."
    elif score >= 75:
        result += f"\n✅ Strong {dir_text} — enter with confidence."
    else:
        result += f"\n⚡ Moderate {dir_text} — enter cautiously with tight SL."

    warnings = []
    if indicators["choppiness"] > 61.8: warnings.append("Choppy market")
    if indicators["adx"] < 20: warnings.append("Weak trend")
    if indicators["session_mult"] < 0.8: warnings.append("Low liquidity")
    if sig["direction"] == "BUY" and indicators["trend"] == "bearish": warnings.append("Counter-trend")
    if sig["direction"] == "SELL" and indicators["trend"] == "bullish": warnings.append("Counter-trend")
    if warnings:
        result += f"\n⚠️ Warning: {' | '.join(warnings)}"

    return result


async def analyze_and_signal(pair: str, timeframe: str, indicators: dict, lang: str = "ar") -> tuple:
    """
    Generate the signal output. The direction is ALREADY decided by the
    scoring engine — this function formats it for display.

    Falls back to local formatting if AI is unavailable.
    """
    from config import PAIRS
    pair_info = PAIRS[pair]
    pair_name = pair_info["name_ar"] if lang == "ar" else pair_info["name_en"]

    # The decision is already made by math
    sig = indicators["signal"]
    is_wait = sig["direction"] == "WAIT"

    # Format locally (no AI dependency for the decision)
    if lang == "ar":
        result = _format_signal_ar(pair_name, timeframe, indicators)
    else:
        result = _format_signal_en(pair_name, timeframe, indicators)

    # Optional: Use AI to generate a 1-sentence market insight
    # This is purely cosmetic — the trade decision is locked
    try:
        if GROQ_KEY and sig["direction"] != "WAIT":
            insight = await _get_ai_insight(pair_name, timeframe, indicators, lang)
            if insight:
                label = "💡 رؤية الذكاء الاصطناعي:" if lang == "ar" else "💡 AI Insight:"
                result += f"\n\n{label} {insight}"
    except Exception:
        pass  # AI insight is optional — failure is fine

    return result, is_wait


async def _get_ai_insight(pair_name: str, timeframe: str, indicators: dict, lang: str) -> str:
    """Get a 1-sentence AI market insight. The direction is already locked."""
    sig = indicators["signal"]
    top_factors = [b for b in indicators.get("score_breakdown", []) if "→ +" in b][:3]

    if lang == "ar":
        system = "أنت محلل أسواق. أعطِ جملة واحدة فقط عن أهم سبب لهذه الإشارة. لا تغير الاتجاه أو الأرقام."
        prompt = (f"الإشارة: {sig['direction']} بثقة {sig['score']}/100 لـ {pair_name}\n"
                  f"أهم العوامل: {'; '.join(top_factors[:3])}\n"
                  f"اكتب جملة واحدة فقط تلخص أهم سبب.")
    else:
        system = "You are a market analyst. Give ONE sentence about the key reason for this signal. Do not change direction or numbers."
        prompt = (f"Signal: {sig['direction']} with {sig['score']}/100 confidence for {pair_name}\n"
                  f"Top factors: {'; '.join(top_factors[:3])}\n"
                  f"Write ONE sentence summarizing the key driver.")

    headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt}
        ],
        "max_tokens": 100,
        "temperature": 0.1,
    }

    async with aiohttp.ClientSession() as s:
        async with s.post(GROQ_URL, json=payload, headers=headers,
                          timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                return ""
            data = await resp.json()

    return data["choices"][0]["message"]["content"].strip()
