"""
ai_engine.py — V6 Signal Formatter
====================================
Redesigned UI with confidence meter, risk rating, and cleaner layout.
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

def _confidence_bar(score):
    """Visual confidence meter."""
    filled = int(score / 10)
    empty = 10 - filled
    if score >= 85:    color = "🟢"
    elif score >= 70:  color = "🟢"
    elif score >= 55:  color = "🟡"
    elif score >= 40:  color = "🟠"
    else:              color = "🔴"
    bar = "█" * filled + "░" * empty
    return f"{color} [{bar}] {score}/100"


def _format_signal_en(pair_name, timeframe, indicators):
    sig = indicators["signal"]
    trade = indicators["trade"]
    mtf = MTF_MAP_EN.get(timeframe, MTF_MAP_EN["1h"])

    direction = sig["direction"]
    score = sig["score"]
    strength = sig["strength"]

    if direction == "BUY":    dir_text, dir_emoji = "BUY 🟢", "🟢"
    elif direction == "SELL": dir_text, dir_emoji = "SELL 🔴", "🔴"
    else:                     dir_text, dir_emoji = "WAIT ⚪", "⚪"

    strength_en = {"VERY_STRONG": "Very Strong 💪💪", "STRONG": "Strong 💪",
                   "MODERATE": "Moderate ⚡", "ENTRY": "Entry Signal 📍", "WEAK": "Weak ⚠️"}.get(strength, "—")

    trend_en = {"bullish": "Bullish 📈", "bearish": "Bearish 📉", "neutral": "Neutral ↔️"}.get(indicators["trend"], "—")
    struct_en = {"bullish": "Bullish (HH+HL)", "bearish": "Bearish (LH+LL)",
                 "choch_bullish": "Bull reversal (CHoCH)", "choch_bearish": "Bear reversal (CHoCH)",
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

    chop = indicators["choppiness"]
    chop_text = "Choppy ⚠️" if chop > 61.8 else ("Trending ✅" if chop < 38.2 else "Mixed")

    # Momentum burst
    mb = indicators.get("momentum_burst", {})
    mb_text = ""
    if mb.get("burst") == "bullish":
        mb_text = f"\n🚀 Momentum Burst: Bullish ({mb['consecutive']} bars)"
    elif mb.get("burst") == "bearish":
        mb_text = f"\n🚀 Momentum Burst: Bearish ({mb['consecutive']} bars)"

    # Volatility regime
    vol_regime = indicators.get("volatility_regime", "normal")
    vol_ratio_val = indicators.get("volatility_ratio", 1.0)
    regime_text = {"explosive": "🔥 Explosive", "high": "📈 High", "low": "😴 Low", "normal": "📊 Normal"}.get(vol_regime, "Normal")

    # EMA Ribbon
    ribbon_dir = indicators.get("ema_ribbon_dir", "neutral")
    ribbon_str = indicators.get("ema_ribbon_str", 0)
    ribbon_text = ""
    if ribbon_dir != "neutral" and ribbon_str > 0.5:
        ribbon_text = f"\nEMA Ribbon: {ribbon_dir.title()} ({ribbon_str:.0%})"

    result = f"""⚡ Signal: {dir_text}
{_confidence_bar(score)}
📊 Strength: {strength_en}

━━ Market Context ━━
📈 Trend ({mtf['trend']}): {trend_en} ({indicators['trend_strength']:.0%})
🏗 Structure ({mtf['structure']}): {struct_en}
🌡 Volatility: {regime_text} (×{vol_ratio_val:.1f})
📊 Momentum: {chop_text} (CI={chop:.0f}){mb_text}

━━ Indicators ━━
RSI: {indicators['rsi']} | StochRSI: K={indicators['stoch_k']:.0f} D={indicators['stoch_d']:.0f}
MACD: {macd_en} | ADX: {indicators['adx']:.0f} (+DI={indicators['plus_di']:.0f} -DI={indicators['minus_di']:.0f})
EMA: 9 {'above' if indicators['ema9'] > indicators['ema21'] else 'below'} 21 | BB: {indicators['bb_position']}
Volume: {vol_text}{ribbon_text}"""

    if indicators.get("vwap"):
        result += f"\nVWAP: {indicators['vwap']}"

    result += f"""

