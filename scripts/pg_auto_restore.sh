#!/usr/bin/env bash
# pg_auto_restore.sh — Safety guard: detects empty Postgres and restores from latest backup.
# Designed to run after Docker Compose startup (e.g. via cron @reboot or manually).
set -euo pipefail

cd "$(dirname "$0")/.."

CONTAINER="gilbertus-postgres"
DB_USER="${POSTGRES_USER:-gilbertus}"
DB_NAME="${POSTGRES_DB:-gilbertus}"
BACKUP_BASE="backups/db"
LOG_FILE="backups/auto_restore.log"

log() {
    echo "[$(date '+%F %T')] $*" | tee -a "$LOG_FILE"
}

# 1. Wait for Postgres to accept connections (max 60s)
TRIES=0
MAX_TRIES=30
while ! docker exec "$CONTAINER" pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; do
    TRIES=$((TRIES + 1))
    if [ "$TRIES" -ge "$MAX_TRIES" ]; then
        log "ERROR: Postgres not ready after ${MAX_TRIES} attempts. Aborting."
        exit 1
    fi
    sleep 2
done

# 2. Check if DB has tables
TABLE_COUNT=$(docker exec "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -tAc \
    "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null || echo "0")

TABLE_COUNT=$(echo "$TABLE_COUNT" | tr -d '[:space:]')

if [ "$TABLE_COUNT" -gt 0 ]; then
    log "OK: Database has $TABLE_COUNT tables. No restore needed."
    exit 0
fi

log "WARNING: Database is empty (0 tables). Looking for backup to restore..."

# 3. Find latest backup with valid dump
LATEST_BACKUP=""
for DIR in $(ls -dt "$BACKUP_BASE"/20* 2>/dev/null); do
    DUMP_FILE="$DIR/postgres.dump"
    if [ -f "$DUMP_FILE" ]; then
        DUMP_SIZE=$(stat --format=%s "$DUMP_FILE" 2>/dev/null || echo "0")
        # Reject dumps smaller than 1MB (likely empty/corrupt)
        if [ "$DUMP_SIZE" -gt 1048576 ]; then
            LATEST_BACKUP="$DIR"
            break
        else
            log "SKIP: $DUMP_FILE too small (${DUMP_SIZE} bytes), likely empty DB dump"
        fi
    fi
done

if [ -z "$LATEST_BACKUP" ]; then
    log "ERROR: No valid backup found in $BACKUP_BASE. Manual intervention required."
    exit 1
fi

DUMP_FILE="$LATEST_BACKUP/postgres.dump"
DUMP_SIZE_MB=$(( $(stat --format=%s "$DUMP_FILE") / 1048576 ))

log "RESTORING from $LATEST_BACKUP (dump: ${DUMP_SIZE_MB}MB)..."

# 4. Restore
docker exec -i "$CONTAINER" pg_restore \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --clean --if-exists \
    --no-owner --no-privileges \
    < "$DUMP_FILE" 2>&1 | tee -a "$LOG_FILE"

# 5. Verify
POST_TABLE_COUNT=$(docker exec "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -tAc \
    "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null || echo "0")
POST_TABLE_COUNT=$(echo "$POST_TABLE_COUNT" | tr -d '[:space:]')

DOC_COUNT=$(docker exec "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -tAc \
    "SELECT count(*) FROM documents;" 2>/dev/null || echo "0")
DOC_COUNT=$(echo "$DOC_COUNT" | tr -d '[:space:]')

CHUNK_COUNT=$(docker exec "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -tAc \
    "SELECT count(*) FROM chunks;" 2>/dev/null || echo "0")
CHUNK_COUNT=$(echo "$CHUNK_COUNT" | tr -d '[:space:]')

if [ "$POST_TABLE_COUNT" -gt 0 ]; then
    log "SUCCESS: Restored $POST_TABLE_COUNT tables, $DOC_COUNT documents, $CHUNK_COUNT chunks from $LATEST_BACKUP"
else
    log "ERROR: Restore failed — still 0 tables after pg_restore. Manual intervention required."
    exit 1
fi
