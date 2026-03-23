"""
handlers/payment.py — Upgrade flow, payment instructions, manual confirmation.
"""

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import database as db
from config import (
    YOUR_USDT_TRC20, YOUR_USDT_ERC20, YOUR_BTC, YOUR_ETH,
    PRICE_MONTHLY_USDT, PRICE_3MONTH_USDT, PRICE_MONTHLY_BTC,
    ADMIN_IDS, BOT_NAME
)


PLANS = {
    "pro_1m": {
        "name":    "Pro — 1 Month",
        "months":  1,
        "price":   PRICE_MONTHLY_USDT,
        "coin":    "USDT",
        "label":   f"⭐ 1 Month — ${PRICE_MONTHLY_USDT} USDT",
    },
    "pro_3m": {
        "name":    "Pro — 3 Months",
        "months":  3,
        "price":   PRICE_3MONTH_USDT,
        "coin":    "USDT",
        "label":   f"💰 3 Months — ${PRICE_3MONTH_USDT} USDT (save $4)",
    },
}

WALLETS = {
    "USDT_TRC20": {"address": YOUR_USDT_TRC20, "label": "USDT TRC-20 (Tron) ✅ Recommended"},
    "USDT_ERC20": {"address": YOUR_USDT_ERC20, "label": "USDT ERC-20 (Ethereum)"},
    "BTC":        {"address": YOUR_BTC,         "label": "Bitcoin (BTC)"},
    "ETH":        {"address": YOUR_ETH,         "label": "Ethereum (ETH)"},
}


