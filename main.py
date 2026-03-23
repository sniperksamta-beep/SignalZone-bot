"""
main.py — Flareposts Bot entry point.
"""

import logging
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters
)

from config import TELEGRAM_TOKEN
import database as db
from handlers.core import (
    start_handler, help_handler, status_handler,
    generate_handler, platform_callback
)
from handlers.payment import (
    upgrade_handler, show_plans_callback,
    confirm_payment_cmd, admin_stats_cmd
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("flareposts.log"),
        logging.StreamHandler(),
    ]
)

def main():
    db.init()

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start",   start_handler))
    app.add_handler(CommandHandler("help",    help_handler))
    app.add_handler(CommandHandler("status",  status_handler))
    app.add_handler(CommandHandler("upgrade", upgrade_handler))

    # Admin commands
    app.add_handler(CommandHandler("confirm", confirm_payment_cmd))
    app.add_handler(CommandHandler("stats",   admin_stats_cmd))

    # Callbacks (inline buttons)
    app.add_handler(CallbackQueryHandler(show_plans_callback,
        pattern="^(show_plans|buy_|pay_coin_|paid_)"))
    app.add_handler(CallbackQueryHandler(platform_callback,
        pattern="^(show_platform_|show_all|how_it_works|my_stats|back_home)"))

    # Main: any text message triggers generation
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, generate_handler))

    logging.info("🚀 Flareposts Bot started.")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
