[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/Oxeigns/bothacker.git)


# SINGULARITY-X 24/7 Setup Guide

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install telethon aiohttp aiolimiter aiosqlite aiofiles psutil
```

### 2. Create Config
```bash
cp config_template.py config.py
nano config.py
```

Fill in:
- `API_ID` & `API_HASH` - from my.telegram.org
- `BOT_TOKEN` - from @BotFather
- `LOG_CHAT` - your group/channel ID
- `GH_TOKENS` - GitHub personal access tokens

### 3. Test Run
```bash
python3 singularity_x_ultimate.py
```

## 🔄 24/7 Operation Setup

### Method 1: Systemd Service (Recommended)

```bash
# Copy service file
sudo cp singularity.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start on boot
sudo systemctl enable singularity

# Start service
sudo systemctl start singularity

# Check status
sudo systemctl status singularity

# View logs
sudo journalctl -u singularity -f
```

### Method 2: Screen/Tmux Session

```bash
# Using screen
screen -S singularity
python3 singularity_x_ultimate.py
# Ctrl+A, D to detach

# Reattach
screen -r singularity
```

### Method 3: PM2 (Node.js style)

```bash
npm install -g pm2
pm2 start singularity_x_ultimate.py --name singularity
pm2 save
pm2 startup
```

## 📊 Monitoring

### Real-time Logs
```bash
tail -f singularity.log
```

### Check Database
```bash
sqlite3 singularity_24x7.db "SELECT * FROM hits ORDER BY hit_time DESC LIMIT 10;"
```

### Health Monitor Script
```bash
python3 monitor.py &
```

## 🔧 Configuration Tuning

### High-Performance Mode
Edit `ScanConfig` in the script:
```python
REQUESTS_PER_SECOND = 10000
MAX_CONCURRENT = 1000
BATCH_SIZE = 100
```

### Conservative Mode (for VPS)
```python
REQUESTS_PER_SECOND = 1000
MAX_CONCURRENT = 100
BATCH_SIZE = 25
```

## 🛡️ Reliability Features

### Auto-Recovery
- Circuit breaker for failed APIs
- Automatic retry with exponential backoff
- Memory monitoring and alerts
- Stall detection and recovery

### Health Monitoring
- Database health logs every 30 seconds
- Telegram stats every 5 minutes
- Admin alerts for critical issues
- Self-healing on errors

### Data Persistence
- SQLite database with WAL mode
- Async operations for performance
- Automatic report saving
- No data loss on crash

## 🔔 Notifications

You'll receive Telegram notifications for:
- ✅ Live hits (instant)
- 📊 Stats updates (every 5 min)
- ⚠️ Admin alerts (errors/high memory/stalls)
- 🚀 Startup/shutdown events

## 📁 File Structure

```
/home/user/
├── singularity_x_ultimate.py  # Main scanner
├── config.py                   # Your config
├── singularity_24x7.db         # SQLite database
├── singularity.log             # Runtime logs
├── reports/                    # JSON reports
│   ├── botname_1234567890.json
│   └── ...
└── singularity_session.session # Telegram session
```

## 🐛 Troubleshooting

### High Memory Usage
```bash
# Reduce memory limit in config
MEMORY_LIMIT_MB = 1024

# Or restart service
sudo systemctl restart singularity
```

### Rate Limiting
- Add more GitHub tokens
- Reduce REQUESTS_PER_SECOND
- Increase retry delays

### Telegram Flood Wait
- Bot automatically handles waits
- Reduce notification frequency
- Use multiple bot tokens if needed

### Database Locked
```bash
# Reset database permissions
chmod 664 singularity_24x7.db
```

## 📈 Performance Tips

1. **Use multiple GitHub tokens** - Rotate to avoid rate limits
2. **Run on VPS/cloud** - Stable internet, 24/7 uptime
3. **SSD storage** - Faster database operations
4. **2GB+ RAM** - For optimal performance
5. **Multiple workers** - Already configured (2 realtime + 3 search)

## 🔒 Security

- Keep `config.py` secure (chmod 600)
- Use environment variables for tokens
- Don't commit tokens to git
- Regular database backups

## 📞 Support

Check logs:
```bash
tail -100 singularity.log
grep ERROR singularity.log
```

Database queries:
```bash
sqlite3 singularity_24x7.db
.tables
SELECT * FROM tokens WHERE validated=1;
```
