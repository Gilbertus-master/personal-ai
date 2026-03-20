#!/usr/bin/env bash
set -euo pipefail

show_chunk() {
  local chunk_id="$1"
  echo
  echo "============================================================"
  echo "chunk_id=$chunk_id"
  docker exec -i gilbertus-postgres psql -P pager=off -U gilbertus -d gilbertus -x -c "
  SELECT
    id,
    document_id,
    chunk_index,
    timestamp_start,
    left(text, 1200) AS sample
  FROM chunks
  WHERE id = ${chunk_id};
  "
}

show_chunk 125675
show_chunk 4279
show_chunk 3783
show_chunk 86547
