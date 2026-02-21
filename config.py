import os

class Config:
    # Heroku Config Vars mein comma (,) se 50 tokens dalo
    GH_TOKENS = os.environ.get("GH_TOKENS", "").split(",")
    API_ID = int(os.environ.get("API_ID", "35335474"))
    API_HASH = os.environ.get("API_HASH", "65c9d8d32a75ba9af8cc401d940b5957")
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "") # Tera Log Bot
    LOG_CHAT = int(os.environ.get("LOG_CHAT", "-1003577257855"))
