import os
from dotenv import load_dotenv

load_dotenv()

def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value

TELEGRAM_API_ID = int(required("TELEGRAM_API_ID"))
TELEGRAM_API_HASH = required("TELEGRAM_API_HASH")
TELEGRAM_BOT_TOKEN = required("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = required("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")

REPORT_CHAT_ID = int(os.getenv("REPORT_CHAT_ID", "0"))

raw_chats = os.getenv("TELEGRAM_CHATS", "")
TELEGRAM_CHATS = [
    x.strip().lower().replace("@", "")
    for x in raw_chats.split(",")
    if x.strip()
]

BACKFILL_MESSAGES = int(os.getenv("BACKFILL_MESSAGES", "20"))

# Optional. Example: +919876543210
# If empty, the application asks interactively.
TELEGRAM_PHONE_NUMBER = os.getenv("TELEGRAM_PHONE_NUMBER", "").strip()

MEDIA_DIR = "media"
DB_PATH = "data/messages.db"
