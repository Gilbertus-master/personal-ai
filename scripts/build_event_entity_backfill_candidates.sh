#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

docker exec -i gilbertus-postgres psql -v ON_ERROR_STOP=1 -U gilbertus -d gilbertus <<'SQL'
TRUNCATE event_entity_backfill_candidates;

INSERT INTO event_entity_backfill_candidates (chunk_id)
SELECT DISTINCT e.chunk_id
FROM events e
LEFT JOIN chunk_entities ce ON ce.chunk_id = e.chunk_id
WHERE ce.id IS NULL;
SQL
