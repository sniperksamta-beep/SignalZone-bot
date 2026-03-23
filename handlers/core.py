"""
handlers/core.py — واجهة البوت الكاملة بالعربية مع تنقل سهل
"""

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import database as db
from config import BOT_NAME, FREE_USES_PER_MONTH

PLATFORM_EMOJIS = {
    "TWITTER":   "🐦",
    "LINKEDIN":  "💼",
    "INSTAGRAM": "📸",
    "YOUTUBE":   "▶️",
    "EMAIL":     "📧",
    "TIKTOK":    "🎵",
}

PLATFORM_NAMES = {
    "TWITTER":   "خيط تويتر / X",
    "LINKEDIN":  "منشور لينكدإن",
    "INSTAGRAM": "تعليق إنستغرام",
    "YOUTUBE":   "وصف يوتيوب",
    "EMAIL":     "نشرة بريدية",
    "TIKTOK":    "سكريبت تيك توك",
}

# ── زر الرئيسية الثابت ─────────────────────────────────────────
HOME_ROW = [InlineKeyboardButton("🏠 الرئيسية", callback_data="go_home")]


def home_keyboard(extra_rows: list = None) -> InlineKeyboardMarkup:
    """أي كيبورد + زر الرئيسية دائمًا في الأسفل."""
    rows = extra_rows or []
    rows.append(HOME_ROW)
    return InlineKeyboardMarkup(rows)


async def _send_home(target, edit: bool = False):
    """إرسال أو تعديل رسالة الرئيسية."""
    text = (
        f"🔥 *Flareposts*\n\n"
        f"أرسل لي أي شيء وسأحوّله إلى 6 منشورات جاهزة:\n\n"
        f"🔗 رابط مقال\n"
        f"▶️ رابط يوتيوب\n"
        f"📝 نص أو أفكار\n\n"
        f"*المنصات:*\n"
        f"🐦 تويتر/X  |  💼 لينكدإن  |  📸 إنستغرام\n"
        f"▶️ يوتيوب  |  📧 بريد  |  🎵 تيك توك"
    )
    keyboard = home_keyboard([
        [
            InlineKeyboardButton("💎 ترقية برو", callback_data="show_plans"),
            InlineKeyboardButton("📊 إحصائياتي", callback_data="my_stats"),
        ],
        [InlineKeyboardButton("📖 كيف يعمل؟", callback_data="how_it_works")],
    ])
    if edit:
        await target.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
    else:
        await target.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def start_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.ensure_user(user.id, user.username or "", user.full_name or "")
    await _send_home(update.message)


async def help_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        f"📖 *دليل الاستخدام*\n\n"
        f"أرسل رابطًا أو نصًا وسيولّد البوت 6 منشورات.\n\n"
        f"*الأوامر:*\n"
        f"`/start` — الرئيسية\n"
        f"`/upgrade` — الترقية إلى برو\n"
        f"`/status` — خطتك واستخداماتك\n\n"
        f"*الخطط:*\n"
        f"🆓 مجاني — {FREE_USES_PER_MONTH} توليدات/شهر\n"
        f"⭐ برو — غير محدود مقابل 8 USDT/شهر\n"
        f"💰 3 أشهر — 20 USDT (وفّر 4$)"
    )
    await update.message.reply_text(
        text, parse_mode="Markdown",
        reply_markup=home_keyboard([
            [InlineKeyboardButton("💎 الترقية إلى برو", callback_data="show_plans")]
        ])
    )


