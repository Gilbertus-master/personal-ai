#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Użycie: ./scripts/import_with_backup.sh <komenda> [argumenty...]"
  echo 'Przykład: ./scripts/import_with_backup.sh python scripts/import_chatgpt.py'
  exit 1
fi

cd "$(dirname "$0")/.."

echo "==> KATALOG PROJEKTU"
pwd

echo "==> STATUS KONTENERÓW"
docker compose ps

echo "==> BACKUP PRZED IMPORTEM"
./scripts/backup_db.sh

echo "==> IMPORT"
"$@"

echo "==> WALIDACJA POST-IMPORT"

docker exec -i gilbertus-postgres psql -U gilbertus -d gilbertus -c \
"SELECT COUNT(*) AS total_sources FROM sources;"

docker exec -i gilbertus-postgres psql -U gilbertus -d gilbertus -c \
"SELECT COUNT(*) AS total_documents FROM documents;"

docker exec -i gilbertus-postgres psql -U gilbertus -d gilbertus -c \
"SELECT COUNT(*) AS total_chunks FROM chunks;"

echo "==> ROZMIAR QDRANT"
du -sh data/processed/qdrant || true

echo "==> BACKUP PO IMPORCIE"
./scripts/backup_db.sh

echo "==> GOTOWE"