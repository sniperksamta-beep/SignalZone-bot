"""
handlers/payment.py — نظام الدفع والاشتراك (ثنائي اللغة)
"""

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import database as db
from config import (
    YOUR_USDT_TRC20, YOUR_USDT_ERC20, YOUR_BTC,
    PRICE_MONTHLY, PRICE_3MONTH, ADMIN_IDS, BOT_NAME
)
from handlers.core import home_keyboard, t

PLANS = {
    "pro_1m": {"months": 1, "price": PRICE_MONTHLY},
    "pro_3m": {"months": 3, "price": PRICE_3MONTH},
}

WALLETS = {
    "USDT_TRC20": {"address": YOUR_USDT_TRC20},
    "USDT_ERC20": {"address": YOUR_USDT_ERC20},
    "BTC":        {"address": YOUR_BTC},
}


async def upgrade_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _show_plans(update.message, update.effective_user.id)


async def plans_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data    = query.data

    if data == "show_plans":
        await _show_plans(query, user_id, edit=True)

    elif data.startswith("buy_"):
        plan_key = data.replace("buy_", "")
        plan     = PLANS.get(plan_key)
        if not plan:
            return
        ctx.user_data["plan_key"] = plan_key

        if t(user_id, "ar", "en") == "ar":
            labels = {
                "USDT_TRC20": "USDT TRC-20 (ترون) ✅ موصى به",
                "USDT_ERC20": "USDT ERC-20 (إيثيريوم)",
                "BTC":        "بيتكوين (BTC)",
            }
            title = f"💳 اختر طريقة الدفع\nالمبلغ: *{plan['price']}$*"
        else:
            labels = {
                "USDT_TRC20": "USDT TRC-20 (Tron) ✅ Recommended",
                "USDT_ERC20": "USDT ERC-20 (Ethereum)",
                "BTC":        "Bitcoin (BTC)",
            }
            title = f"💳 Choose payment method\nAmount: *${plan['price']}*"

        buttons = [[InlineKeyboardButton(labels[k], callback_data=f"paycoin_{k}_{plan_key}")]
                   for k in WALLETS]

        await query.edit_message_text(
            title, parse_mode="Markdown",
            reply_markup=home_keyboard(user_id, buttons)
        )

    elif data.startswith("paycoin_"):
        parts    = data.split("_")
        plan_key = "_".join(parts[-2:])
        coin_key = "_".join(parts[1:-2])
        plan     = PLANS.get(plan_key)
        wallet   = WALLETS.get(coin_key)
        if not plan or not wallet:
            return

        pay_id = db.add_payment(user_id, plan_key, plan["price"], coin_key, wallet["address"])
        ctx.user_data["pay_months"] = plan["months"]

        addr = wallet["address"]
        amt  = plan["price"]

        if t(user_id, "ar", "en") == "ar":
            text = (
                f"💳 *تعليمات الدفع*\n\n"
                f"المبلغ: *{amt} USDT*\n"
                f"الشبكة: *{coin_key}*\n\n"
                f"أرسل *{amt} USDT بالضبط* إلى:\n\n"
                f"`{addr}`\n\n"
                f"_اضغط العنوان لنسخه_\n\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"بعد الإرسال اضغط ✅ أدناه.\n"
                f"⚠️ تأكد من الشبكة الصحيحة!\n"
                f"رقم الدفع: `{pay_id}`"
            )
            confirm_btn = "✅ أرسلت الدفع"
            back_btn    = "⬅️ تغيير"
        else:
            text = (
                f"💳 *Payment Instructions*\n\n"
                f"Amount: *{amt} USDT*\n"
                f"Network: *{coin_key}*\n\n"
                f"Send *exactly {amt} USDT* to:\n\n"
                f"`{addr}`\n\n"
                f"_Tap address to copy_\n\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"After sending, tap ✅ below.\n"
                f"⚠️ Use the correct network!\n"
                f"Payment ID: `{pay_id}`"
            )
            confirm_btn = "✅ I've sent the payment"
            back_btn    = "⬅️ Back"

        await query.edit_message_text(
            text, parse_mode="Markdown",
            reply_markup=home_keyboard(user_id, [
                [InlineKeyboardButton(confirm_btn, callback_data=f"paid_{pay_id}")],
                [InlineKeyboardButton(back_btn,    callback_data=f"buy_{plan_key}")],
            ])
        )

    elif data.startswith("paid_"):
        pay_id  = int(data.replace("paid_", ""))
        months  = ctx.user_data.get("pay_months", 1)
        name    = query.from_user.full_name or query.from_user.username or str(user_id)

        for admin_id in ADMIN_IDS:
            try:
                await ctx.bot.send_message(
                    admin_id,
                    f"💰 *طلب تأكيد دفع*\n\n"
                    f"المستخدم: {name} (`{user_id}`)\n"
                    f"رقم الدفع: `{pay_id}`\n"
                    f"الأشهر: `{months}`\n\n"
                    f"للتفعيل:\n`/confirm {pay_id} {user_id} {months}`",
                    parse_mode="Markdown"
                )
            except Exception:
                pass

        if t(user_id, "ar", "en") == "ar":
            text = (
                f"⏳ *تم إرسال طلب الدفع!*\n\n"
                f"رقم الدفع: `{pay_id}`\n\n"
                f"سيتم تفعيل اشتراكك خلال *1-2 ساعة*.\n"
                f"ستصلك رسالة تأكيد هنا."
            )
        else:
            text = (
                f"⏳ *Payment submitted!*\n\n"
                f"Payment ID: `{pay_id}`\n\n"
                f"Your Pro plan will be activated within *1-2 hours*.\n"
                f"You'll receive a confirmation message here."
            )

        await query.edit_message_text(text, parse_mode="Markdown",
                                       reply_markup=home_keyboard(user_id))