async def status_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.ensure_user(user.id, user.username or "", user.full_name or "")
    row = db.get_user(user.id)
    pro = db.is_pro(user.id)
    used_month = db.uses_this_month(user.id)
    total = row["total_uses"] if row else 0

    if pro and row:
        import datetime
        expires_str = datetime.datetime.fromtimestamp(row["plan_expires"]).strftime("%d %b %Y")
        plan_text = f"⭐ *برو* — ينتهي {expires_str}"
    else:
        remaining = max(0, FREE_USES_PER_MONTH - used_month)
        plan_text = f"🆓 *مجاني* — {remaining}/{FREE_USES_PER_MONTH} متبقية"

    text = (
        f"📊 *إحصائياتك*\n\n"
        f"الخطة: {plan_text}\n"
        f"هذا الشهر: `{used_month}` توليدات\n"
        f"الإجمالي: `{total}` توليدات"
    )
    extra = [] if pro else [[InlineKeyboardButton("💎 الترقية إلى برو", callback_data="show_plans")]]
    await update.message.reply_text(
        text, parse_mode="Markdown",
        reply_markup=home_keyboard(extra)
    )


async def generate_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()
    if text.startswith("/"):
        return

    db.ensure_user(user.id, user.username or "", user.full_name or "")
    pro  = db.is_pro(user.id)
    used = db.uses_this_month(user.id)

    if not pro and used >= FREE_USES_PER_MONTH:
        await update.message.reply_text(
            f"⚠️ *استنفدت {FREE_USES_PER_MONTH} توليدات المجانية هذا الشهر.*\n\n"
            f"قم بالترقية إلى برو للحصول على استخدام غير محدود.",
            parse_mode="Markdown",
            reply_markup=home_keyboard([
                [InlineKeyboardButton("💎 ترقية إلى برو", callback_data="show_plans")]
            ])
        )
        return

    msg = await update.message.reply_text(
        "⚡ *جارٍ توليد المحتوى...*\n\n"
        "🔍 قراءة المصدر...\n"
        "🤖 توليد 6 منشورات...\n"
        "_يستغرق هذا 10-20 ثانية_",
        parse_mode="Markdown"
    )

    try:
        from services.ai_engine import generate_content
        result = await generate_content(text)
        db.log_generation(user.id, text[:200])

        ctx.user_data["last_result"] = result["platforms"]

        source_labels = {"url": "🔗 مقال", "youtube": "▶️ فيديو", "text": "📝 نص"}
        source_label  = source_labels.get(result["source_type"], "محتوى")

        # بناء أزرار المنصات
        platform_buttons = []
        platforms = list(result["platforms"].keys())
        for i in range(0, len(platforms), 2):
            row = []
            for p in platforms[i:i+2]:
                row.append(InlineKeyboardButton(
                    f"{PLATFORM_EMOJIS.get(p,'')} {PLATFORM_NAMES.get(p,p)}",
                    callback_data=f"show_platform_{p}"
                ))
            platform_buttons.append(row)

        platform_buttons.append([
            InlineKeyboardButton("📦 جميع المنشورات الـ 6", callback_data="show_all")
        ])

        used_now = db.uses_this_month(user.id)
        footer = f"\n_{'⭐ برو — غير محدود' if pro else f'استخدمت {used_now}/{FREE_USES_PER_MONTH} هذا الشهر'}_"

        await msg.edit_text(
            f"✅ *تم التوليد من {source_label}!*\n\n"
            f"اختر المنصة 👇{footer}",
            parse_mode="Markdown",
            reply_markup=home_keyboard(platform_buttons)
        )

    except ValueError as e:
        await msg.edit_text(
            f"⚠️ {e}\n\nجرّب رابطًا آخر أو الصق النص مباشرة.",
            reply_markup=home_keyboard()
        )
    except Exception:
        await msg.edit_text(
            "❌ حدث خطأ. الرجاء المحاولة مرة أخرى.",
            reply_markup=home_keyboard()
        )
        raise


