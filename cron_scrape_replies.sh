#!/usr/bin/env bash
# Cron wrapper for reply scraping
# Usage:
#   ./cron_scrape_replies.sh          # incremental (daily)
#   ./cron_scrape_replies.sh backfill  # continue backfill (older messages)
set -euo pipefail

cd /home/ubuntu/confessit-scraper
source venv/bin/activate

LOG_DIR="logs"
mkdir -p "$LOG_DIR"
TIMESTAMP=$(date +"%Y-%m-%d_%H:%M:%S")
LOG_FILE="$LOG_DIR/reply_scrape_cron_$TIMESTAMP.log"
MODE="${1:-incremental}"

if [ "$MODE" = "backfill" ]; then
    python3 scrape_replies.py --backfill --log-level INFO > "$LOG_FILE" 2>&1
else
    python3 scrape_replies.py --log-level INFO > "$LOG_FILE" 2>&1
fi

SAVED=$(grep -oP 'Saved:\s+\K\d+' "$LOG_FILE" | tail -1)
TOTAL=$(python3 -c "
import sqlite3
c=sqlite3.connect('data/messages.db')
print(c.execute('SELECT COUNT(*) FROM replies').fetchone()[0])
c.close()
")
echo "[reply-scrape] $TIMESTAMP — mode=$MODE saved=$SAVED total=$TOTAL"