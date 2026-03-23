"""
handlers/core.py — /start, /help, and the main content generation flow.
"""

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import database as db
from config import BOT_NAME, BOT_EMOJI, FREE_USES_PER_MONTH


PLATFORM_EMOJIS = {
    "TWITTER":   "🐦",
    "LINKEDIN":  "💼",
    "INSTAGRAM": "📸",
    "YOUTUBE":   "▶️",
    "EMAIL":     "📧",
    "TIKTOK":    "🎵",
}

PLATFORM_NAMES = {
    "TWITTER":   "Twitter / X Thread",
    "LINKEDIN":  "LinkedIn Post",
    "INSTAGRAM": "Instagram Caption",
    "YOUTUBE":   "YouTube Description",
    "EMAIL":     "Email Newsletter",
    "TIKTOK":    "TikTok / Reels Script",
}


async def start_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.ensure_user(user.id, user.username or "", user.full_name or "")

    pro = db.is_pro(user.id)
    used = db.uses_this_month(user.id)
    remaining = max(0, FREE_USES_PER_MONTH - used) if not pro else "∞"

    plan_badge = "⭐ PRO" if pro else f"🆓 Free ({remaining} left this month)"

    text = (
        f"{BOT_EMOJI} *Welcome to {BOT_NAME}!*\n\n"
        f"Turn any content into 6 ready-to-post social media pieces — in 30 seconds.\n\n"
        f"*Just send me:*\n"
        f"🔗 Any article URL\n"
        f"▶️ A YouTube video link\n"
        f"📝 Raw text / notes / ideas\n\n"
        f"*I'll generate:*\n"
        f"🐦 Twitter/X Thread\n"
        f"💼 LinkedIn Post\n"
        f"📸 Instagram Caption\n"
        f"▶️ YouTube Description\n"
        f"📧 Email Newsletter Hook\n"
        f"🎵 TikTok/Reels Script\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"Your plan: *{plan_badge}*"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 Go Pro — $8/mo", callback_data="show_plans")],
        [
            InlineKeyboardButton("📖 How it works", callback_data="how_it_works"),
            InlineKeyboardButton("📊 My stats",     callback_data="my_stats"),
        ]
    ])

    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def help_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        f"📖 *{BOT_NAME} — How to use*\n\n"
        f"*Send anything:*\n"
        f"• A URL → `https://example.com/article`\n"
        f"• A YouTube link → `https://youtube.com/watch?v=...`\n"
        f"• Plain text → just type or paste it\n\n"
        f"*Commands:*\n"
        f"`/start` — Home screen\n"
        f"`/upgrade` — Go Pro\n"
        f"`/status` — Your plan & usage\n"
        f"`/help` — This message\n\n"
        f"*Plans:*\n"
        f"🆓 *Free* — {FREE_USES_PER_MONTH} generations/month\n"
        f"⭐ *Pro* — Unlimited for $8 USDT/month\n"
        f"💰 *3-Month* — $20 USDT (save $4)\n\n"
        f"*Payment:* USDT TRC-20, USDT ERC-20, BTC, ETH\n"
        f"Instant activation after you confirm payment.\n\n"
        f"Questions? Use /support"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def status_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.ensure_user(user.id, user.username or "", user.full_name or "")

    row = db.get_user(user.id)
    pro = db.is_pro(user.id)
    used_month = db.uses_this_month(user.id)
    total = row["total_uses"] if row else 0

    import time
    if pro and row:
        expires_ts = row["plan_expires"]
        import datetime
        expires_str = datetime.datetime.fromtimestamp(expires_ts).strftime("%b %d, %Y")
        plan_text = f"⭐ *Pro* — expires {expires_str}"
    else:
        remaining = max(0, FREE_USES_PER_MONTH - used_month)
        plan_text = f"🆓 *Free* — {remaining}/{FREE_USES_PER_MONTH} uses left this month"

    text = (
        f"📊 *Your Stats*\n\n"
        f"Plan: {plan_text}\n"
        f"This month: `{used_month}` generations\n"
        f"All time: `{total}` generations\n"
    )

    buttons = []
    if not pro:
        buttons.append([InlineKeyboardButton("💎 Upgrade to Pro", callback_data="show_plans")])

    await update.message.reply_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons) if buttons else None
    )


