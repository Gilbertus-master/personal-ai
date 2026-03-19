#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

run_dir() {
  local dir="$1"
  if [ -d "$dir" ]; then
    find "$dir" -maxdepth 1 -type f -name '*.sql' | sort | while read -r file; do
      echo "==> Running migration: $file"
      docker exec -i gilbertus-postgres psql -v ON_ERROR_STOP=1 -U gilbertus -d gilbertus < "$file"
    done
  fi
}

run_dir app/db/migrations
run_dir migrations