async def _show_plans(target, user_id, edit=False):
    if t(user_id, "ar", "en") == "ar":
        text = (
            f"💎 *اشتراك {BOT_NAME} برو*\n\n"
            f"🆓 *مجاني:* {4} توصيات فقط\n\n"
            f"⭐ *برو:*\n"
            f"• توصيات غير محدودة\n"
            f"• جميع الأزواج\n"
            f"• جميع الإطارات الزمنية\n"
            f"• تحليل ذكاء اصطناعي عميق\n\n"
            f"*اختر خطة:*"
        )
        buttons = [
            [InlineKeyboardButton(f"⭐ شهر واحد — {PRICE_MONTHLY}$",  callback_data="buy_pro_1m")],
            [InlineKeyboardButton(f"💰 3 أشهر — {PRICE_3MONTH}$ (وفّر 15$)", callback_data="buy_pro_3m")],
        ]
    else:
        text = (
            f"💎 *{BOT_NAME} Pro Subscription*\n\n"
            f"🆓 *Free:* {4} signals only\n\n"
            f"⭐ *Pro:*\n"
            f"• Unlimited signals\n"
            f"• All pairs\n"
            f"• All timeframes\n"
            f"• Deep AI analysis\n\n"
            f"*Choose a plan:*"
        )
        buttons = [
            [InlineKeyboardButton(f"⭐ 1 Month — ${PRICE_MONTHLY}",        callback_data="buy_pro_1m")],
            [InlineKeyboardButton(f"💰 3 Months — ${PRICE_3MONTH} (save $15)", callback_data="buy_pro_3m")],
        ]

    keyboard = home_keyboard(user_id, buttons)
    if edit:
        await target.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
    else:
        await target.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


# ── أوامر الإدارة ─────────────────────────────────────────────────
async def confirm_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    args = ctx.args
    if len(args) < 3:
        await update.message.reply_text("Usage: /confirm {pay_id} {user_id} {months}")
        return
    try:
        pay_id, user_id, months = int(args[0]), int(args[1]), int(args[2])
    except ValueError:
        await update.message.reply_text("Invalid args.")
        return

    db.confirm_payment(pay_id, user_id, months)

    try:
        import datetime
        exp = datetime.datetime.now() + datetime.timedelta(days=months*30)
        lang = db.get_lang(user_id)
        if lang == "ar":
            msg = f"🎉 *تم تفعيل اشتراكك برو!*\n\n✅ توصيات غير محدودة\n📅 حتى: *{exp.strftime('%d/%m/%Y')}*"
        else:
            msg = f"🎉 *Pro plan activated!*\n\n✅ Unlimited signals\n📅 Until: *{exp.strftime('%d/%m/%Y')}*"
        await ctx.bot.send_message(user_id, msg, parse_mode="Markdown")
    except Exception:
        pass

    await update.message.reply_text(f"✅ Confirmed. User {user_id} activated for {months} month(s).")


async def stats_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    text = (
        f"📊 *Admin Stats*\n\n"
        f"Users: `{db.all_users_count()}`\n"
        f"Pro: `{db.pro_users_count()}`\n"
        f"Signals: `{db.total_signals_count()}`\n"
        f"Pending payments: `{len(db.pending_payments())}`"
    )
    await update.message.reply_text(text, parse_mode="Markdown")
