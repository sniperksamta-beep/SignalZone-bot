from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import database as db
import datetime
import time
from config import (
    YOUR_USDT_TRC20, YOUR_USDT_ERC20, YOUR_BTC, YOUR_ETH, YOUR_BNB, YOUR_SOL,
    PRICE_MONTHLY, PRICE_3MONTH, ADMIN_IDS, BOT_NAME
)
from handlers.core import home_keyboard, t

PLANS = {
    "pro_1m": {"months": 1, "price": PRICE_MONTHLY},
    "pro_3m": {"months": 3, "price": PRICE_3MONTH},
}

def get_wallets(user_id):
    ar = t(user_id,"ar","en") == "ar"
    wallets = {}
    if YOUR_USDT_TRC20: wallets["USDT_TRC20"] = {"address": YOUR_USDT_TRC20, "label": "USDT TRC-20 (ترون) ✅" if ar else "USDT TRC-20 (Tron) ✅"}
    if YOUR_USDT_ERC20: wallets["USDT_ERC20"] = {"address": YOUR_USDT_ERC20, "label": "USDT ERC-20 (إيثيريوم)" if ar else "USDT ERC-20 (Ethereum)"}
    if YOUR_BTC:        wallets["BTC"]         = {"address": YOUR_BTC,        "label": "بيتكوين (BTC)" if ar else "Bitcoin (BTC)"}
    if YOUR_ETH:        wallets["ETH"]         = {"address": YOUR_ETH,        "label": "إيثيريوم (ETH)" if ar else "Ethereum (ETH)"}
    if YOUR_BNB:        wallets["BNB"]         = {"address": YOUR_BNB,        "label": "BNB (BSC)"}
    if YOUR_SOL:        wallets["SOL"]         = {"address": YOUR_SOL,        "label": "سولانا (SOL)" if ar else "Solana (SOL)"}
    return wallets


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
        plan_key = data.replace("buy_","")
        plan     = PLANS.get(plan_key)
        if not plan: return
        wallets  = get_wallets(user_id)
        title    = f"💳 {'اختر طريقة الدفع' if t(user_id,'ar','en')=='ar' else 'Choose payment'}\n{'المبلغ' if t(user_id,'ar','en')=='ar' else 'Amount'}: *{plan['price']}$*"
        buttons  = [[InlineKeyboardButton(w["label"], callback_data=f"paycoin_{k}_{plan_key}")] for k,w in wallets.items()]
        await query.edit_message_text(title, parse_mode="Markdown", reply_markup=home_keyboard(user_id, buttons))

    elif data.startswith("paycoin_"):
        parts    = data.split("_")
        plan_key = "_".join(parts[-2:])
        coin_key = "_".join(parts[1:-2])
        plan     = PLANS.get(plan_key)
        wallets  = get_wallets(user_id)
        wallet   = wallets.get(coin_key)
        if not plan or not wallet: return

        pay_id = db.add_payment(user_id, plan_key, plan["price"], coin_key, wallet["address"])
        ctx.user_data["pay_months"] = plan["months"]
        addr, amt = wallet["address"], plan["price"]

        if t(user_id,"ar","en") == "ar":
            text = (f"💳 *تعليمات الدفع*\n\nالمبلغ: *{amt}$*\nالشبكة: *{wallet['label']}*\n\n"
                    f"أرسل بالضبط إلى:\n`{addr}`\n\n_اضغط للنسخ_\n\n━━━━━━━━━━━━━━━━\n"
                    f"بعد الإرسال اضغط ✅\n⚠️ تأكد من الشبكة!\nرقم الدفع: `{pay_id}`")
            cb, bk = "✅ أرسلت الدفع", "⬅️ تغيير"
        else:
            text = (f"💳 *Payment Instructions*\n\nAmount: *${amt}*\nNetwork: *{wallet['label']}*\n\n"
                    f"Send exactly to:\n`{addr}`\n\n_Tap to copy_\n\n━━━━━━━━━━━━━━━━\n"
                    f"After sending tap ✅\n⚠️ Use correct network!\nPayment ID: `{pay_id}`")
            cb, bk = "✅ I've sent the payment", "⬅️ Back"

        await query.edit_message_text(text, parse_mode="Markdown",
            reply_markup=home_keyboard(user_id, [
                [InlineKeyboardButton(cb, callback_data=f"paid_{pay_id}")],
                [InlineKeyboardButton(bk, callback_data=f"buy_{plan_key}")],
            ]))

    elif data.startswith("paid_"):
        pay_id = int(data.replace("paid_",""))
        months = ctx.user_data.get("pay_months", 1)
        name   = query.from_user.full_name or query.from_user.username or str(user_id)
        for admin_id in ADMIN_IDS:
            try:
                await ctx.bot.send_message(admin_id,
                    f"💰 *طلب تأكيد دفع*\n\nالمستخدم: {name} (`{user_id}`)\n"
                    f"رقم الدفع: `{pay_id}`\nالأشهر: `{months}`\n\n"
                    f"للتفعيل:\n`/confirm {pay_id} {user_id} {months}`",
                    parse_mode="Markdown")
            except Exception:
                pass
        text = (f"⏳ *تم إرسال طلب الدفع!*\n\nرقم الدفع: `{pay_id}`\n\nسيتم التفعيل خلال *1-2 ساعة*."
                if t(user_id,"ar","en")=="ar" else
                f"⏳ *Payment submitted!*\n\nPayment ID: `{pay_id}`\n\nActivation within *1-2 hours*.")
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=home_keyboard(user_id))


