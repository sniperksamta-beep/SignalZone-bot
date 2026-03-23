import os
from dotenv import load_dotenv
load_dotenv()

TELEGRAM_TOKEN    = os.getenv("TELEGRAM_TOKEN", "")
GROQ_KEY          = os.getenv("GROQ_API_KEY", "")

YOUR_USDT_TRC20   = os.getenv("USDT_TRC20_ADDRESS", "")
YOUR_USDT_ERC20   = os.getenv("USDT_ERC20_ADDRESS", "")
YOUR_BTC          = os.getenv("BTC_ADDRESS", "")

ADMIN_IDS         = [int(x) for x in os.getenv("ADMIN_IDS", "0").split(",") if x.strip().isdigit()]

FREE_SIGNALS      = 4        # توصيات مجانية للمستخدم الجديد
PRICE_MONTHLY     = 35       # دولار شهرياً
PRICE_3MONTH      = 90       # 3 أشهر

BOT_NAME          = "SignalsZone"
DB_FILE           = "tradeai.db"

# الأزواج المدعومة
PAIRS = {
    "XAUUSD": {"name_ar": "ذهب / دولار",       "name_en": "Gold / USD",        "emoji": "🥇", "yahoo": "GC=F"},
    "XAGUSD": {"name_ar": "فضة / دولار",        "name_en": "Silver / USD",      "emoji": "🥈", "yahoo": "SI=F"},
    "BTCUSD": {"name_ar": "بيتكوين / دولار",   "name_en": "Bitcoin / USD",     "emoji": "₿",  "yahoo": "BTC-USD"},
    "ETHUSD": {"name_ar": "إيثيريوم / دولار",  "name_en": "Ethereum / USD",    "emoji": "Ξ",  "yahoo": "ETH-USD"},
    "EURUSD": {"name_ar": "يورو / دولار",       "name_en": "EUR / USD",         "emoji": "💶", "yahoo": "EURUSD=X"},
    "USDJPY": {"name_ar": "دولار / ين",         "name_en": "USD / JPY",         "emoji": "💴", "yahoo": "JPY=X"},
}

# الفريمات المدعومة
TIMEFRAMES = {
    "15m":  {"label_ar": "15 دقيقة",  "label_en": "15 Minutes",  "yf_interval": "15m",  "yf_period": "5d"},
    "1h":   {"label_ar": "ساعة",      "label_en": "1 Hour",      "yf_interval": "1h",   "yf_period": "1mo"},
    "4h":   {"label_ar": "4 ساعات",   "label_en": "4 Hours",     "yf_interval": "1h",   "yf_period": "1mo"},
    "1d":   {"label_ar": "يومي",      "label_en": "Daily",       "yf_interval": "1d",   "yf_period": "6mo"},
}
