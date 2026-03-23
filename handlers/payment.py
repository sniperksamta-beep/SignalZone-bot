"""
handlers/payment.py — نظام الدفع والترقية بالعربية
"""

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import database as db
from config import (
    YOUR_USDT_TRC20, YOUR_USDT_ERC20, YOUR_BTC, YOUR_ETH,
    PRICE_MONTHLY_USDT, PRICE_3MONTH_USDT, ADMIN_IDS, BOT_NAME
)

PLANS = {
    "pro_1m": {
        "name":   "برو — شهر واحد",
        "months": 1,
        "price":  PRICE_MONTHLY_USDT,
        "label":  f"⭐ شهر واحد — {PRICE_MONTHLY_USDT}$ USDT",
    },
    "pro_3m": {
        "name":   "برو — 3 أشهر",
        "months": 3,
        "price":  PRICE_3MONTH_USDT,
        "label":  f"💰 3 أشهر — {PRICE_3MONTH_USDT}$ USDT (وفّر 4$)",
    },
}

WALLETS = {
    "USDT_TRC20": {"address": YOUR_USDT_TRC20, "label": "USDT TRC-20 (ترون) ✅ موصى به"},
    "USDT_ERC20": {"address": YOUR_USDT_ERC20, "label": "USDT ERC-20 (إيثيريوم)"},
    "BTC":        {"address": YOUR_BTC,         "label": "بيتكوين (BTC)"},
    "ETH":        {"address": YOUR_ETH,         "label": "إيثيريوم (ETH)"},
}


async def upgrade_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _show_plans(update.message)


