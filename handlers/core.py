"""
handlers/core.py — التدفق الكامل: اختيار اللغة → الزوج → الفريم → التوصية
"""

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import database as db
from config import PAIRS, TIMEFRAMES, FREE_SIGNALS, BOT_NAME

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
    await update.message.reply_text("🌐 *Choose your language / اختر لغتك:*",
                                     parse_mode="Markdown", reply_markup=keyboard)

async def send_home(target, user_id, edit=False):
    pro  = db.is_pro(user_id)
    used = db.free_signals_used(user_id)
    rem  = max(0, FREE_SIGNALS - used)

    if t(user_id, "ar", "en") == "ar":
        plan_badge = "⭐ برو — غير محدود" if pro else f"🆓 مجاني — {rem}/{FREE_SIGNALS} متبقية"
        text = (
            f"📡 *{BOT_NAME}*\n\n"
            f"توصيات تداول دقيقة مدعومة بالذكاء الاصطناعي\n"
            f"وبيانات السوق الحقيقية.\n\n"
            f"*الأزواج المتاحة:*\n"
            + "\n".join([f"{v['emoji']} {v['name_ar']}" for v in PAIRS.values()])
            + f"\n\n━━━━━━━━━━━━━━━━\n"
            f"خطتك: *{plan_badge}*\n\n"
            f"👇 اضغط *توصية جديدة* للبدء"
        )
        buttons = [
            [InlineKeyboardButton("📡 توصية جديدة", callback_data="new_signal")],
            [InlineKeyboardButton("💎 اشتراك برو", callback_data="show_plans"),
             InlineKeyboardButton("📊 إحصائياتي",  callback_data="my_stats")],
            [InlineKeyboardButton("🌐 English", callback_data="lang_en")],
        ]
    else:
        plan_badge = "⭐ Pro — Unlimited" if pro else f"🆓 Free — {rem}/{FREE_SIGNALS} left"
        text = (
            f"📡 *{BOT_NAME}*\n\n"
            f"AI-powered trading signals based on\n"
            f"real market data & technical analysis.\n\n"
            f"*Available Pairs:*\n"
            + "\n".join([f"{v['emoji']} {v['name_en']}" for v in PAIRS.values()])
            + f"\n\n━━━━━━━━━━━━━━━━\n"
            f"Your plan: *{plan_badge}*\n\n"
            f"👇 Tap *New Signal* to start"
        )
        buttons = [
            [InlineKeyboardButton("📡 New Signal", callback_data="new_signal")],
            [InlineKeyboardButton("💎 Go Pro",   callback_data="show_plans"),
             InlineKeyboardButton("📊 My Stats", callback_data="my_stats")],
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
            text = (f"📊 *إحصائياتك*\n\nالخطة: *{'⭐ برو' if pro else '🆓 مجاني'}*\n"
                    f"توصيات مجانية استُخدمت: `{used}/{FREE_SIGNALS}`\nإجمالي التوصيات: `{total}`")
        else:
            text = (f"📊 *Your Stats*\n\nPlan: *{'⭐ Pro' if pro else '🆓 Free'}*\n"
                    f"Free signals used: `{used}/{FREE_SIGNALS}`\nTotal signals: `{total}`")
        extra = [] if pro else [[InlineKeyboardButton(
            t(user_id, "💎 ترقية إلى برو", "💎 Upgrade to Pro"), callback_data="show_plans")]]
        await query.edit_message_text(text, parse_mode="Markdown",
                                       reply_markup=home_keyboard(user_id, extra))
        return

    if data == "new_signal":
        if not db.can_use(user_id):
            text = (f"⚠️ *استنفدت توصياتك المجانية الـ {FREE_SIGNALS}.*\n\nاشترك في برو للحصول على توصيات غير محدودة."
                    if t(user_id, "ar", "en") == "ar" else
                    f"⚠️ *You've used all {FREE_SIGNALS} free signals.*\n\nSubscribe to Pro for unlimited signals.")
            await query.edit_message_text(text, parse_mode="Markdown",
                reply_markup=home_keyboard(user_id, [[InlineKeyboardButton(
                    t(user_id, "💎 اشتراك برو — 35$", "💎 Go Pro — $35/mo"),
                    callback_data="show_plans")]]))
            return

        buttons = []
        for pair_key, pair_info in PAIRS.items():
            name = pair_info["name_ar"] if t(user_id, "ar", "en") == "ar" else pair_info["name_en"]
            buttons.append([InlineKeyboardButton(f"{pair_info['emoji']} {name}", callback_data=f"pair_{pair_key}")])
        label = "اختر الزوج:" if t(user_id, "ar", "en") == "ar" else "Choose a pair:"
        await query.edit_message_text(f"📊 *{label}*", parse_mode="Markdown",
                                       reply_markup=home_keyboard(user_id, buttons))
        return

    if data.startswith("pair_"):
        pair = data.replace("pair_", "")
        ctx.user_data["selected_pair"] = pair
        pair_info = PAIRS[pair]
        buttons = []
        for tf_key, tf_info in TIMEFRAMES.items():
            label = tf_info["label_ar"] if t(user_id, "ar", "en") == "ar" else tf_info["label_en"]
            buttons.append([InlineKeyboardButton(f"⏱ {label}", callback_data=f"tf_{tf_key}")])
        pair_name = pair_info["name_ar"] if t(user_id, "ar", "en") == "ar" else pair_info["name_en"]
        label = "اختر الإطار الزمني:" if t(user_id, "ar", "en") == "ar" else "Choose timeframe:"
        await query.edit_message_text(f"{pair_info['emoji']} *{pair_name}*\n\n*{label}*",
                                       parse_mode="Markdown", reply_markup=home_keyboard(user_id, buttons))
        return

    if data.startswith("tf_"):
        timeframe = data.replace("tf_", "")
        pair      = ctx.user_data.get("selected_pair")
        if not pair:
            await send_home(query, user_id, edit=True)
            return

        pair_info = PAIRS[pair]
        tf_info   = TIMEFRAMES[timeframe]
        lang      = db.get_lang(user_id)
        pair_name = pair_info["name_ar"] if lang == "ar" else pair_info["name_en"]
        tf_name   = tf_info["label_ar"]  if lang == "ar" else tf_info["label_en"]

        wait_text = (
            f"⏳ *جارٍ تحليل {pair_name} على {tf_name}...*\n\n"
            f"🔍 جلب بيانات السوق الحقيقية...\n📊 حساب المؤشرات التقنية...\n🤖 تحليل الذكاء الاصطناعي...\n\n"
            f"_قد يستغرق هذا دقيقة_"
            if lang == "ar" else
            f"⏳ *Analyzing {pair} on {tf_name}...*\n\n"
            f"🔍 Fetching real market data...\n📊 Computing indicators...\n🤖 AI deep analysis...\n\n"
            f"_This may take a minute_"
        )
        await query.edit_message_text(wait_text, parse_mode="Markdown")

        try:
            from services.market_data import fetch_candles, compute_indicators
            from services.ai_engine   import analyze_and_signal

            df         = await fetch_candles(pair, timeframe)
            indicators = compute_indicators(df)
            signal_text = await analyze_and_signal(pair, timeframe, indicators, lang)

            # تسجيل الاستخدام
            direction = "BUY" if "BUY" in signal_text.upper() else "SELL" if "SELL" in signal_text.upper() else "WAIT"
            db.log_signal(user_id, pair, timeframe, direction)

            pro  = db.is_pro(user_id)
            used = db.free_signals_used(user_id)

            if lang == "ar":
                header = f"📡 *توصية {pair_info['emoji']} {pair_name} — {tf_name}*\n{'━'*30}\n\n"
                footer = f"\n\n{'━'*30}\n_{'⭐ برو — غير محدود' if pro else f'🆓 استخدمت {used}/{FREE_SIGNALS} مجانية'}_"
            else:
                header = f"📡 *Signal: {pair_info['emoji']} {pair} — {tf_name}*\n{'━'*30}\n\n"
                footer = f"\n\n{'━'*30}\n_{'⭐ Pro — Unlimited' if pro else f'🆓 Used {used}/{FREE_SIGNALS} free'}_"

            full_text = header + signal_text + footer
            chunks    = [full_text[i:i+4000] for i in range(0, len(full_text), 4000)]

            extra_buttons = [[InlineKeyboardButton(
                t(user_id, "📡 توصية جديدة", "📡 New Signal"), callback_data="new_signal")]]
            if not pro:
                extra_buttons.append([InlineKeyboardButton(
                    t(user_id, "💎 اشتراك برو — توصيات غير محدودة", "💎 Go Pro — Unlimited Signals"),
                    callback_data="show_plans")])

            await query.edit_message_text(chunks[0], parse_mode="Markdown",
                                           reply_markup=home_keyboard(user_id, extra_buttons))
            for chunk in chunks[1:]:
                await query.message.reply_text(chunk, parse_mode="Markdown")

        except Exception as e:
            await query.edit_message_text(
                f"❌ {'حدث خطأ أثناء التحليل' if lang == 'ar' else 'Analysis failed'}.\n`{str(e)[:100]}`",
                parse_mode="Markdown", reply_markup=home_keyboard(user_id))
            raise