━━ Smart Money ━━
Divergence: {div_text}
Order Blocks: {indicators['bull_order_blocks']} bull / {indicators['bear_order_blocks']} bear
FVG: {indicators['bull_fvg_count']} bull / {indicators['bear_fvg_count']} bear"""

    if sweep_text:
        result += f"\n{sweep_text}"
    if pat_texts:
        result += f"\nPatterns: {', '.join(pat_texts)}"

    if direction != "WAIT":
        res_text = " | ".join([str(r) for r in indicators["resistance"][:3]]) if indicators["resistance"] else "—"
        sup_text = " | ".join([str(s) for s in indicators["support"][:3]]) if indicators["support"] else "—"
        result += f"""

━━ Trade Setup ━━
💰 Entry: {trade['entry']}
🛡 Stop Loss: {trade['sl']} ({trade['sl_dist']} pts)
🎯 TP1: {trade['tp1']}
🎯 TP2: {trade['tp2']}
🎯 TP3: {trade['tp3']}
📈 R/R: {trade['rr_ratio']}
💼 Risk: {trade.get('risk_label', 'N/A')}

Resistance: {res_text}
Support: {sup_text}"""

    # Top contributing factors
    bd = indicators.get("score_breakdown", [])
    top_factors = [b for b in bd if "→ +" in b and float(b.split("+")[-1]) > 3][:4]
    if top_factors:
        result += "\n\n━━ Key Drivers ━━"
        for f in top_factors:
            result += f"\n• {f}"

    session_en = indicators["session"]
    result += f"""