async def show_plans_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "show_plans":
        await _show_plans(query.message, edit=True)

    elif query.data.startswith("buy_"):
        plan_key = query.data.replace("buy_", "")
        plan = PLANS.get(plan_key)
        if not plan:
            return

        ctx.user_data["selected_plan"] = plan_key

        buttons = []
        for coin_key, wallet in WALLETS.items():
            buttons.append([InlineKeyboardButton(
                wallet["label"], callback_data=f"pay_coin_{coin_key}_{plan_key}"
            )])
        buttons.append([InlineKeyboardButton("⬅️ رجوع", callback_data="show_plans")])

        await query.edit_message_text(
            f"💎 *{plan['name']}*\n"
            f"السعر: *{plan['price']} USDT*\n\n"
            f"اختر طريقة الدفع:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    elif query.data.startswith("pay_coin_"):
        parts    = query.data.split("_")
        plan_key = "_".join(parts[-2:])
        coin_key = "_".join(parts[2:-2])

        plan   = PLANS.get(plan_key)
        wallet = WALLETS.get(coin_key)
        if not plan or not wallet:
            await query.answer("اختيار غير صالح.", show_alert=True)
            return

        user_id = query.from_user.id
        pay_id  = db.add_payment(user_id, plan_key, plan["price"], coin_key, wallet["address"])
        ctx.user_data["pay_id"]    = pay_id
        ctx.user_data["pay_months"] = plan["months"]

        address    = wallet["address"]
        amount     = plan["price"]
        coin_label = wallet["label"]

        instruction = (
            f"💳 *تعليمات الدفع*\n\n"
            f"الخطة: *{plan['name']}*\n"
            f"المبلغ: *{amount} USDT*\n"
            f"الشبكة: *{coin_label}*\n\n"
            f"أرسل *{amount} USDT بالضبط* إلى:\n\n"
            f"`{address}`\n\n"
            f"_(اضغط على العنوان لنسخه)_\n\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"بعد الإرسال، اضغط ✅ أدناه وسيتم تفعيل خطة برو.\n\n"
            f"⚠️ *مهم:*\n"
            f"• أرسل على الشبكة الصحيحة\n"
            f"• الشبكة الخاطئة = ضياع الأموال\n"
            f"• رقم الدفع: `{pay_id}`"
        )

        buttons = [
            [InlineKeyboardButton("✅ أرسلت الدفع", callback_data=f"paid_{pay_id}")],
            [InlineKeyboardButton("⬅️ تغيير العملة", callback_data=f"buy_{plan_key}")],
        ]

        await query.edit_message_text(
            instruction, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    elif query.data.startswith("paid_"):
        pay_id  = int(query.data.replace("paid_", ""))
        user_id = query.from_user.id
        months  = ctx.user_data.get("pay_months", 1)
        user    = query.from_user
        name    = user.full_name or user.username or str(user_id)

        for admin_id in ADMIN_IDS:
            try:
                await ctx.bot.send_message(
                    admin_id,
                    f"💰 *طلب تأكيد دفع!*\n\n"
                    f"المستخدم: {name} (`{user_id}`)\n"
                    f"رقم الدفع: `{pay_id}`\n"
                    f"الأشهر: `{months}`\n\n"
                    f"للتفعيل أرسل:\n"
                    f"`/confirm {pay_id} {user_id} {months}`",
                    parse_mode="Markdown",
                )
            except Exception:
                pass

        await query.edit_message_text(
            "⏳ *تم إرسال طلب الدفع للمراجعة!*\n\n"
            f"رقم الدفع: `{pay_id}`\n\n"
            "سيتم التحقق وتفعيل خطة برو خلال *1-2 ساعة*.\n\n"
            "ستصلك رسالة هنا فور التفعيل.\n\n"
            "_إذا لم تتلقَّ ردًا خلال ساعتين، استخدم /support_",
            parse_mode="Markdown",
        )


async def _show_plans(message, edit: bool = False):
    text = (
        f"💎 *الترقية إلى {BOT_NAME} برو*\n\n"
        f"🆓 *الخطة المجانية*\n"
        f"• {5} توليدات شهريًا\n"
        f"• جميع المنصات الـ 6\n\n"
        f"⭐ *خطة برو*\n"
        f"• ♾️ توليدات غير محدودة\n"
        f"• معالجة أولوية\n"
        f"• جميع المنصات الـ 6\n"
        f"• الميزات الجديدة مجانًا\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"*اختر خطة:*"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(PLANS["pro_1m"]["label"], callback_data="buy_pro_1m")],
        [InlineKeyboardButton(PLANS["pro_3m"]["label"], callback_data="buy_pro_3m")],
    ])

    if edit:
        await message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)
    else:
        await message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def confirm_payment_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        return

    args = ctx.args
    if len(args) < 3:
        await update.message.reply_text("الاستخدام: /confirm {pay_id} {user_id} {months}")
        return

    try:
        pay_id  = int(args[0])
        user_id = int(args[1])
        months  = int(args[2])
    except ValueError:
        await update.message.reply_text("معطيات غير صالحة.")
        return

    db.confirm_payment(pay_id, user_id, months)

    try:
        import datetime
        expires = datetime.datetime.now() + datetime.timedelta(days=months*30)
        await ctx.bot.send_message(
            user_id,
            f"🎉 *تم تفعيل خطة برو!*\n\n"
            f"✅ توليدات غير محدودة مفعّلة\n"
            f"📅 صالحة حتى: *{expires.strftime('%d %B %Y')}*\n\n"
            f"أرسل لي أي رابط أو نص وابدأ التوليد!",
            parse_mode="Markdown",
        )
    except Exception:
        pass

    await update.message.reply_text(
        f"✅ تم تأكيد الدفع {pay_id}. تم تفعيل المستخدم {user_id} لمدة {months} شهر/أشهر."
    )


async def admin_stats_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return

    total_users = db.all_users_count()
    pro_users   = db.pro_users_count()
    total_gens  = db.total_generations()
    pending     = db.pending_payments()

    text = (
        f"📊 *إحصائيات الإدارة*\n\n"
        f"إجمالي المستخدمين: `{total_users}`\n"
        f"مستخدمو برو: `{pro_users}`\n"
        f"إجمالي التوليدات: `{total_gens}`\n\n"
        f"*المدفوعات المعلّقة:* `{len(pending)}`\n"
    )
    for p in pending:
        text += f"\n• ID `{p['id']}` — مستخدم `{p['user_id']}` — {p['plan']} — {p['coin']}"

    await update.message.reply_text(text, parse_mode="Markdown")
