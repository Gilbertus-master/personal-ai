#!/usr/bin/env bash
# sync_corporate_data.sh — Hourly corporate data sync: email, Teams, embed, extract.
# Designed for cron: sets PATH, handles errors gracefully, idempotent.
#
# Each step runs independently — a failure in one does not stop the rest.

cd "$(dirname "$0")/.."
PROJECT_DIR="$(pwd)"

# --- Cron-safe environment ---
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PROJECT_DIR/.venv/bin"
export TIKTOKEN_CACHE_DIR="/tmp/tiktoken_cache"

# Load .env for Graph API credentials, DB connection, etc.
set -a
[ -f "$PROJECT_DIR/.env" ] && source "$PROJECT_DIR/.env"
set +a

LOG="$PROJECT_DIR/logs/sync_corporate_data.log"
mkdir -p "$PROJECT_DIR/logs"

TS() { date '+%F %T'; }

echo "" >> "$LOG"
echo "[$(TS)] ========== Corporate data sync started ==========" >> "$LOG"

# --- 1. Sync inbox email (with attachments, integrated in email_sync.py) ---
echo "[$(TS)] Step 1/5: Syncing inbox email" >> "$LOG"
"$PROJECT_DIR/.venv/bin/python" -m app.ingestion.graph_api.email_sync \
    --folder inbox >> "$LOG" 2>&1 || {
    echo "[$(TS)] WARNING: Inbox sync failed (exit $?)" >> "$LOG"
}

# --- 2. Sync sent items ---
echo "[$(TS)] Step 2/5: Syncing sent items" >> "$LOG"
"$PROJECT_DIR/.venv/bin/python" -m app.ingestion.graph_api.email_sync \
    --folder sentitems --source-name corporate_email_sent >> "$LOG" 2>&1 || {
    echo "[$(TS)] WARNING: Sent items sync failed (exit $?)" >> "$LOG"
}

# --- 3. Sync Teams chats (uses /me/ endpoint when MS_GRAPH_USER_ID is unset) ---
echo "[$(TS)] Step 3/5: Syncing Teams chats" >> "$LOG"
unset MS_GRAPH_USER_ID  # Force /me/ endpoint for delegated permissions
"$PROJECT_DIR/.venv/bin/python" -m app.ingestion.graph_api.teams_sync >> "$LOG" 2>&1 || {
    echo "[$(TS)] WARNING: Teams sync failed (exit $?)" >> "$LOG"
}

# --- 4. Embed new chunks ---
echo "[$(TS)] Step 4/5: Embedding new chunks" >> "$LOG"
"$PROJECT_DIR/.venv/bin/python" -m app.retrieval.index_chunks \
    --batch-size 100 --limit 500 >> "$LOG" 2>&1 || {
    echo "[$(TS)] WARNING: Embedding failed (exit $?)" >> "$LOG"
}

# --- 5. Entity extraction on new data (50 chunks, Haiku) ---
echo "[$(TS)] Step 5/5: Entity extraction (50 chunks, Haiku)" >> "$LOG"
ANTHROPIC_EXTRACTION_MODEL=claude-haiku-4-5-20251001 \
"$PROJECT_DIR/.venv/bin/python" -m app.extraction.entities \
    --candidates-only 50 >> "$LOG" 2>&1 || {
    echo "[$(TS)] WARNING: Entity extraction failed (exit $?)" >> "$LOG"
}

echo "[$(TS)] ========== Corporate data sync finished ==========" >> "$LOG"