async def upgrade_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show upgrade plans."""
    await _show_plans(update.message)


async def show_plans_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "show_plans":
        await _show_plans(query.message, edit=True)

    elif query.data.startswith("buy_"):
        plan_key = query.data.replace("buy_", "")
        plan     = PLANS.get(plan_key)
        if not plan:
            return

        ctx.user_data["selected_plan"] = plan_key

        # Show coin selector
        buttons = []
        for coin_key, wallet in WALLETS.items():
            buttons.append([InlineKeyboardButton(
                wallet["label"],
                callback_data=f"pay_coin_{coin_key}_{plan_key}"
            )])
        buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="show_plans")])

        await query.edit_message_text(
            f"💎 *{plan['name']}*\n"
            f"Price: *{plan['price']} {plan['coin']}*\n\n"
            f"Choose your payment method:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    elif query.data.startswith("pay_coin_"):
        parts    = query.data.split("_")
        # format: pay_coin_{COIN_KEY}_{plan_key}
        # e.g.   pay_coin_USDT_TRC20_pro_1m
        # Find plan key (last 2 parts joined)
        plan_key = "_".join(parts[-2:])
        coin_key = "_".join(parts[2:-2])

        plan   = PLANS.get(plan_key)
        wallet = WALLETS.get(coin_key)
        if not plan or not wallet:
            await query.answer("Invalid selection.", show_alert=True)
            return

        user_id = query.from_user.id
        pay_id  = db.add_payment(user_id, plan_key, plan["price"], coin_key, wallet["address"])
        ctx.user_data["pay_id"]   = pay_id
        ctx.user_data["pay_months"] = plan["months"]

        address = wallet["address"]
        amount  = plan["price"]
        coin_label = wallet["label"]

        instruction = (
            f"💳 *Payment Instructions*\n\n"
            f"Plan: *{plan['name']}*\n"
            f"Amount: *{amount} USDT*\n"
            f"Network: *{coin_label}*\n\n"
            f"Send *exactly* `{amount}` USDT to:\n\n"
            f"`{address}`\n\n"
            f"_(Tap the address to copy)_\n\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"After sending, tap ✅ below and I'll activate your Pro plan.\n\n"
            f"⚠️ *Important:*\n"
            f"• Send on the correct network\n"
            f"• Wrong network = lost funds\n"
            f"• Payment ID: `{pay_id}`"
        )

        buttons = [
            [InlineKeyboardButton("✅ I've sent the payment", callback_data=f"paid_{pay_id}")],
            [InlineKeyboardButton("⬅️ Choose different coin",  callback_data=f"buy_{plan_key}")],
        ]

        await query.edit_message_text(
            instruction,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    elif query.data.startswith("paid_"):
        pay_id  = int(query.data.replace("paid_", ""))
        user_id = query.from_user.id
        months  = ctx.user_data.get("pay_months", 1)

        # Notify admins for manual verification
        user    = query.from_user
        name    = user.full_name or user.username or str(user_id)

        for admin_id in ADMIN_IDS:
            try:
                await ctx.bot.send_message(
                    admin_id,
                    f"💰 *Payment claim received!*\n\n"
                    f"User: {name} (`{user_id}`)\n"
                    f"Payment ID: `{pay_id}`\n"
                    f"Months: `{months}`\n\n"
                    f"To activate, reply:\n"
                    f"`/confirm {pay_id} {user_id} {months}`",
                    parse_mode="Markdown",
                )
            except Exception:
                pass

        await query.edit_message_text(
            "⏳ *Payment submitted for review!*\n\n"
            f"Payment ID: `{pay_id}`\n\n"
            "Our team will verify and activate your Pro plan within *1-2 hours*.\n\n"
            "You'll receive a notification here once it's activated.\n\n"
            "_If you don't hear back in 2 hours, use /support_",
            parse_mode="Markdown",
        )


async def _show_plans(message, edit: bool = False):
    text = (
        f"💎 *Upgrade to {BOT_NAME} Pro*\n\n"
        f"🆓 *Free Plan*\n"
        f"• {5} generations per month\n"
        f"• All 6 platforms\n\n"
        f"⭐ *Pro Plan*\n"
        f"• ♾️ Unlimited generations\n"
        f"• Priority processing\n"
        f"• All 6 platforms\n"
        f"• Future features free\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"*Choose a plan:*"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(PLANS["pro_1m"]["label"], callback_data="buy_pro_1m")],
        [InlineKeyboardButton(PLANS["pro_3m"]["label"], callback_data="buy_pro_3m")],
    ])

    if edit:
        await message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)
    else:
        await message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


# ── Admin commands ────────────────────────────────────────────────

async def confirm_payment_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin command: /confirm {pay_id} {user_id} {months}"""
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        return

    args = ctx.args
    if len(args) < 3:
        await update.message.reply_text("Usage: /confirm {pay_id} {user_id} {months}")
        return

    try:
        pay_id  = int(args[0])
        user_id = int(args[1])
        months  = int(args[2])
    except ValueError:
        await update.message.reply_text("Invalid arguments.")
        return

    db.confirm_payment(pay_id, user_id, months)

    # Notify the user
    try:
        import datetime
        expires = datetime.datetime.now() + datetime.timedelta(days=months*30)
        await ctx.bot.send_message(
            user_id,
            f"🎉 *Your Pro plan is now active!*\n\n"
            f"✅ Unlimited generations unlocked\n"
            f"📅 Valid until: *{expires.strftime('%B %d, %Y')}*\n\n"
            f"Send me any URL or text to start creating content!",
            parse_mode="Markdown",
        )
    except Exception:
        pass

    await update.message.reply_text(
        f"✅ Payment {pay_id} confirmed. User {user_id} activated for {months} month(s)."
    )


async def admin_stats_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin command: /stats"""
    if update.effective_user.id not in ADMIN_IDS:
        return

    total_users  = db.all_users_count()
    pro_users    = db.pro_users_count()
    total_gens   = db.total_generations()
    pending      = db.pending_payments()

    text = (
        f"📊 *Admin Stats*\n\n"
        f"Total users: `{total_users}`\n"
        f"Pro users: `{pro_users}`\n"
        f"Total generations: `{total_gens}`\n\n"
        f"*Pending payments:* `{len(pending)}`\n"
    )
    for p in pending:
        text += f"\n• ID `{p['id']}` — User `{p['user_id']}` — {p['plan']} — {p['coin']}"

    await update.message.reply_text(text, parse_mode="Markdown")
