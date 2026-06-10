#!/usr/bin/env bash
# Weekly end-to-end refresh: scrape posts -> scrape replies -> refresh
# reaction counts. Stats endpoints (/api/stats, /api/insights,
# /api/landscape) compute live from the DB with a 1h cache, so they pick
# up the new data automatically.
#
# Safe to run manually:  ./scripts/weekly_refresh.sh
# Overlap-safe: uses flock on a lockfile; a second invocation exits
# immediately instead of queuing.
set -uo pipefail

REPO_DIR="/home/ubuntu/confessit-scraper"
LOCK_FILE="$REPO_DIR/logs/weekly_refresh.lock"
LOG_DIR="$REPO_DIR/logs"
TIMESTAMP=$(date +"%Y-%m-%d_%H%M%S")
LOG_FILE="$LOG_DIR/weekly_refresh_$TIMESTAMP.log"

mkdir -p "$LOG_DIR"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    echo "[weekly-refresh] $TIMESTAMP — another run is in progress, exiting" >&2
    exit 0
fi

cd "$REPO_DIR"
PY="$REPO_DIR/venv/bin/python3"

log() { echo "[$(date +'%H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

run_step() {
    local name="$1"; shift
    log "── step: $name"
    if "$@" >> "$LOG_FILE" 2>&1; then
        log "── step: $name OK"
    else
        log "── step: $name FAILED (exit $?) — continuing"
        FAILED_STEPS="${FAILED_STEPS:-}$name "
    fi
}

FAILED_STEPS=""
log "weekly refresh starting"

# 1. New posts since last scrape
run_step "scrape-posts"   "$PY" scrape.py --log-level INFO

# 2. Incremental reply scrape
run_step "scrape-replies" "$PY" scrape_replies.py --log-level INFO

# 3. Refresh engagement counts (reactions/forwards drift on older posts)
run_step "refresh-reactions" "$PY" refresh_reactions.py --log-level INFO

# 4. Refresh embeddings for new posts, if a refresh script exists
#    (added by the semantic-search feature; no-op until then)
if [ -f "$REPO_DIR/refresh_embeddings.py" ]; then
    run_step "refresh-embeddings" "$PY" refresh_embeddings.py
fi

TOTAL=$("$PY" - <<'EOF'
import sqlite3
c = sqlite3.connect("data/messages.db")
posts = c.execute("SELECT COUNT(*) FROM messages WHERE is_reply=0").fetchone()[0]
replies = c.execute("SELECT COUNT(*) FROM replies").fetchone()[0]
print(f"posts={posts} replies={replies}")
EOF
)
log "db totals: $TOTAL"

# Keep the last 12 weekly logs
ls -1t "$LOG_DIR"/weekly_refresh_*.log 2>/dev/null | tail -n +13 | xargs -r rm --

if [ -n "$FAILED_STEPS" ]; then
    log "weekly refresh finished WITH FAILURES: $FAILED_STEPS"
    exit 1
fi
log "weekly refresh finished OK"
