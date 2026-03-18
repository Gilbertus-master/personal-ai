#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

TS="$(date +%F_%H-%M-%S)"
BACKUP_DIR="backups/db/$TS"
mkdir -p "$BACKUP_DIR"

echo "==> Tworze backup w: $BACKUP_DIR"

docker exec gilbertus-postgres pg_dump \
  -U "${POSTGRES_USER:-gilbertus}" \
  -d "${POSTGRES_DB:-gilbertus}" \
  -Fc \
  > "$BACKUP_DIR/postgres.dump"

tar -I 'zstd -3 -T0' -cf "$BACKUP_DIR/qdrant.tar.zst" data/processed/qdrant

cat > "$BACKUP_DIR/manifest.json" <<MANIFEST
{
  "timestamp": "$TS",
  "project": "Gilbertus Albans",
  "postgres_db": "${POSTGRES_DB:-gilbertus}",
  "postgres_container": "gilbertus-postgres",
  "qdrant_container": "gilbertus-qdrant",
  "postgres_dump": "postgres.dump",
  "qdrant_archive": "qdrant.tar.zst"
}
MANIFEST

echo "==> Backup gotowy"
ls -lh "$BACKUP_DIR"