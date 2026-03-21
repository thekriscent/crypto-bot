import os


MARKET = {
    "exchange_code": "paper",
    "exchange_name": "Paper Metals Feed",
    "symbol": "XAUUSD",
    "base_asset": "XAU",
    "quote_asset": "USD",
}

LOG_FILE = "xauusd_bot_log.json"
DB_FILE = "xauusd_bot.db"

SCAN_INTERVAL = 5
COOLDOWN_SECONDS = 120

WINDOWS = [60, 180, 300]
CHECKPOINTS = [60, 180, 300]
CONTEXT_HISTORY_SECONDS = (24 * 60 * 60) + 60

# XAU-specific session placeholders. Adjust these once the live feed and
# execution schedule are finalized.
SESSIONS = [
    {"name": "asia", "start_utc": "22:00", "end_utc": "07:00"},
    {"name": "london", "start_utc": "07:00", "end_utc": "16:00"},
    {"name": "new_york", "start_utc": "12:00", "end_utc": "21:00"},
]

# Placeholder thresholds only. These are intentionally not tuned to gold yet.
THRESHOLDS = {
    "early_score": 3,
    "confirmed_score": 5,
    "pullback_score": 3,
    "move_1m_up_strong": 0.0004,
    "move_1m_up_soft": 0.0002,
    "move_1m_down_strong": -0.0004,
    "move_1m_down_soft": -0.0002,
    "move_3m_up_strong": 0.0008,
    "move_3m_up_soft": 0.0004,
    "move_3m_down_strong": -0.0008,
    "move_3m_down_soft": -0.0004,
    "move_5m_up_strong": 0.0012,
    "move_5m_up_soft": 0.0008,
    "move_5m_down_strong": -0.0012,
    "move_5m_down_soft": -0.0008,
}

# A production-grade XAUUSD data provider can be swapped in here later without
# changing the rest of the bot scaffold.
PRICE_SOURCE_URLS = [
    "https://api.gold-api.com/price/XAU",
    "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1m&range=1d",
]
DEMO_PRICE = os.getenv("XAUUSD_DEMO_PRICE")
SIMULATE_PRICE = os.getenv("XAUUSD_SIMULATE") == "1"
SIMULATION_BASE_PRICE = float(os.getenv("XAUUSD_SIMULATION_BASE_PRICE", "2350"))
