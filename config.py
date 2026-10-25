import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Automatically use persistent /data volume on Fly.io / Render / Railway if mounted
DEFAULT_DB_DIR = Path("/data") if Path("/data").exists() and os.access("/data", os.W_OK) else BASE_DIR

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dsp_owner_persistent_secret_key_6767_v2")
    DATABASE_PATH = os.environ.get("DATABASE_PATH", str(DEFAULT_DB_DIR / "platform.db"))
    DISCORD_CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID", "")
    DISCORD_CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET", "")
    DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
    DISCORD_REDIRECT_URI = os.environ.get("DISCORD_REDIRECT_URI", "http://127.0.0.1:5000/api/auth/discord/callback")
    PAYMENT_WEBHOOK_SECRET = os.environ.get("PAYMENT_WEBHOOK_SECRET", "whsec_test_secret_key_6767")
    ENABLE_BACKGROUND_WORKER = os.environ.get("ENABLE_BACKGROUND_WORKER", "true").lower() == "true"
    HOST = os.environ.get("HOST", "0.0.0.0")
    PORT = int(os.environ.get("PORT", "5000"))
    DEBUG = os.environ.get("DEBUG", "false").lower() == "true"
