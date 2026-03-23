#!/usr/bin/env bash
set -euo pipefail

if [ $# -ne 1 ]; then
    echo "Użycie: ./scripts/restore_db.sh backups/db/YYYY-MM-DD_HH-MM-SS"
    exit 1
fi

BACKUP_DIR="$1"

cd "$(dirname "$0")/.."

CONTAINER="gilbertus-postgres"
DB_USER="${POSTGRES_USER:-gilbertus}"
DB_NAME="${POSTGRES_DB:-gilbertus}"
QDRANT_URL="http://127.0.0.1:6333"

if [ ! -d "$BACKUP_DIR" ]; then
    echo "Nie istnieje katalog backupu: $BACKUP_DIR"
    exit 1
fi

if [ ! -f "$BACKUP_DIR/postgres.dump" ]; then
    echo "Brak pliku: $BACKUP_DIR/postgres.dump"
    exit 1
fi

DUMP_SIZE=$(stat --format=%s "$BACKUP_DIR/postgres.dump" 2>/dev/null || echo "0")
DUMP_SIZE_MB=$(( DUMP_SIZE / 1048576 ))
echo "==> Backup dump: ${DUMP_SIZE_MB}MB"

if [ "$DUMP_SIZE" -lt 1048576 ]; then
    echo "==> ERROR: Dump too small (${DUMP_SIZE} bytes). Likely empty/corrupt. Aborting."
    exit 1
fi

echo "==> UWAGA: to nadpisze aktualne dane Postgresa i Qdranta"
echo "==> Przywracam z: $BACKUP_DIR"

# ── Postgres restore ──
echo "==> Czekam na Postgresa"
until docker exec "$CONTAINER" pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; do
    sleep 2
done

echo "==> Recreate public schema"
docker exec -i "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "DROP SCHEMA IF EXISTS public CASCADE;"
docker exec -i "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "CREATE SCHEMA public;"

echo "==> Odtwarzanie Postgresa"
docker exec -i "$CONTAINER" pg_restore \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --no-owner \
    --no-privileges \
    < "$BACKUP_DIR/postgres.dump"

# ── Qdrant restore (snapshot API) ──
SNAP_DIR="$BACKUP_DIR/qdrant_snapshots"
if [ -d "$SNAP_DIR" ]; then
    for SNAP_FILE in "$SNAP_DIR"/*.snapshot; do
        [ -f "$SNAP_FILE" ] || continue
        COLL_NAME=$(basename "$SNAP_FILE" .snapshot)
        echo "==> Odtwarzanie Qdrant collection: $COLL_NAME"

        # Delete existing collection
        curl -sf -X DELETE "$QDRANT_URL/collections/$COLL_NAME" >/dev/null 2>&1 || true
        sleep 1

        # Upload snapshot
        curl -sf -X POST "$QDRANT_URL/collections/$COLL_NAME/snapshots/upload" \
            -H "Content-Type: multipart/form-data" \
            -F "snapshot=@$SNAP_FILE" >/dev/null 2>&1 || {
            echo "==> WARNING: Failed to restore Qdrant collection $COLL_NAME"
        }
    done
else
    echo "==> Brak Qdrant snapshots w backupie (legacy format lub brak danych)"
fi

# ── Verification ──
echo "==> Gotowe. Aktualne liczniki:"
docker exec -i "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT COUNT(*) AS total_documents FROM documents;"
docker exec -i "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT COUNT(*) AS total_chunks FROM chunks;"

QDRANT_COLLS=$(curl -sf "$QDRANT_URL/collections" 2>/dev/null || echo "{}")
echo "==> Qdrant collections: $QDRANT_COLLS"
