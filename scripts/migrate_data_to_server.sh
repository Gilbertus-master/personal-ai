#!/usr/bin/env bash
# migrate_data_to_server.sh — Migrate Postgres + Qdrant data to the Hetzner VPS.
#
# Usage:
#   ./scripts/migrate_data_to_server.sh <SERVER_IP> [SSH_KEY_PATH]
#
# What it does:
#   1. Creates a Postgres dump locally (via Docker)
#   2. Creates Qdrant snapshots locally (via API)
#   3. SCPs both to the remote server
#   4. Restores Postgres and Qdrant on the remote server
#   5. Verifies data counts match between local and remote
#
# Prerequisites:
#   - Local Docker containers running (gilbertus-postgres, gilbertus-qdrant)
#   - Remote server already deployed (via deploy_hetzner_cloud.sh)
#   - SSH access to the server
#
set -euo pipefail

# ── Args ──────────────────────────────────────────────────────────────────────

if [ $# -lt 1 ]; then
    echo "Usage: $0 <SERVER_IP> [SSH_KEY_PATH]"
    echo ""
    echo "  SERVER_IP     IP address of the Hetzner VPS"
    echo "  SSH_KEY_PATH  Path to SSH key (default: ~/.ssh/gilbertus_hetzner)"
    exit 1
fi

SERVER_IP="$1"
SSH_KEY="${2:-$HOME/.ssh/gilbertus_hetzner}"

# ── Configuration ─────────────────────────────────────────────────────────────

cd "$(dirname "$0")/.."
PROJECT_DIR="$(pwd)"

CONTAINER="gilbertus-postgres"
DB_USER="${POSTGRES_USER:-gilbertus}"
DB_NAME="${POSTGRES_DB:-gilbertus}"
QDRANT_URL="http://127.0.0.1:6333"

MIGRATE_DIR="/tmp/gilbertus_migration_$(date +%F_%H-%M-%S)"
REMOTE_MIGRATE_DIR="/tmp/gilbertus_migration"
MIN_PG_DUMP_BYTES=1048576  # 1MB minimum

mkdir -p "$MIGRATE_DIR"

log() { echo "[$(date '+%H:%M:%S')] $*"; }
die() { echo "ERROR: $*" >&2; rm -rf "$MIGRATE_DIR"; exit 1; }

# SSH/SCP helpers
remote() {
    ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 \
        -i "$SSH_KEY" root@"$SERVER_IP" "$@"
}

remote_copy() {
    scp -o StrictHostKeyChecking=no -i "$SSH_KEY" "$@"
}

# ── Preflight checks ─────────────────────────────────────────────────────────

log "Preflight checks..."

# Check local Docker containers
docker ps --format '{{.Names}}' | grep -q "$CONTAINER" || \
    die "Local container $CONTAINER is not running. Start with: docker compose up -d"

docker ps --format '{{.Names}}' | grep -q "gilbertus-qdrant" || \
    die "Local container gilbertus-qdrant is not running. Start with: docker compose up -d"

# Check SSH access
remote "echo OK" >/dev/null 2>&1 || \
    die "Cannot SSH to root@$SERVER_IP with key $SSH_KEY"

# Check remote Docker
remote "docker ps --format '{{.Names}}' | grep -q gilbertus-postgres" || \
    die "Remote gilbertus-postgres container is not running. Deploy first."

log "All preflight checks passed."

# ── Step 1: Local Postgres dump ──────────────────────────────────────────────

log "Creating local Postgres dump..."

# Get local counts for verification
LOCAL_DOC_COUNT=$(docker exec "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -tAc \
    "SELECT count(*) FROM documents;" 2>/dev/null || echo "0")
LOCAL_DOC_COUNT=$(echo "$LOCAL_DOC_COUNT" | tr -d '[:space:]')

LOCAL_CHUNK_COUNT=$(docker exec "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -tAc \
    "SELECT count(*) FROM chunks;" 2>/dev/null || echo "0")
LOCAL_CHUNK_COUNT=$(echo "$LOCAL_CHUNK_COUNT" | tr -d '[:space:]')

LOCAL_TABLE_COUNT=$(docker exec "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -tAc \
    "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null || echo "0")
LOCAL_TABLE_COUNT=$(echo "$LOCAL_TABLE_COUNT" | tr -d '[:space:]')

log "Local DB: $LOCAL_TABLE_COUNT tables, $LOCAL_DOC_COUNT documents, $LOCAL_CHUNK_COUNT chunks"

if [ "$LOCAL_DOC_COUNT" -eq 0 ]; then
    die "Local database has 0 documents. Nothing to migrate."
fi

# Create the dump
docker exec "$CONTAINER" pg_dump \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    -Fc \
    > "$MIGRATE_DIR/postgres.dump"

DUMP_SIZE=$(stat --format=%s "$MIGRATE_DIR/postgres.dump" 2>/dev/null || echo "0")
DUMP_SIZE_MB=$(( DUMP_SIZE / 1048576 ))

if [ "$DUMP_SIZE" -lt "$MIN_PG_DUMP_BYTES" ]; then
    die "Postgres dump too small (${DUMP_SIZE} bytes). Aborting."
fi

log "Postgres dump: ${DUMP_SIZE_MB}MB"

# ── Step 2: Local Qdrant snapshots ───────────────────────────────────────────

log "Creating local Qdrant snapshots..."

QDRANT_SNAP_DIR="$MIGRATE_DIR/qdrant_snapshots"
mkdir -p "$QDRANT_SNAP_DIR"

COLLECTIONS=$(curl -sf "$QDRANT_URL/collections" 2>/dev/null | \
    .venv/bin/python -c "import sys,json; [print(c['name']) for c in json.load(sys.stdin).get('result',{}).get('collections',[])]" 2>/dev/null || true)

declare -A LOCAL_QDRANT_COUNTS

if [ -n "$COLLECTIONS" ]; then
    for COLL in $COLLECTIONS; do
        log "  Snapshotting collection: $COLL"

        # Get point count for verification
        POINT_COUNT=$(curl -sf "$QDRANT_URL/collections/$COLL" 2>/dev/null | \
            .venv/bin/python -c "import sys,json; print(json.load(sys.stdin).get('result',{}).get('points_count',0))" 2>/dev/null || echo "0")
        LOCAL_QDRANT_COUNTS[$COLL]="$POINT_COUNT"
        log "    Points: $POINT_COUNT"

        # Create snapshot
        SNAP_RESP=$(curl -sf -X POST "$QDRANT_URL/collections/$COLL/snapshots" 2>/dev/null || echo "")
        if [ -z "$SNAP_RESP" ]; then
            log "  WARNING: Failed to create snapshot for $COLL"
            continue
        fi

        SNAP_NAME=$(echo "$SNAP_RESP" | \
            .venv/bin/python -c "import sys,json; print(json.load(sys.stdin).get('result',{}).get('name',''))" 2>/dev/null || echo "")

        if [ -n "$SNAP_NAME" ]; then
            curl -sf "$QDRANT_URL/collections/$COLL/snapshots/$SNAP_NAME" \
                -o "$QDRANT_SNAP_DIR/${COLL}.snapshot" 2>/dev/null

            # Cleanup snapshot from Qdrant server
            curl -sf -X DELETE "$QDRANT_URL/collections/$COLL/snapshots/$SNAP_NAME" >/dev/null 2>&1 || true

            SNAP_SIZE=$(stat --format=%s "$QDRANT_SNAP_DIR/${COLL}.snapshot" 2>/dev/null || echo "0")
            log "    Snapshot: $(( SNAP_SIZE / 1048576 ))MB"
        fi
    done
else
    log "WARNING: No Qdrant collections found (empty or unreachable)"
fi

# ── Step 3: Transfer to server ───────────────────────────────────────────────

log "Transferring data to $SERVER_IP..."

# Prepare remote directory
remote "rm -rf $REMOTE_MIGRATE_DIR && mkdir -p $REMOTE_MIGRATE_DIR/qdrant_snapshots"

# Transfer Postgres dump
log "  Transferring Postgres dump (${DUMP_SIZE_MB}MB)..."
remote_copy "$MIGRATE_DIR/postgres.dump" "root@$SERVER_IP:$REMOTE_MIGRATE_DIR/postgres.dump"

# Transfer Qdrant snapshots
SNAP_FILES=$(ls "$QDRANT_SNAP_DIR"/*.snapshot 2>/dev/null || true)
if [ -n "$SNAP_FILES" ]; then
    for SNAP_FILE in $SNAP_FILES; do
        FNAME=$(basename "$SNAP_FILE")
        FSIZE=$(stat --format=%s "$SNAP_FILE" 2>/dev/null || echo 0)
        log "  Transferring Qdrant snapshot: $FNAME ($(( FSIZE / 1048576 ))MB)..."
        remote_copy "$SNAP_FILE" "root@$SERVER_IP:$REMOTE_MIGRATE_DIR/qdrant_snapshots/$FNAME"
    done
fi

log "Transfer complete."

# ── Step 4: Restore on server ────────────────────────────────────────────────

log "Restoring data on remote server..."

remote bash -s -- "$DB_USER" "$DB_NAME" "$REMOTE_MIGRATE_DIR" <<'RESTORE_SCRIPT'
set -euo pipefail

DB_USER="$1"
DB_NAME="$2"
MIGRATE_DIR="$3"
CONTAINER="gilbertus-postgres"
QDRANT_URL="http://127.0.0.1:6333"

echo "==> Waiting for Postgres to be ready..."
until docker exec "$CONTAINER" pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; do
    sleep 2
done

echo "==> Restoring Postgres..."
# Drop and recreate public schema to get a clean slate
docker exec -i "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" \
    -c "DROP SCHEMA IF EXISTS public CASCADE;"
docker exec -i "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" \
    -c "CREATE SCHEMA public;"

# Restore the dump
docker exec -i "$CONTAINER" pg_restore \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --no-owner \
    --no-privileges \
    < "$MIGRATE_DIR/postgres.dump"

echo "==> Postgres restore complete."

# Restore Qdrant snapshots
SNAP_DIR="$MIGRATE_DIR/qdrant_snapshots"
if [ -d "$SNAP_DIR" ] && ls "$SNAP_DIR"/*.snapshot >/dev/null 2>&1; then
    for SNAP_FILE in "$SNAP_DIR"/*.snapshot; do
        COLL_NAME=$(basename "$SNAP_FILE" .snapshot)
        echo "==> Restoring Qdrant collection: $COLL_NAME"

        # Delete existing collection if any
        curl -sf -X DELETE "$QDRANT_URL/collections/$COLL_NAME" >/dev/null 2>&1 || true
        sleep 1

        # Upload snapshot to restore
        curl -sf -X POST "$QDRANT_URL/collections/$COLL_NAME/snapshots/upload" \
            -H "Content-Type: multipart/form-data" \
            -F "snapshot=@$SNAP_FILE" >/dev/null 2>&1 || {
            echo "WARNING: Failed to restore Qdrant collection $COLL_NAME"
        }
        sleep 2
    done
    echo "==> Qdrant restore complete."
else
    echo "==> No Qdrant snapshots to restore."
fi

# Cleanup
rm -rf "$MIGRATE_DIR"
echo "==> Cleanup done."
RESTORE_SCRIPT

log "Remote restore complete."

# ── Step 5: Verify data counts ───────────────────────────────────────────────

log "Verifying data counts..."

echo ""
echo "================================================================"
echo "  DATA VERIFICATION"
echo "================================================================"

# Remote Postgres counts
REMOTE_DOC_COUNT=$(remote "docker exec gilbertus-postgres psql -U $DB_USER -d $DB_NAME -tAc 'SELECT count(*) FROM documents;'" | tr -d '[:space:]')
REMOTE_CHUNK_COUNT=$(remote "docker exec gilbertus-postgres psql -U $DB_USER -d $DB_NAME -tAc 'SELECT count(*) FROM chunks;'" | tr -d '[:space:]')

echo ""
echo "  Postgres:"
echo "    Documents:  local=$LOCAL_DOC_COUNT  remote=$REMOTE_DOC_COUNT"
echo "    Chunks:     local=$LOCAL_CHUNK_COUNT  remote=$REMOTE_CHUNK_COUNT"

PG_OK=true
if [ "$LOCAL_DOC_COUNT" != "$REMOTE_DOC_COUNT" ]; then
    echo "    WARNING: Document count mismatch!"
    PG_OK=false
fi
if [ "$LOCAL_CHUNK_COUNT" != "$REMOTE_CHUNK_COUNT" ]; then
    echo "    WARNING: Chunk count mismatch!"
    PG_OK=false
fi

if [ "$PG_OK" = true ]; then
    echo "    Status: OK (counts match)"
fi

# Remote Qdrant counts
echo ""
echo "  Qdrant:"

QDRANT_OK=true
for COLL in "${!LOCAL_QDRANT_COUNTS[@]}"; do
    LOCAL_PTS="${LOCAL_QDRANT_COUNTS[$COLL]}"
    REMOTE_PTS=$(remote "curl -sf http://127.0.0.1:6333/collections/$COLL 2>/dev/null" | \
        .venv/bin/python -c "import sys,json; print(json.load(sys.stdin).get('result',{}).get('points_count',0))" 2>/dev/null || echo "?")

    echo "    $COLL:  local=$LOCAL_PTS  remote=$REMOTE_PTS"

    if [ "$LOCAL_PTS" != "$REMOTE_PTS" ]; then
        echo "    WARNING: Point count mismatch for $COLL!"
        QDRANT_OK=false
    fi
done

if [ ${#LOCAL_QDRANT_COUNTS[@]} -eq 0 ]; then
    echo "    (no collections to verify)"
elif [ "$QDRANT_OK" = true ]; then
    echo "    Status: OK (counts match)"
fi

echo ""
echo "================================================================"

if [ "$PG_OK" = true ] && [ "$QDRANT_OK" = true ]; then
    echo "  MIGRATION SUCCESSFUL — all data verified."
else
    echo "  MIGRATION COMPLETED WITH WARNINGS — check counts above."
fi

echo ""
echo "  Next: restart the API to pick up the new data:"
echo "    ssh -i $SSH_KEY root@$SERVER_IP"
echo "    systemctl restart gilbertus-api"
echo ""
echo "================================================================"

# Cleanup local temp
rm -rf "$MIGRATE_DIR"
log "Local cleanup done."
