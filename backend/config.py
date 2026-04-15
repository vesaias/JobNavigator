"""Loads .env secrets only. All other config lives in the settings DB table."""
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID", "")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET", "")
GMAIL_REFRESH_TOKEN = os.getenv("GMAIL_REFRESH_TOKEN", "")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://jobnavigator:password@db:5432/jobnavigator")
INITIAL_API_KEY = os.getenv("INITIAL_API_KEY", "change-me-on-first-login")
