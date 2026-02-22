#!/usr/bin/env python3
"""
Singularity-X Monitor
Monitor scanner health and send alerts
"""

import subprocess
import time
import sys
import os
from datetime import datetime

def check_process():
    """Check if scanner is running"""
    try:
        result = subprocess.run(['pgrep', '-f', 'singularity_x_ultimate.py'], 
                              capture_output=True, text=True)
        return result.returncode == 0
    except:
        return False

def get_stats():
    """Get recent stats from log"""
    try:
        with open('singularity.log', 'r') as f:
            lines = f.readlines()
            # Get last 10 lines with stats
            recent = [l for l in lines if 'STATS' in l or 'HIT' in l][-10:]
            return recent
    except:
        return []

def restart_service():
    """Restart the scanner"""
    print(f"[{datetime.now()}] Restarting service...")
    os.system('systemctl restart singularity || pkill -f singularity_x_ultimate.py && python3 singularity_x_ultimate.py &')

def main():
    print(f"[{datetime.now()}] Singularity-X Monitor started")
    
    fail_count = 0
    
    while True:
        time.sleep(60)  # Check every minute
        
        if not check_process():
            fail_count += 1
            print(f"[{datetime.now()}] Process not running (fail {fail_count}/3)")
            
            if fail_count >= 3:
                restart_service()
                fail_count = 0
        else:
            fail_count = 0
            stats = get_stats()
            if stats:
                print(f"[{datetime.now()}] Scanner active - Last: {stats[-1].strip()}")

if __name__ == "__main__":
    main()
