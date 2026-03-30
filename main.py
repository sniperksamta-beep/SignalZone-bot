import logging
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler
)
from config import TELEGRAM_TOKEN
import database as db
from handlers.core    import start_handler, callback_handler
from handlers.payment import (
    upgrade_handler, plans_callback,
    confirm_cmd, adddays_cmd, userinfo_cmd, users_cmd, stats_cmd,
    broadcast_cmd
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.FileHandler("tradeai.log"), logging.StreamHandler()]
)

def main():
    db.init()
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # أوامر المستخدمين
    app.add_handler(CommandHandler("start",    start_handler))
    app.add_handler(CommandHandler("upgrade",  upgrade_handler))

    # أوامر الإدارة
    app.add_handler(CommandHandler("confirm",  confirm_cmd))
    app.add_handler(CommandHandler("adddays",  adddays_cmd))
    app.add_handler(CommandHandler("userinfo", userinfo_cmd))
    app.add_handler(CommandHandler("users",    users_cmd))
    app.add_handler(CommandHandler("stats",    stats_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))

    # الأزرار
    app.add_handler(CallbackQueryHandler(plans_callback,
        pattern="^(show_plans|buy_|paycoin_|paid_)"))
    app.add_handler(CallbackQueryHandler(callback_handler))

    logging.info("🚀 SignalsZone Bot started.")
    app.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    main()
