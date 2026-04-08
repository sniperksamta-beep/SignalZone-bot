from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import database as db
from config import PAIRS, TIMEFRAMES, FREE_SIGNALS, BOT_NAME, BOT_VERSION, SUPPORT_USERNAME
import datetime

import re, logging
_log = logging.getLogger(__name__)

def _sanitize_markdown(text: str) -> str:
    """Fix common broken Markdown that Telegram rejects."""
    # Ensure even number of each inline marker so entities close properly
    for ch in ['`', '*', '_']:
        if text.count(ch) % 2 != 0:
            text = text + ch          # close the dangling entity
    return text

def _smart_chunks(text: str, limit: int = 4000) -> list[str]:
    """Split text at newlines instead of mid-entity."""
    if len(text) <= limit:
        return [text]
    chunks, current = [], ""
    for line in text.split('\n'):
        if len(current) + len(line) + 1 > limit and current:
            chunks.append(_sanitize_markdown(current))
            current = line
        else:
            current = current + '\n' + line if current else line
    if current:
        chunks.append(_sanitize_markdown(current))
    return chunks or [text]

async def _safe_edit(msg, text, **kwargs):
    """Try Markdown first, fall back to plain text on parse error."""
    try:
        return await msg.edit_text(text, parse_mode="Markdown", **kwargs)
    except Exception as e:
        if "parse entities" in str(e).lower() or "can't find end" in str(e).lower():
            _log.warning("Markdown parse failed, sending as plain text")
            return await msg.edit_text(text, **kwargs)
        raise

async def _safe_reply(msg, text, **kwargs):
    try:
        return await msg.reply_text(text, parse_mode="Markdown", **kwargs)
    except Exception as e:
        if "parse entities" in str(e).lower() or "can't find end" in str(e).lower():
            return await msg.reply_text(text, **kwargs)
        raise

def t(user_id, ar_text, en_text):
    lang = db.get_lang(user_id)
    return ar_text if lang == "ar" else en_text

def home_keyboard(user_id, extra_rows=None):
    rows = extra_rows or []
    rows.append([InlineKeyboardButton(t(user_id, "🏠 الرئيسية", "🏠 Home"), callback_data="go_home")])
    return InlineKeyboardMarkup(rows)

async def start_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.ensure_user(user.id, user.username or "", user.full_name or "")
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar"),
        InlineKeyboardButton("🇺🇸 English",  callback_data="lang_en"),
    ]])
    await update.message.reply_text(
        "🌐 *Choose your language / اختر لغتك:*",
        parse_mode="Markdown", reply_markup=keyboard
    )

