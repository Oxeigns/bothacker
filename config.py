"""
SINGULARITY-X Configuration File
Fill in your credentials and API keys
"""

class Config:
    # Telegram Bot Credentials (for notifications)
    API_ID = 12345678  # Your Telegram API ID from my.telegram.org
    API_HASH = "your_api_hash_here"  # Your Telegram API Hash
    BOT_TOKEN = "your_bot_token_here"  # Your bot token for sending reports
    LOG_CHAT = -1001234567890  # Chat ID where reports are sent (can be your user ID)
    
    # GitHub Personal Access Tokens (for GitHub API - get from github.com/settings/tokens)
    # Add multiple tokens to rotate and avoid rate limits
    GH_TOKENS = [
        "ghp_your_token_1_here",
        "ghp_your_token_2_here",
        # Add more tokens as needed
    ]
    
    # Optional: GitLab Tokens
    GITLAB_TOKENS = [
        # "glpat-your-gitlab-token",
    ]
    
    # Optional: Custom Webhook for intercepted messages
    WEBHOOK_URL = "https://your-webhook-endpoint.com/telegram-intercept"
    
    # Optional: Proxy settings for anonymity
    PROXIES = [
        # "http://user:pass@proxy:port",
        # "socks5://user:pass@proxy:port",
    ]