━━ Decision ━━
Session: {session_en} ({indicators['liquidity']})"""

    if direction == "WAIT":
        bull_s, bear_s = sig.get("bull_score", 0), sig.get("bear_score", 0)
        result += f"\n⏳ No clear edge — Bull: {bull_s} vs Bear: {bear_s}"
        result += "\n💡 Tip: Try a different timeframe or wait for momentum."
    elif score >= 85:
        result += f"\n✅ Very strong {dir_text} — high confluence."
    elif score >= 70:
        result += f"\n✅ Strong {dir_text} — enter with confidence."
    elif score >= 55:
        result += f"\n⚡ Moderate {dir_text} — enter with tight SL."
    else:
        result += f"\n📍 Entry-level {dir_text} — small position, tight SL."

    warnings = []
    if indicators["choppiness"] > 61.8: warnings.append("Choppy market")
    if indicators["adx"] < 15: warnings.append("Weak trend")
    if indicators["session_mult"] < 0.8: warnings.append("Low liquidity session")
    if sig["direction"] == "BUY" and indicators["trend"] == "bearish": warnings.append("Counter-trend")
    if sig["direction"] == "SELL" and indicators["trend"] == "bullish": warnings.append("Counter-trend")
    if vol_regime == "explosive": warnings.append("High volatility — widen SL")
    if warnings:
        result += f"\n⚠️ {' | '.join(warnings)}"

    return result


def _format_signal_ar(pair_name, timeframe, indicators):
    sig = indicators["signal"]
    trade = indicators["trade"]
    mtf = MTF_MAP_AR.get(timeframe, MTF_MAP_AR["1h"])

    direction = sig["direction"]
    score = sig["score"]
    strength = sig["strength"]

    if direction == "BUY":    dir_text = "شراء 🟢"
    elif direction == "SELL": dir_text = "بيع 🔴"
    else:                     dir_text = "انتظار ⚪"

    strength_ar = {"VERY_STRONG": "قوية جداً 💪💪", "STRONG": "قوية 💪",
                   "MODERATE": "متوسطة ⚡", "ENTRY": "إشارة دخول 📍", "WEAK": "ضعيفة ⚠️"}.get(strength, "—")

    trend_ar = {"bullish": "صاعد 📈", "bearish": "هابط 📉", "neutral": "محايد ↔️"}.get(indicators["trend"], "—")
    struct_ar = {"bullish": "صاعد (HH+HL)", "bearish": "هابط (LH+LL)",
                 "choch_bullish": "انعكاس صاعد (CHoCH)", "choch_bearish": "انعكاس هابط (CHoCH)",
                 "neutral": "محايد"}.get(indicators["structure"], "—")
    macd_ar = "صاعد" if indicators["macd_direction"] == "bullish" else "هابط"

    vol = indicators["volume"]
    vol_text = {"bullish": f"شرائي x{vol['vol_ratio']}", "bearish": f"بيعي x{vol['vol_ratio']}",
                "drying_up": "يجف ⚠️", "neutral": f"عادي x{vol['vol_ratio']}"}.get(vol["vol_confirm"], "—")

    div = indicators["divergence"]
    div_text = "لا يوجد"
    if div["regular"] == "bullish": div_text = "تباعد صاعد 🔄"
    elif div["regular"] == "bearish": div_text = "تباعد هابط 🔄"
    elif div["hidden"] == "bullish": div_text = "تباعد خفي صاعد"
    elif div["hidden"] == "bearish": div_text = "تباعد خفي هابط"

    sweep = indicators["liquidity_sweep"]
    sweep_text = ""
    if sweep["bullish_sweep"]: sweep_text = "مسح سيولة صاعد 🎯"
    elif sweep["bearish_sweep"]: sweep_text = "مسح سيولة هابط 🎯"

    pat_texts = []
    for name, _ in indicators.get("candle_patterns", []):
        pat_map = {"bullish_engulfing": "ابتلاع صاعد", "bearish_engulfing": "ابتلاع هابط",
                   "bullish_pin_bar": "بن بار صاعد", "bearish_pin_bar": "بن بار هابط",
                   "morning_star": "نجمة الصباح", "evening_star": "نجمة المساء",
                   "three_white_soldiers": "3 جنود بيض", "three_black_crows": "3 غربان سود",
                   "hammer": "مطرقة", "shooting_star": "نجم ساقط",
                   "bull_momentum_candle": "شمعة زخم صاعد", "bear_momentum_candle": "شمعة زخم هابط"}
        pat_texts.append(pat_map.get(name, name))

    chop = indicators["choppiness"]
    chop_text = "متذبذب ⚠️" if chop > 61.8 else ("متجه ✅" if chop < 38.2 else "متوسط")

    mb = indicators.get("momentum_burst", {})
    mb_text = ""
    if mb.get("burst") == "bullish": mb_text = f"\n🚀 زخم صاعد ({mb['consecutive']} شمعات)"
    elif mb.get("burst") == "bearish": mb_text = f"\n🚀 زخم هابط ({mb['consecutive']} شمعات)"

    vol_regime = indicators.get("volatility_regime", "normal")
    vol_ratio_val = indicators.get("volatility_ratio", 1.0)
    regime_text = {"explosive": "🔥 انفجاري", "high": "📈 عالي", "low": "😴 منخفض", "normal": "📊 عادي"}.get(vol_regime, "عادي")

    session_ar = {"London": "لندن 🇬🇧", "London-NY Overlap": "تداخل لندن-نيويورك 🔥",
                  "New York": "نيويورك 🇺🇸", "Asia": "آسيا 🌏",
                  "Late NY / Early Asia": "آسيا المبكرة 🌙"}.get(indicators["session"], indicators["session"])

    result = f"""⚡ الإشارة: {dir_text}
{_confidence_bar(score)}
📊 القوة: {strength_ar}

━━ سياق السوق ━━
📈 الاتجاه ({mtf['trend']}): {trend_ar} ({indicators['trend_strength']:.0%})
🏗 البنية ({mtf['structure']}): {struct_ar}
🌡 التذبذب: {regime_text} (×{vol_ratio_val:.1f})
📊 الزخم: {chop_text} (CI={chop:.0f}){mb_text}

━━ المؤشرات ━━
RSI: {indicators['rsi']} | StochRSI: K={indicators['stoch_k']:.0f} D={indicators['stoch_d']:.0f}
MACD: {macd_ar} | ADX: {indicators['adx']:.0f} (+DI={indicators['plus_di']:.0f} -DI={indicators['minus_di']:.0f})
EMA: 9={'فوق' if indicators['ema9'] > indicators['ema21'] else 'تحت'} 21 | BB: {indicators['bb_position']}
الحجم: {vol_text}"""

    if indicators.get("vwap"):
        result += f"\nVWAP: {indicators['vwap']}"

    result += f"""

