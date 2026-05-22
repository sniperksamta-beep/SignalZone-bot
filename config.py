import os
from dotenv import load_dotenv
load_dotenv()

TELEGRAM_TOKEN    = os.getenv("TELEGRAM_TOKEN", "")
GROQ_KEY          = os.getenv("GROQ_API_KEY", "")

YOUR_USDT_TRC20   = os.getenv("USDT_TRC20_ADDRESS", "")
YOUR_USDT_ERC20   = os.getenv("USDT_ERC20_ADDRESS", "")
YOUR_BTC          = os.getenv("BTC_ADDRESS", "")
YOUR_ETH          = os.getenv("ETH_ADDRESS", "")
YOUR_BNB          = os.getenv("BNB_ADDRESS", "")
YOUR_SOL          = os.getenv("SOL_ADDRESS", "")

ADMIN_IDS         = [int(x) for x in os.getenv("ADMIN_IDS", "0").split(",") if x.strip().isdigit()]

# حساب الدعم الفني — ضع يوزرنيم تيليغرام الخاص بك
SUPPORT_USERNAME  = os.getenv("SUPPORT_USERNAME", "YourUsername")

FREE_SIGNALS      = 4
PRICE_MONTHLY     = 35
PRICE_3MONTH      = 90

BOT_NAME          = "SignalsZone"
DB_FILE           = "tradeai.db"

PAIRS = {
    "XAUUSD": {"name_ar": "ذهب / دولار",      "name_en": "Gold / USD",       "emoji": "🥇", "yahoo": "XAUUSD=X"},
    "BTCUSD": {"name_ar": "بيتكوين / دولار",  "name_en": "Bitcoin / USD",    "emoji": "₿",  "yahoo": "BTC-USD"},
    "ETHUSD": {"name_ar": "إيثيريوم / دولار",      "name_en": "Ethereum / USD",   "emoji": "🔷",  "yahoo": "ETH-USD"},
    "EURUSD": {"name_ar": "يورو / دولار",      "name_en": "EUR / USD",        "emoji": "💶", "yahoo": "EURUSD=X"},
    "USDJPY": {"name_ar": "دولار / ين",        "name_en": "USD / JPY",        "emoji": "💴", "yahoo": "USDJPY=X"},
}

TIMEFRAMES = {
    "5m":  {"label_ar": "5 دقائق",  "label_en": "5 Minutes",  "yf_interval": "5m",  "yf_period": "1d"},
    "15m": {"label_ar": "15 دقيقة", "label_en": "15 Minutes", "yf_interval": "15m", "yf_period": "5d"},
    "1h":  {"label_ar": "ساعة",     "label_en": "1 Hour",     "yf_interval": "1h",  "yf_period": "1mo"},
    "4h":  {"label_ar": "4 ساعات",  "label_en": "4 Hours",    "yf_interval": "1h",  "yf_period": "1mo"},
    "1d":  {"label_ar": "يومي",     "label_en": "Daily",      "yf_interval": "1d",  "yf_period": "6mo"},
}
