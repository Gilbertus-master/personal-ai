#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/.."
docker exec -i gilbertus-postgres psql -U gilbertus -d gilbertus < app/db/migrations/001_init_metadata.sql