async def _show_plans(target, user_id, edit=False):
    if t(user_id,"ar","en") == "ar":
        text = (f"💎 *اشتراك {BOT_NAME} برو*\n\n🆓 *مجاني:* 4 توصيات فقط\n\n"
                f"⭐ *برو:*\n• توصيات غير محدودة\n• تحليل 3 فريمات\n• جميع الأزواج\n\n*اختر خطة:*")
        buttons = [
            [InlineKeyboardButton(f"⭐ شهر — {PRICE_MONTHLY}$",              callback_data="buy_pro_1m")],
            [InlineKeyboardButton(f"💰 3 أشهر — {PRICE_3MONTH}$ (وفّر 15$)", callback_data="buy_pro_3m")],
        ]
    else:
        text = (f"💎 *{BOT_NAME} Pro*\n\n🆓 *Free:* 4 signals only\n\n"
                f"⭐ *Pro:*\n• Unlimited signals\n• 3-TF analysis\n• All pairs\n\n*Choose plan:*")
        buttons = [
            [InlineKeyboardButton(f"⭐ 1 Month — ${PRICE_MONTHLY}",           callback_data="buy_pro_1m")],
            [InlineKeyboardButton(f"💰 3 Months — ${PRICE_3MONTH} (save $15)",callback_data="buy_pro_3m")],
        ]
    keyboard = home_keyboard(user_id, buttons)
    if edit:
        await target.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
    else:
        await target.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


# ── أوامر الإدارة — محمية بـ ADMIN_IDS ───────────────────────────

async def confirm_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return  # يتجاهل أي شخص آخر
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
        exp  = datetime.datetime.now() + datetime.timedelta(days=months*30)
        lang = db.get_lang(user_id)
        msg  = (f"🎉 *تم تفعيل برو!*\n✅ غير محدود\n📅 حتى: *{exp.strftime('%d/%m/%Y')}*"
                if lang=="ar" else
                f"🎉 *Pro activated!*\n✅ Unlimited\n📅 Until: *{exp.strftime('%d/%m/%Y')}*")
        await ctx.bot.send_message(user_id, msg, parse_mode="Markdown")
    except Exception:
        pass
    await update.message.reply_text(f"✅ Confirmed. User {user_id} activated ({months} months).")


async def adddays_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return  # يتجاهل أي شخص آخر
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text("Usage: /adddays {user_id} {days}")
        return
    try:
        user_id, days = int(args[0]), int(args[1])
    except ValueError:
        await update.message.reply_text("Invalid args.")
        return
    success = db.add_days(user_id, days)
    if not success:
        await update.message.reply_text(f"❌ User {user_id} not found.")
        return
    row = db.get_user(user_id)
    exp = datetime.datetime.fromtimestamp(row["plan_expires"]).strftime("%d/%m/%Y")
    try:
        lang = db.get_lang(user_id)
        msg  = (f"🎁 *تم إضافة {days} يوم مجاني!*\n📅 صالح حتى: *{exp}*"
                if lang=="ar" else
                f"🎁 *{days} free days added!*\n📅 Valid until: *{exp}*")
        await ctx.bot.send_message(user_id, msg, parse_mode="Markdown")
    except Exception:
        pass
    await update.message.reply_text(f"✅ Added {days} days to {user_id}. Expires: {exp}")


async def userinfo_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return  # يتجاهل أي شخص آخر
    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: /userinfo {user_id or username}")
        return
    row = db.search_user(args[0])
    if not row:
        await update.message.reply_text(f"❌ User '{args[0]}' not found.")
        return
    pro    = row["plan"] == "pro" and row["plan_expires"] > time.time()
    exp    = datetime.datetime.fromtimestamp(row["plan_expires"]).strftime("%d/%m/%Y") if row["plan_expires"] else "—"
    joined = datetime.datetime.fromtimestamp(row["joined"]).strftime("%d/%m/%Y") if row["joined"] else "—"
    text   = (
        f"👤 *معلومات المستخدم*\n\n"
        f"ID: `{row['id']}`\n"
        f"Username: @{row['username'] or '—'}\n"
        f"الاسم: {row['name'] or '—'}\n"
        f"اللغة: {row['lang']}\n"
        f"انضم: {joined}\n\n"
        f"الخطة: *{'⭐ برو' if pro else '🆓 مجاني'}*\n"
        f"تنتهي: {exp}\n"
        f"مجانية استُخدمت: {row['free_used']}/4\n"
        f"إجمالي التوصيات: {row['total_signals']}\n\n"
        f"*أوامر:*\n"
        f"`/adddays {row['id']} 30`\n"
        f"`/confirm 0 {row['id']} 1`"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def users_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return  # يتجاهل أي شخص آخر
    rows  = db.get_all_users(20)
    now   = time.time()
    lines = [f"👥 *آخر {len(rows)} مستخدم:*\n"]
    for r in rows:
        pro   = "⭐" if (r["plan"]=="pro" and r["plan_expires"] > now) else "🆓"
        uname = f"@{r['username']}" if r["username"] else r["name"] or "—"
        lines.append(f"{pro} `{r['id']}` — {uname} — {r['total_signals']} توصية")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def stats_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return  # يتجاهل أي شخص آخر
    pending = db.pending_payments()
    text = (
        f"📊 *إحصائيات الإدارة*\n\n"
        f"المستخدمون: `{db.all_users_count()}`\n"
        f"المشتركون برو: `{db.pro_users_count()}`\n"
        f"إجمالي التوصيات: `{db.total_signals_count()}`\n"
        f"مدفوعات معلقة: `{len(pending)}`\n\n"
        f"*الأوامر:*\n"
        f"`/users` — آخر المستخدمين\n"
        f"`/userinfo {{id}}` — معلومات مستخدم\n"
        f"`/adddays {{id}} {{days}}` — أيام مجانية\n"
        f"`/confirm {{pay_id}} {{user_id}} {{months}}` — تأكيد دفع"
    )
    await update.message.reply_text(text, parse_mode="Markdown")
