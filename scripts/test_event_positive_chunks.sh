#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
source .venv/bin/activate

echo "==> TRUNCATE testowych eventów"
docker exec -i gilbertus-postgres psql -U gilbertus -d gilbertus -c "TRUNCATE event_entities, events RESTART IDENTITY CASCADE;"

echo
echo "==> decision: chunk_id=125675"
./scripts/extract_events.sh --chunk-id 125675

echo
echo "==> health: chunk_id=4279"
./scripts/extract_events.sh --chunk-id 4279

echo
echo "==> conflict: chunk_id=3783"
./scripts/extract_events.sh --chunk-id 3783

echo
echo "==> family: chunk_id=86547"
./scripts/extract_events.sh --chunk-id 86547

echo
echo "==> Wynik końcowy: events"
docker exec -i gilbertus-postgres psql -P pager=off -U gilbertus -d gilbertus -x -c \
"SELECT * FROM events ORDER BY id;"

echo
echo "==> Wynik końcowy: event_entities"
docker exec -i gilbertus-postgres psql -P pager=off -U gilbertus -d gilbertus -x -c \
"SELECT * FROM event_entities ORDER BY id;"
