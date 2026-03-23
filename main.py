import logging
from telegram.ext import (
    Application, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters
)
from config import TELEGRAM_TOKEN
import database as db
from handlers.core    import start_handler, callback_handler
from handlers.payment import upgrade_handler, plans_callback, confirm_cmd, stats_cmd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.FileHandler("tradeai.log"), logging.StreamHandler()]
)

def main():
    db.init()
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start",   start_handler))
    app.add_handler(CommandHandler("upgrade", upgrade_handler))
    app.add_handler(CommandHandler("confirm", confirm_cmd))
    app.add_handler(CommandHandler("stats",   stats_cmd))

    # جميع الأزرار — الدفع أولاً لأن لديه patterns أكثر تحديداً
    app.add_handler(CallbackQueryHandler(plans_callback,
        pattern="^(show_plans|buy_|paycoin_|paid_)"))
    app.add_handler(CallbackQueryHandler(callback_handler))

    logging.info("🚀 TradeAI Bot started.")
    app.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    main()