async def platform_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # ── الرئيسية ─────────────────────────────────────────────────
    if data == "go_home":
        await _send_home(query, edit=True)
        return

    # ── كيف يعمل ─────────────────────────────────────────────────
    if data == "how_it_works":
        await query.edit_message_text(
            "🔧 *كيف يعمل Flareposts:*\n\n"
            "1️⃣ أرسل رابطًا أو نص يوتيوب أو نصًا\n"
            "2️⃣ يقرأ الذكاء الاصطناعي المحتوى ويفهمه\n"
            "3️⃣ يعيد كتابته بأسلوب كل منصة\n"
            "4️⃣ تختار المنشورات وتنسخها\n\n"
            "• تويتر: خيوط موجزة وجذّابة\n"
            "• لينكدإن: سرد احترافي\n"
            "• إنستغرام: أسلوب غير رسمي + هاشتاقات\n"
            "• يوتيوب: وصف محسّن لـ SEO\n"
            "• البريد: نشرة مع دعوة للعمل\n"
            "• تيك توك: سكريبت منطوق مع توقيت",
            parse_mode="Markdown",
            reply_markup=home_keyboard()
        )
        return

    # ── إحصائيات ─────────────────────────────────────────────────
    if data == "my_stats":
        user  = query.from_user
        row   = db.get_user(user.id)
        pro   = db.is_pro(user.id)
        used  = db.uses_this_month(user.id)
        total = row["total_uses"] if row else 0
        remaining = "∞" if pro else max(0, FREE_USES_PER_MONTH - used)

        await query.edit_message_text(
            f"📊 *إحصائياتك*\n\n"
            f"الخطة: *{'⭐ برو' if pro else '🆓 مجاني'}*\n"
            f"هذا الشهر: `{used}` توليدات\n"
            f"المتبقي: `{remaining}`\n"
            f"الإجمالي: `{total}` توليدات",
            parse_mode="Markdown",
            reply_markup=home_keyboard(
                [] if pro else [[InlineKeyboardButton("💎 ترقية إلى برو", callback_data="show_plans")]]
            )
        )
        return

    # ── عرض منصة معينة ───────────────────────────────────────────
    platforms = ctx.user_data.get("last_result", {})

    if data == "show_all":
        await query.edit_message_text(
            "📦 *إرسال جميع المنشورات...*",
            parse_mode="Markdown",
            reply_markup=home_keyboard()
        )
        for platform, content in platforms.items():
            emoji = PLATFORM_EMOJIS.get(platform, "📄")
            name  = PLATFORM_NAMES.get(platform, platform)
            full_text = f"{emoji} *{name}*\n{'─'*30}\n{content}"
            for chunk in [full_text[i:i+4000] for i in range(0, len(full_text), 4000)]:
                await query.message.reply_text(chunk, parse_mode="Markdown")

        # زر الرجوع بعد إرسال الكل
        await query.message.reply_text(
            "✅ *تم إرسال جميع المنشورات!*",
            parse_mode="Markdown",
            reply_markup=home_keyboard()
        )
        return

    if data.startswith("show_platform_"):
        if not platforms:
            await query.edit_message_text(
                "⚠️ انتهت الجلسة. أرسل المحتوى مجددًا.",
                reply_markup=home_keyboard()
            )
            return

        platform  = data.replace("show_platform_", "")
        content   = platforms.get(platform, "غير متاح.")
        emoji     = PLATFORM_EMOJIS.get(platform, "📄")
        name      = PLATFORM_NAMES.get(platform, platform)
        full_text = f"{emoji} *{name}*\n{'─'*30}\n{content}"

        # أزرار التنقل بين المنصات
        nav_buttons = [
            InlineKeyboardButton(PLATFORM_EMOJIS.get(p, "📄"), callback_data=f"show_platform_{p}")
            for p in platforms.keys()
        ]

        keyboard = home_keyboard([
            nav_buttons,
            [InlineKeyboardButton("📦 جميع المنشورات", callback_data="show_all")]
        ])

        for i, chunk in enumerate([full_text[j:j+4000] for j in range(0, len(full_text), 4000)]):
            if i == 0:
                await query.edit_message_text(chunk, parse_mode="Markdown", reply_markup=keyboard)
            else:
                await query.message.reply_text(chunk, parse_mode="Markdown")
