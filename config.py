"""
config.py — Flareposts Bot configuration.
Fill in your keys via environment variables or directly here.
"""

import os
from dotenv import load_dotenv
load_dotenv()

# ── Core ──────────────────────────────────────────────────────────
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "YOUR_BOT_TOKEN")
GROQ_KEY = os.getenv("GROQ_API_KEY", "")

# ── Your crypto wallets (where you receive payments) ─────────────
YOUR_USDT_TRC20  = os.getenv("USDT_TRC20_ADDRESS", "YOUR_TRC20_WALLET")
YOUR_USDT_ERC20  = os.getenv("USDT_ERC20_ADDRESS", "YOUR_ERC20_WALLET")
YOUR_BTC         = os.getenv("BTC_ADDRESS",         "YOUR_BTC_WALLET")
YOUR_ETH         = os.getenv("ETH_ADDRESS",         "YOUR_ETH_WALLET")

# ── Pricing ───────────────────────────────────────────────────────
FREE_USES_PER_MONTH   = 5          # Free tier: 5 generations/month
PRICE_MONTHLY_USDT    = 8          # $8 USDT/month
PRICE_3MONTH_USDT     = 20         # $20 USDT for 3 months (save $4)
PRICE_MONTHLY_BTC     = "0.00009"  # ~$8 worth of BTC (update periodically)

# ── Admin ─────────────────────────────────────────────────────────
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "0").split(",") if x.strip().isdigit()]

# ── Branding ──────────────────────────────────────────────────────
BOT_NAME    = "Flareposts"
BOT_EMOJI   = "⚡"
BOT_VERSION = "1.0.0"

# ── Database ──────────────────────────────────────────────────────
DB_FILE = "flareposts.db"