async def generate_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Main handler — triggered when user sends any text/URL."""
    user    = update.effective_user
    text    = update.message.text.strip()

    # Ignore commands
    if text.startswith("/"):
        return

    db.ensure_user(user.id, user.username or "", user.full_name or "")

    # Check usage limit
    pro  = db.is_pro(user.id)
    used = db.uses_this_month(user.id)

    if not pro and used >= FREE_USES_PER_MONTH:
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("💎 Go Pro — Unlimited", callback_data="show_plans")
        ]])
        await update.message.reply_text(
            f"⚠️ *You've used all {FREE_USES_PER_MONTH} free generations this month.*\n\n"
            f"Upgrade to Pro for *unlimited* access — just $8 USDT/month.\n"
            f"Your generations reset on the 1st of each month.",
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
        return

    # Show working indicator
    msg = await update.message.reply_text(
        "⚡ *Forging your content...*\n\n"
        "🔍 Reading source...\n"
        "🤖 Generating 6 posts...\n"
        "_This takes 10-20 seconds_",
        parse_mode="Markdown"
    )

    try:
        from services.ai_engine import generate_content
        result = await generate_content(text)

        # Log the generation
        db.log_generation(user.id, text[:200])

        # Update status message
        source_labels = {"url": "🔗 article", "youtube": "▶️ video", "text": "📝 text"}
        source_label  = source_labels.get(result["source_type"], "content")

        await msg.edit_text(
            f"✅ *Done! Generated from your {source_label}.*\n\n"
            f"Choose which post to see 👇",
            parse_mode="Markdown",
        )

        # Store result in context for the callback
        ctx.user_data["last_result"] = result["platforms"]
        ctx.user_data["last_source"] = text[:100]

        # Show platform selector
        buttons = []
        platforms = list(result["platforms"].keys())
        for i in range(0, len(platforms), 2):
            row = []
            for p in platforms[i:i+2]:
                emoji = PLATFORM_EMOJIS.get(p, "📄")
                row.append(InlineKeyboardButton(
                    f"{emoji} {p.title()}",
                    callback_data=f"show_platform_{p}"
                ))
            buttons.append(row)

        buttons.append([InlineKeyboardButton("📦 Get ALL 6 posts", callback_data="show_all")])

        used_now = db.uses_this_month(user.id)
        footer = (
            f"\n_{'⭐ Pro — Unlimited' if pro else f'Used {used_now}/{FREE_USES_PER_MONTH} this month'}_"
        )

        await update.message.reply_text(
            f"🎯 *Pick a platform:*{footer}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    except ValueError as e:
        await msg.edit_text(f"⚠️ {e}\n\nPlease try a different URL or paste the text directly.")
    except Exception as e:
        await msg.edit_text(
            "❌ Something went wrong generating your content.\n"
            "Please try again in a moment."
        )
        raise


async def platform_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show a specific platform's post."""
    query = update.callback_query
    await query.answer()

    data = query.data

    # Navigation callbacks
    if data == "how_it_works":
        await query.edit_message_text(
            "🔧 *How Flareposts works:*\n\n"
            "1️⃣ Send a URL, YouTube link, or paste text\n"
            "2️⃣ Our AI reads and understands the content\n"
            "3️⃣ It rewrites it natively for each platform\n"
            "4️⃣ You pick the posts you want and copy them\n\n"
            "Each platform post is written differently:\n"
            "• Twitter: punchy threads\n"
            "• LinkedIn: professional storytelling\n"
            "• Instagram: casual + hashtags\n"
            "• YouTube: SEO-optimized description\n"
            "• Email: newsletter hook with CTA\n"
            "• TikTok: spoken script with timing\n\n"
            "Send me anything to try it! 👇",
            parse_mode="Markdown",
        )
        return

    if data == "my_stats":
        user = query.from_user
        row  = db.get_user(user.id)
        pro  = db.is_pro(user.id)
        used = db.uses_this_month(user.id)
        total = row["total_uses"] if row else 0

        remaining = "∞" if pro else max(0, FREE_USES_PER_MONTH - used)
        plan_name = "⭐ Pro" if pro else "🆓 Free"

        await query.edit_message_text(
            f"📊 *Your Stats*\n\n"
            f"Plan: *{plan_name}*\n"
            f"This month: `{used}` generations\n"
            f"Remaining: `{remaining}`\n"
            f"All time: `{total}` generations",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Back", callback_data="back_home")
            ]])
        )
        return

    if data == "back_home":
        await query.delete_message()
        return

    # Platform display
    platforms = ctx.user_data.get("last_result", {})
    if not platforms:
        await query.edit_message_text(
            "⚠️ Session expired. Please send your content again."
        )
        return

    if data == "show_all":
        # Send all 6 posts as separate messages
        await query.edit_message_text("📦 *Sending all 6 posts...*", parse_mode="Markdown")
        for platform, content in platforms.items():
            emoji = PLATFORM_EMOJIS.get(platform, "📄")
            name  = PLATFORM_NAMES.get(platform, platform)
            header = f"{emoji} *{name}*\n{'─'*30}\n"
            # Telegram message limit: 4096 chars
            full_text = header + content
            chunks = [full_text[i:i+4000] for i in range(0, len(full_text), 4000)]
            for chunk in chunks:
                await query.message.reply_text(chunk, parse_mode="Markdown")
        return

    if data.startswith("show_platform_"):
        platform = data.replace("show_platform_", "")
        content  = platforms.get(platform, "Not available.")
        emoji    = PLATFORM_EMOJIS.get(platform, "📄")
        name     = PLATFORM_NAMES.get(platform, platform)

        header = f"{emoji} *{name}*\n{'─'*30}\n"
        full_text = header + content

        # Build back + copy navigation
        all_buttons = []
        for p, c in platforms.items():
            e = PLATFORM_EMOJIS.get(p, "📄")
            all_buttons.append(
                InlineKeyboardButton(f"{e}", callback_data=f"show_platform_{p}")
            )

        keyboard = InlineKeyboardMarkup([
            all_buttons,
            [InlineKeyboardButton("📦 Get ALL 6", callback_data="show_all")]
        ])

        chunks = [full_text[i:i+4000] for i in range(0, len(full_text), 4000)]
        await query.edit_message_text(
            chunks[0], parse_mode="Markdown", reply_markup=keyboard
        )
        for chunk in chunks[1:]:
            await query.message.reply_text(chunk, parse_mode="Markdown")
