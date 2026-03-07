import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
PORTAL_BASE_URL = os.getenv(
    "PORTAL_BASE_URL",
    "https://sandiego.hylandcloud.com/211agendaonlinecouncil",
)
DATABASE_PATH = os.getenv("DATABASE_PATH", "advocacy_bot.db")
SCRAPE_INTERVAL_MINUTES = int(os.getenv("SCRAPE_INTERVAL_MINUTES", "240"))  # 4 hours default
REMINDER_CHECK_MINUTES = int(os.getenv("REMINDER_CHECK_MINUTES", "60"))
REQUEST_DELAY_SECONDS = float(os.getenv("REQUEST_DELAY_SECONDS", "2"))
REQUEST_TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))