async def send_home(target, user_id, edit=False):
    pro  = db.is_pro(user_id)
    used = db.free_signals_used(user_id)
    rem  = max(0, FREE_SIGNALS - used)

    if t(user_id, "ar", "en") == "ar":
        plan_badge = "⭐ برو — غير محدود" if pro else f"🆓 مجاني — {rem}/{FREE_SIGNALS} متبقية"
        text = (
            f"📡 *{BOT_NAME} V{BOT_VERSION}*\n\n"
            f"🧠 محرك تحليل مؤسسي — 20+ مؤشر مرجّح\n"
            f"🚀 محسّن للسكالبينج — إشارات فعلية\n"
            f"⚡ Smart Money + زخم + EMA Ribbon\n"
            f"📊 3 أهداف ربح + تقييم مخاطر\n\n"
            f"*الأزواج المتاحة:*\n"
            + "\n".join([f"{v['emoji']} {v['name_ar']}" for v in PAIRS.values()])
            + f"\n\n━━━━━━━━━━━━━━━━\n"
            f"خطتك: *{plan_badge}*\n\n"
            f"👇 اضغط *توصية جديدة* للبدء"
        )
        buttons = [
            [InlineKeyboardButton("📡 توصية جديدة", callback_data="new_signal")],
            [
                InlineKeyboardButton("⚡ سكالب سريع", callback_data="quick_scalp"),
                InlineKeyboardButton("📊 إحصائياتي", callback_data="my_stats"),
            ],
            [
                InlineKeyboardButton("💎 اشتراك برو",  callback_data="show_plans"),
                InlineKeyboardButton("🆘 الدعم الفني",  url=f"https://t.me/{SUPPORT_USERNAME}"),
            ],
            [InlineKeyboardButton("🌐 English", callback_data="lang_en")],
        ]
    else:
        plan_badge = "⭐ Pro — Unlimited" if pro else f"🆓 Free — {rem}/{FREE_SIGNALS} left"
        text = (
            f"📡 *{BOT_NAME} V{BOT_VERSION}*\n\n"
            f"🧠 Institutional engine — 20+ weighted indicators\n"
            f"🚀 Optimized for scalping — real signals\n"
            f"⚡ Smart Money + Momentum Burst + EMA Ribbon\n"
            f"📊 3 TP targets + Risk assessment\n\n"
            f"*Available Pairs:*\n"
            + "\n".join([f"{v['emoji']} {v['name_en']}" for v in PAIRS.values()])
            + f"\n\n━━━━━━━━━━━━━━━━\n"
            f"Your plan: *{plan_badge}*\n\n"
            f"👇 Tap *New Signal* to start"
        )
        buttons = [
            [InlineKeyboardButton("📡 New Signal", callback_data="new_signal")],
            [
                InlineKeyboardButton("⚡ Quick Scalp", callback_data="quick_scalp"),
                InlineKeyboardButton("📊 My Stats",    callback_data="my_stats"),
            ],
            [
                InlineKeyboardButton("💎 Go Pro",    callback_data="show_plans"),
                InlineKeyboardButton("🆘 Support",   url=f"https://t.me/{SUPPORT_USERNAME}"),
            ],
            [InlineKeyboardButton("🌐 العربية", callback_data="lang_ar")],
        ]

    keyboard = InlineKeyboardMarkup(buttons)
    if edit:
        await target.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
    else:
        await target.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    data    = query.data
    user_id = query.from_user.id

    if data in ("lang_ar", "lang_en"):
        lang = data.split("_")[1]
        db.ensure_user(user_id, query.from_user.username or "", query.from_user.full_name or "", lang)
        db.set_lang(user_id, lang)
        await send_home(query, user_id, edit=True)
        return

    if data == "go_home":
        await send_home(query, user_id, edit=True)
        return

    if data == "my_stats":
        row   = db.get_user(user_id)
        pro   = db.is_pro(user_id)
        used  = db.free_signals_used(user_id)
        total = row["total_signals"] if row else 0
        if t(user_id, "ar", "en") == "ar":
            text = (
                f"📊 *إحصائياتك*\n\n"
                f"الخطة: *{'⭐ برو' if pro else '🆓 مجاني'}*\n"
                f"توصيات مجانية: `{used}/{FREE_SIGNALS}`\n"
                f"إجمالي: `{total}`\n"
                f"الإصدار: `V{BOT_VERSION}`"
            )
        else:
            text = (
                f"📊 *Your Stats*\n\n"
                f"Plan: *{'⭐ Pro' if pro else '🆓 Free'}*\n"
                f"Free used: `{used}/{FREE_SIGNALS}`\n"
                f"Total: `{total}`\n"
                f"Version: `V{BOT_VERSION}`"
            )
        extra = [] if pro else [[InlineKeyboardButton(
            t(user_id, "💎 ترقية إلى برو", "💎 Upgrade to Pro"),
            callback_data="show_plans"
        )]]
        await query.edit_message_text(
            text, parse_mode="Markdown",
            reply_markup=home_keyboard(user_id, extra)
        )
        return

    # Quick Scalp — XAUUSD 5m one-tap
    if data == "quick_scalp":
        if not db.can_use(user_id):
            text = (
                f"⚠️ *{'استنفدت التوصيات المجانية' if t(user_id,'ar','en')=='ar' else 'Free signals used up'}*"
            )
            await query.edit_message_text(text, parse_mode="Markdown",
                reply_markup=home_keyboard(user_id, [[
                    InlineKeyboardButton(t(user_id, "💎 برو", "💎 Pro"), callback_data="show_plans")
                ]]))
            return

        remaining = db.check_cooldown(user_id)
        if remaining > 0:
            m, s = remaining // 60, remaining % 60
            await query.edit_message_text(
                f"⏳ *{'انتظر' if t(user_id,'ar','en')=='ar' else 'Wait'} {m}:{s:02d}*",
                parse_mode="Markdown", reply_markup=home_keyboard(user_id))
            return

        # Show pair selection for quick scalp
        buttons = []
        for pair_key, pair_info in PAIRS.items():
            name = pair_info["name_ar"] if t(user_id,"ar","en") == "ar" else pair_info["name_en"]
            buttons.append([InlineKeyboardButton(
                f"⚡ {pair_info['emoji']} {name}",
                callback_data=f"scalp_{pair_key}"
            )])
        label = "⚡ سكالب سريع — اختر الزوج:" if t(user_id,"ar","en") == "ar" else "⚡ Quick Scalp — Choose pair:"
        await query.edit_message_text(
            f"*{label}*", parse_mode="Markdown",
            reply_markup=home_keyboard(user_id, buttons)
        )
        return

    # Quick scalp execution — auto 5m
    if data.startswith("scalp_"):
        pair = data.replace("scalp_", "")
        ctx.user_data["selected_pair"] = pair
        # Jump straight to analysis with 5m
        data = "tf_5m"
        # Fall through to tf_ handler below

    if data == "new_signal":
        if not db.can_use(user_id):
            text = (
                f"⚠️ *استنفدت {FREE_SIGNALS} توصيات المجانية.*\n\n"
                f"اشترك في برو للحصول على توصيات غير محدودة."
                if t(user_id,"ar","en") == "ar" else
                f"⚠️ *You've used all {FREE_SIGNALS} free signals.*\n\n"
                f"Subscribe to Pro for unlimited signals."
            )
            await query.edit_message_text(
                text, parse_mode="Markdown",
                reply_markup=home_keyboard(user_id, [[
                    InlineKeyboardButton(
                        t(user_id, "💎 اشتراك برو", "💎 Go Pro"),
                        callback_data="show_plans"
                    )
                ]])
            )
            return

        remaining = db.check_cooldown(user_id)
        if remaining > 0:
            mins = remaining // 60
            secs = remaining % 60
            text = (
                f"⏳ *انتظر {mins}:{secs:02d} دقيقة*\n\n"
                f"فترة انتظار بين كل توصية والأخرى لضمان جودة التحليل."
                if t(user_id,"ar","en") == "ar" else
                f"⏳ *Wait {mins}:{secs:02d} minutes*\n\n"
                f"Cooldown between signals to ensure analysis quality."
            )
            await query.edit_message_text(
                text, parse_mode="Markdown",
                reply_markup=home_keyboard(user_id)
            )
            return

        buttons = []
        for pair_key, pair_info in PAIRS.items():
            name = pair_info["name_ar"] if t(user_id,"ar","en") == "ar" else pair_info["name_en"]
            buttons.append([InlineKeyboardButton(
                f"{pair_info['emoji']} {name}",
                callback_data=f"pair_{pair_key}"
            )])
        label = "اختر الزوج:" if t(user_id,"ar","en") == "ar" else "Choose a pair:"
        await query.edit_message_text(
            f"📊 *{label}*", parse_mode="Markdown",
            reply_markup=home_keyboard(user_id, buttons)
        )
        return

    if data.startswith("pair_"):
        pair      = data.replace("pair_", "")
        ctx.user_data["selected_pair"] = pair
        pair_info = PAIRS[pair]
        buttons   = []
        for tf_key, tf_info in TIMEFRAMES.items():
            label = tf_info["label_ar"] if t(user_id,"ar","en") == "ar" else tf_info["label_en"]
            buttons.append([InlineKeyboardButton(f"⏱ {label}", callback_data=f"tf_{tf_key}")])
        pair_name = pair_info["name_ar"] if t(user_id,"ar","en") == "ar" else pair_info["name_en"]
        label     = "اختر الإطار الزمني:" if t(user_id,"ar","en") == "ar" else "Choose timeframe:"
        await query.edit_message_text(
            f"{pair_info['emoji']} *{pair_name}*\n\n*{label}*",
            parse_mode="Markdown",
            reply_markup=home_keyboard(user_id, buttons)
        )
        return

    if data.startswith("tf_"):
        timeframe = data.replace("tf_", "")
        pair      = ctx.user_data.get("selected_pair")
        if not pair:
            await send_home(query, user_id, edit=True)
            return

        # Cooldown check (was missing here — users bypassed via Same Pair)
        remaining = db.check_cooldown(user_id)
        if remaining > 0:
            m, s = remaining // 60, remaining % 60
            text = (
                f"⏳ *انتظر {m}:{s:02d} دقيقة*\n\n"
                f"فترة انتظار بين كل توصية والأخرى لضمان جودة التحليل."
                if t(user_id,"ar","en") == "ar" else
                f"⏳ *Wait {m}:{s:02d} minutes*\n\n"
                f"Cooldown between signals to ensure analysis quality."
            )
            await query.edit_message_text(
                text, parse_mode="Markdown",
                reply_markup=home_keyboard(user_id)
            )
            return

        if not db.can_use(user_id):
            text = (
                f"⚠️ *{'استنفدت التوصيات المجانية' if t(user_id,'ar','en')=='ar' else 'Free signals used up'}*"
            )
            await query.edit_message_text(text, parse_mode="Markdown",
                reply_markup=home_keyboard(user_id, [[
                    InlineKeyboardButton(t(user_id, "💎 برو", "💎 Pro"), callback_data="show_plans")
                ]]))
            return

        pair_info = PAIRS[pair]
        lang      = db.get_lang(user_id)
        pair_name = pair_info["name_ar"] if lang == "ar" else pair_info["name_en"]
        tf_name   = TIMEFRAMES[timeframe]["label_ar"] if lang == "ar" else TIMEFRAMES[timeframe]["label_en"]

        wait_text = (
            f"⏳ *جارٍ تحليل {pair_name} على {tf_name}...*\n\n"
            f"🔍 جلب 3 فريمات متزامنة...\n"
            f"📊 حساب 20+ مؤشر...\n"
            f"🧠 تحليل Smart Money + Momentum...\n"
            f"⚡ محرك النقاط V6...\n\n"
            f"_قد يستغرق دقيقة_"
            if lang == "ar" else
            f"⏳ *Analyzing {pair} on {tf_name}...*\n\n"
            f"🔍 Fetching 3 timeframes...\n"
            f"📊 Computing 20+ indicators...\n"
            f"🧠 Smart Money + Momentum analysis...\n"
            f"⚡ V6 Scoring Engine...\n\n"
            f"_This may take a minute_"
        )
        await query.edit_message_text(wait_text, parse_mode="Markdown")

        try:
            from services.market_data import fetch_candles, compute_indicators
            from services.ai_engine   import analyze_and_signal

            frames     = await fetch_candles(pair, timeframe)
            indicators = compute_indicators(frames, timeframe)
            signal_text, is_wait = await analyze_and_signal(pair, timeframe, indicators, lang)

            sig = indicators["signal"]
            if not is_wait:
                direction = sig["direction"]
                db.log_signal(user_id, pair, timeframe, direction)
            else:
                db.update_last_signal(user_id)

            pro  = db.is_pro(user_id)
            used = db.free_signals_used(user_id)

            validity_minutes = indicators["trade"].get("validity_minutes", 60)
            score = sig["score"]

            if lang == "ar":
                header = f"📡 *{pair_info['emoji']} {pair_name} — {tf_name}*\n{'━'*30}\n\n"
                footer = (
                    f"\n\n{'━'*30}\n"
                    f"🧠 _نقاط الثقة: {score}/100_\n"
                    f"⏰ _صالحة: {validity_minutes} دقيقة_\n"
                    f"_{'⭐ برو — غير محدود' if pro else f'🆓 استخدمت {used}/{FREE_SIGNALS} مجانية'}_"
                )
            else:
                header = f"📡 *{pair_info['emoji']} {pair} — {tf_name}*\n{'━'*30}\n\n"
                footer = (
                    f"\n\n{'━'*30}\n"
                    f"🧠 _Confidence: {score}/100_\n"
                    f"⏰ _Valid: {validity_minutes} min_\n"
                    f"_{'⭐ Pro — Unlimited' if pro else f'🆓 Used {used}/{FREE_SIGNALS} free'}_"
                )

            full_text = header + signal_text + footer
            chunks    = _smart_chunks(full_text, 4000)

            # After-signal action buttons
            extra_buttons = [
                [
                    InlineKeyboardButton(
                        t(user_id, "🔄 نفس الزوج", "🔄 Same Pair"),
                        callback_data=f"pair_{pair}"
                    ),
                    InlineKeyboardButton(
                        t(user_id, "📡 توصية جديدة", "📡 New Signal"),
                        callback_data="new_signal"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        t(user_id, "⚡ سكالب سريع", "⚡ Quick Scalp"),
                        callback_data="quick_scalp"
                    ),
                ],
            ]
            if not pro:
                extra_buttons.append([InlineKeyboardButton(
                    t(user_id, "💎 اشتراك برو", "💎 Go Pro"),
                    callback_data="show_plans"
                )])

            await _safe_edit(
                query.message, chunks[0],
                reply_markup=home_keyboard(user_id, extra_buttons)
            )
            for chunk in chunks[1:]:
                await _safe_reply(query.message, chunk)

        except Exception as e:
            err_msg = str(e)[:150].replace('`', "'")
            await _safe_edit(
                query.message,
                f"❌ {'حدث خطأ' if lang=='ar' else 'Error'}.\n`{err_msg}`",
                reply_markup=home_keyboard(user_id)
            )
            raise
