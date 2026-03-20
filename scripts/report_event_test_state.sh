#!/usr/bin/env bash
set -euo pipefail

docker exec -i gilbertus-postgres psql -P pager=off -U gilbertus -d gilbertus -c "SELECT COUNT(*) AS events_count FROM events;"
docker exec -i gilbertus-postgres psql -P pager=off -U gilbertus -d gilbertus -c "SELECT COUNT(*) AS event_entities_count FROM event_entities;"

echo
docker exec -i gilbertus-postgres psql -P pager=off -U gilbertus -d gilbertus -x -c "
SELECT id, document_id, chunk_id, event_type, event_time, confidence, left(summary, 250) AS summary
FROM events
ORDER BY id;
"

echo
docker exec -i gilbertus-postgres psql -P pager=off -U gilbertus -d gilbertus -x -c "
SELECT *
FROM event_entities
ORDER BY id;
"
