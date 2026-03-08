#!/usr/bin/env bash
set -e

echo "Checking Qdrant..."
curl -s http://127.0.0.1:6333/collections
echo
echo

echo "Checking Postgres..."
docker exec -i gilbertus-postgres psql -U gilbertus -d gilbertus -c "SELECT 1;"
echo
echo "All local services are reachable."