"""
SINGULARITY-X Configuration File
Loads credentials from environment variables (Heroku Config Vars / app.json)
"""

import os

class Config:
    # Telegram Bot Credentials (Loaded from environment)
    API_ID = int(os.getenv("API_ID", 0))
    API_HASH = os.getenv("API_HASH", "")
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    LOG_CHAT = int(os.getenv("LOG_CHAT", 0))

    # GitHub Tokens (comma separated in env)
    GH_TOKENS = os.getenv("GH_TOKENS", "").split(",")

    # GitLab Tokens (optional)
    GITLAB_TOKENS = os.getenv("GITLAB_TOKENS", "").split(",")

    # Optional Webhook
    WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")

    # Optional Proxies (comma separated)
    PROXIES = os.getenv("PROXIES", "").split(",")
