"""
Configuration settings for NEPSE Algorithmic Screener & Automated Scheduler.
"""
from pathlib import Path
import datetime

# Paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "nepse_cache.db"
HOLIDAYS_FILE = DATA_DIR / "nepal_holidays.json"
EXPORTS_DIR = DATA_DIR / "exports"
EXPORTS_DIR.mkdir(exist_ok=True)

# Default Watchlist
DEFAULT_WATCHLIST = ["NHPC", "RSML", "SHIVM", "SARBTM"]

# Indicator Parameters
RSI_PERIOD = 14
RSI_OVERSOLD = 30.0
RSI_OVERBOUGHT = 70.0
SMA_SHORT_PERIOD = 50
SMA_LONG_PERIOD = 200
VOLUME_WINDOW = 20
VOLUME_STD_DEV_MULTIPLIER = 2.0
MIN_LIQUIDITY_VOLUME = 5000  # Avoid odd-lot / illiquid noise

# Scraper & Network Settings
MAX_RETRIES = 5
BASE_RETRY_DELAY = 1.5
MAX_RETRY_DELAY = 30.0
RATE_LIMIT_TOKENS_PER_SEC = 1.0
RATE_LIMIT_BURST = 5
REQUEST_TIMEOUT = 12

# Market Hours & Dynamic Session Scheduling
# Nepal Standard Time (UTC+5:45)
NPT_TIMEZONE = datetime.timezone(datetime.timedelta(hours=5, minutes=45), name="NPT")

# Market Session Timings
# Daily market check trigger: 11:00 AM NST
SESSION_START_HOUR = 11
SESSION_START_MINUTE = 0

# Standard NEPSE market closing time: 3:00 PM NST (15:00)
SESSION_CLOSE_HOUR = 15
SESSION_CLOSE_MINUTE = 0

# Polling frequency while the market is live (in minutes)
LIVE_POLL_INTERVAL_MINUTES = 5

# Active Trading Days (0 = Mon, 1 = Tue, 2 = Wed, 3 = Thu, 4 = Fri)
ACTIVE_TRADING_DAYS = [0, 1, 2, 3, 4]

# GitHub Repository Sync Settings
ENABLE_GIT_SYNC = True
GIT_COMMIT_DATABASE = True
GIT_COMMIT_CSV_EXPORT = True
GIT_BRANCH = "main"

# GUI Settings
APP_TITLE = "NEPSE Algorithmic Screener & Technical Dashboard"
WINDOW_WIDTH = 1450
WINDOW_HEIGHT = 880
SIGNAL_HIGHLIGHT_COLOR = "#d4edda"
SIGNAL_TEXT_COLOR = "#155724"

# Cloud Sync Configuration (GitHub Raw Database URL)
GITHUB_RAW_DB_URL = "https://raw.githubusercontent.com/August1879/NEPSE-Algorithmic-Screener/main/data/nepse_cache.db"
AUTO_SYNC_GITHUB_ON_STARTUP = True
