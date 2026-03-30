#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

LOCKFILE="/tmp/backup_db.lock"
exec 9>"$LOCKFILE"
if ! flock -n 9; then
    echo "==> Another backup already running — exiting"
    exit 0
fi

CONTAINER="gilbertus-postgres"
DB_USER="${POSTGRES_USER:-gilbertus}"
DB_NAME="${POSTGRES_DB:-gilbertus}"
QDRANT_CONTAINER="gilbertus-qdrant"
QDRANT_URL="http://127.0.0.1:6333"
QDRANT_API_KEY="${QDRANT_API_KEY:-$(grep QDRANT_API_KEY .env 2>/dev/null | cut -d= -f2-)}"
QDRANT_AUTH=()
if [ -n "$QDRANT_API_KEY" ]; then
    QDRANT_AUTH=(-H "api-key:${QDRANT_API_KEY}")
fi

TS="$(date +%F_%H-%M-%S)"
BACKUP_DIR="backups/db/$TS"
MIN_PG_DUMP_BYTES=1048576  # 1MB — anything less means empty DB

mkdir -p "$BACKUP_DIR"

echo "==> Tworze backup w: $BACKUP_DIR"

# ── Pre-flight: verify DB is not empty ──
RAW=$(docker exec "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -tAc \
    "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>&1)
if [ $? -ne 0 ]; then
    echo "==> ERROR: Cannot connect to Postgres — aborting backup"
    exit 1
fi
TABLE_COUNT=$(echo "$RAW" | tr -d '[:space:]')

if [ "$TABLE_COUNT" -eq 0 ]; then
    echo "==> WARNING: Database has 0 tables — skipping backup to avoid overwriting good backups with empty dump"
    exit 0
fi

DOC_COUNT=$(docker exec "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -tAc \
    "SELECT count(*) FROM documents;" 2>/dev/null || echo "0")
DOC_COUNT=$(echo "$DOC_COUNT" | tr -d '[:space:]')
echo "==> Pre-flight: $TABLE_COUNT tables, $DOC_COUNT documents"

# ── Postgres dump ──
docker exec "$CONTAINER" pg_dump \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    -Fc \
    > "$BACKUP_DIR/postgres.dump"

DUMP_SIZE=$(stat --format=%s "$BACKUP_DIR/postgres.dump" 2>/dev/null || echo "0")

if [ "$DUMP_SIZE" -lt "$MIN_PG_DUMP_BYTES" ]; then
    echo "==> ERROR: Postgres dump too small (${DUMP_SIZE} bytes). Removing suspect backup."
    rm -rf "$BACKUP_DIR"
    exit 1
fi

DUMP_SIZE_MB=$(( DUMP_SIZE / 1048576 ))
echo "==> Postgres dump: ${DUMP_SIZE_MB}MB"

# ── Qdrant snapshot via API ──
QDRANT_SNAP_DIR="$BACKUP_DIR/qdrant_snapshots"
mkdir -p "$QDRANT_SNAP_DIR"

COLLECTIONS=$(curl -sf --max-time 60 "${QDRANT_AUTH[@]}" "$QDRANT_URL/collections" 2>/dev/null | \
    .venv/bin/python -c "import sys,json; [print(c['name']) for c in json.load(sys.stdin).get('result',{}).get('collections',[])]" 2>/dev/null || true)

QDRANT_OK=false
if [ -n "$COLLECTIONS" ]; then
    for COLL in $COLLECTIONS; do
        echo "==> Qdrant snapshot: $COLL"
        SNAP_RESP=$(curl -sf --max-time 30 "${QDRANT_AUTH[@]}" -X POST "$QDRANT_URL/collections/$COLL/snapshots" 2>/dev/null || echo "")
        if [ -z "$SNAP_RESP" ]; then
            echo "==> WARNING: Failed to create Qdrant snapshot for $COLL"
            continue
        fi
        SNAP_NAME=$(echo "$SNAP_RESP" | .venv/bin/python -c "import sys,json; print(json.load(sys.stdin).get('result',{}).get('name',''))" 2>/dev/null || echo "")
        if [ -n "$SNAP_NAME" ]; then
            curl -sf --max-time 300 "${QDRANT_AUTH[@]}" "$QDRANT_URL/collections/$COLL/snapshots/$SNAP_NAME" \
                -o "$QDRANT_SNAP_DIR/${COLL}.snapshot" 2>/dev/null || true
            # Cleanup snapshot from Qdrant server
            curl -sf --max-time 10 "${QDRANT_AUTH[@]}" -X DELETE "$QDRANT_URL/collections/$COLL/snapshots/$SNAP_NAME" >/dev/null 2>&1 || true
            SNAP_SIZE=$(stat --format=%s "$QDRANT_SNAP_DIR/${COLL}.snapshot" 2>/dev/null || echo "0")
            echo "==> Qdrant snapshot $COLL: $(( SNAP_SIZE / 1048576 ))MB"
            QDRANT_OK=true
        fi
    done
fi

if [ "$QDRANT_OK" = false ]; then
    echo "==> WARNING: No Qdrant collections to backup (empty or unreachable)"
    rmdir "$QDRANT_SNAP_DIR" 2>/dev/null || true
fi

# ── Manifest ──
TS="$TS" DB_NAME="$DB_NAME" CONTAINER="$CONTAINER" QDRANT_CONTAINER="$QDRANT_CONTAINER" DUMP_SIZE="$DUMP_SIZE" TABLE_COUNT="$TABLE_COUNT" DOC_COUNT="$DOC_COUNT" QDRANT_OK="$QDRANT_OK" \
.venv/bin/python -c '
import json, os
manifest = {
    "timestamp": os.environ["TS"],
    "project": "Gilbertus Albans",
    "postgres_db": os.environ["DB_NAME"],
    "postgres_container": os.environ["CONTAINER"],
    "qdrant_container": os.environ["QDRANT_CONTAINER"],
    "postgres_dump": "postgres.dump",
    "postgres_dump_bytes": int(os.environ["DUMP_SIZE"]),
    "postgres_tables": int(os.environ["TABLE_COUNT"]),
    "postgres_documents": int(os.environ["DOC_COUNT"]),
    "qdrant_snapshot_api": os.environ["QDRANT_OK"] == "true"
}
print(json.dumps(manifest, indent=2))
' > "$BACKUP_DIR/manifest.json"

echo "==> Backup gotowy"
ls -lh "$BACKUP_DIR"
