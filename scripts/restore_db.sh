#!/usr/bin/env bash
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Użycie: ./scripts/restore_db.sh backups/db/YYYY-MM-DD_HH-MM-SS"
  exit 1
fi

BACKUP_DIR="$1"

cd "$(dirname "$0")/.."

if [ ! -d "$BACKUP_DIR" ]; then
  echo "Nie istnieje katalog backupu: $BACKUP_DIR"
  exit 1
fi

if [ ! -f "$BACKUP_DIR/postgres.dump" ]; then
  echo "Brak pliku: $BACKUP_DIR/postgres.dump"
  exit 1
fi

if [ ! -f "$BACKUP_DIR/qdrant.tar.zst" ]; then
  echo "Brak pliku: $BACKUP_DIR/qdrant.tar.zst"
  exit 1
fi

echo "==> UWAGA: to nadpisze aktualne dane Postgresa i Qdranta"
echo "==> Przywracam z: $BACKUP_DIR"

echo "==> Stop kontenerów"
docker compose stop postgres qdrant

echo "==> Czyszczenie katalogu Qdrant"
rm -rf data/processed/qdrant/*
mkdir -p data/processed/qdrant

echo "==> Odtwarzanie plików Qdrant"
tar -I zstd -xf "$BACKUP_DIR/qdrant.tar.zst"

echo "==> Start Postgresa"
docker compose up -d postgres

echo "==> Czekam na Postgresa"
until docker exec gilbertus-postgres pg_isready -U gilbertus -d gilbertus >/dev/null 2>&1; do
  sleep 2
done

echo "==> Recreate public schema"
docker exec -i gilbertus-postgres psql -U gilbertus -d gilbertus -c "DROP SCHEMA IF EXISTS public CASCADE;"
docker exec -i gilbertus-postgres psql -U gilbertus -d gilbertus -c "CREATE SCHEMA public;"

echo "==> Odtwarzanie Postgresa"
docker exec -i gilbertus-postgres pg_restore \
  -U gilbertus \
  -d gilbertus \
  --no-owner \
  --no-privileges \
  < "$BACKUP_DIR/postgres.dump"

echo "==> Start Qdrant"
docker compose up -d qdrant

echo "==> Gotowe. Aktualne liczniki:"
docker exec -i gilbertus-postgres psql -U gilbertus -d gilbertus -c "SELECT COUNT(*) AS total_sources FROM sources;"
docker exec -i gilbertus-postgres psql -U gilbertus -d gilbertus -c "SELECT COUNT(*) AS total_documents FROM documents;"
docker exec -i gilbertus-postgres psql -U gilbertus -d gilbertus -c "SELECT COUNT(*) AS total_chunks FROM chunks;"