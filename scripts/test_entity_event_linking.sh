#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
source .venv/bin/activate

echo "==> Czyszczenie testowych danych"
docker exec -i gilbertus-postgres psql -U gilbertus -d gilbertus -c "TRUNCATE event_entities, events RESTART IDENTITY CASCADE;"
docker exec -i gilbertus-postgres psql -U gilbertus -d gilbertus -c "
DELETE FROM chunk_entities WHERE chunk_id IN (125675, 4279, 3783, 86547);
"

echo
echo "==> Entity extraction"
./scripts/extract_entities.sh --chunk-id 125675
./scripts/extract_entities.sh --chunk-id 4279
./scripts/extract_entities.sh --chunk-id 3783
./scripts/extract_entities.sh --chunk-id 86547

echo
echo "==> Event extraction"
./scripts/extract_events.sh --chunk-id 125675
./scripts/extract_events.sh --chunk-id 4279
./scripts/extract_events.sh --chunk-id 3783
./scripts/extract_events.sh --chunk-id 86547

echo
echo "==> chunk_entities"
docker exec -i gilbertus-postgres psql -P pager=off -U gilbertus -d gilbertus -x -c "
SELECT *
FROM chunk_entities
WHERE chunk_id IN (125675, 4279, 3783, 86547)
ORDER BY id;
"

echo
echo "==> events"
docker exec -i gilbertus-postgres psql -P pager=off -U gilbertus -d gilbertus -x -c "
SELECT *
FROM events
ORDER BY id;
"

echo
echo "==> event_entities"
docker exec -i gilbertus-postgres psql -P pager=off -U gilbertus -d gilbertus -x -c "
SELECT *
FROM event_entities
ORDER BY id;
"