━━ التحليل الذكي ━━
التباعد: {div_text}
أوامر مؤسسية: {indicators['bull_order_blocks']} شرائي / {indicators['bear_order_blocks']} بيعي
FVG: {indicators['bull_fvg_count']} صاعد / {indicators['bear_fvg_count']} هابط"""

    if sweep_text: result += f"\n{sweep_text}"
    if pat_texts: result += f"\nنماذج: {', '.join(pat_texts)}"

    if direction != "WAIT":
        res_text = " | ".join([str(r) for r in indicators["resistance"][:3]]) if indicators["resistance"] else "—"
        sup_text = " | ".join([str(s) for s in indicators["support"][:3]]) if indicators["support"] else "—"
        result += f"""

━━ خطة التداول ━━
💰 الدخول: {trade['entry']}
🛡 وقف الخسارة: {trade['sl']} ({trade['sl_dist']} نقطة)
🎯 الهدف 1: {trade['tp1']}
🎯 الهدف 2: {trade['tp2']}
🎯 الهدف 3: {trade['tp3']}
📈 نسبة R/R: {trade['rr_ratio']}
💼 المخاطرة: {trade.get('risk_label', 'N/A')}

مقاومات: {res_text}
دعوم: {sup_text}"""

    bd = indicators.get("score_breakdown", [])
    top_factors = [b for b in bd if "→ +" in b and float(b.split("+")[-1]) > 3][:4]
    if top_factors:
        result += "\n\n━━ أهم العوامل ━━"
        for f in top_factors:
            result += f"\n• {f}"

    result += f"""

━━ ملخص القرار ━━
الجلسة: {session_ar} ({indicators['liquidity']})"""

    if direction == "WAIT":
        bull_s, bear_s = sig.get("bull_score", 0), sig.get("bear_score", 0)
        result += f"\n⏳ لا توجد أفضلية واضحة — شراء: {bull_s} vs بيع: {bear_s}"
        result += "\n💡 جرّب إطار زمني آخر أو انتظر زخم واضح."
    elif score >= 85:
        result += f"\n✅ إشارة {dir_text} قوية جداً — توافق عالي."
    elif score >= 70:
        result += f"\n✅ إشارة {dir_text} قوية — ادخل بثقة."
    elif score >= 55:
        result += f"\n⚡ إشارة {dir_text} متوسطة — وقف خسارة محكم."
    else:
        result += f"\n📍 إشارة {dir_text} — حجم صغير ووقف محكم."

    warnings = []
    if indicators["choppiness"] > 61.8: warnings.append("سوق متذبذب")
    if indicators["adx"] < 15: warnings.append("اتجاه ضعيف")
    if indicators["session_mult"] < 0.8: warnings.append("سيولة منخفضة")
    if sig["direction"] == "BUY" and indicators["trend"] == "bearish": warnings.append("عكس الاتجاه")
    if sig["direction"] == "SELL" and indicators["trend"] == "bullish": warnings.append("عكس الاتجاه")
    if vol_regime == "explosive": warnings.append("تذبذب عالي — وسّع الوقف")
    if warnings:
        result += f"\n⚠️ {' | '.join(warnings)}"

    return result


async def analyze_and_signal(pair: str, timeframe: str, indicators: dict, lang: str = "ar") -> tuple:
    from config import PAIRS
    pair_info = PAIRS[pair]
    pair_name = pair_info["name_ar"] if lang == "ar" else pair_info["name_en"]

    sig = indicators["signal"]
    is_wait = sig["direction"] == "WAIT"

    if lang == "ar":
        result = _format_signal_ar(pair_name, timeframe, indicators)
    else:
        result = _format_signal_en(pair_name, timeframe, indicators)

    # Optional AI insight for non-WAIT signals
    try:
        if GROQ_KEY and sig["direction"] != "WAIT":
            insight = await _get_ai_insight(pair_name, timeframe, indicators, lang)
            if insight:
                label = "💡 رؤية AI:" if lang == "ar" else "💡 AI Insight:"
                result += f"\n\n{label} {insight}"
    except Exception:
        pass

    return result, is_wait


async def _get_ai_insight(pair_name: str, timeframe: str, indicators: dict, lang: str) -> str:
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
