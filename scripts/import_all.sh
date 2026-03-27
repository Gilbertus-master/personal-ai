#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p logs

run_step() {
  local name="$1"
  shift

  echo
  echo "=================================================="
  echo "==> START: $name"
  echo "=================================================="

  ./scripts/import_with_backup.sh "$@" 2>&1 | tee "logs/${name}_$(date +%F_%H-%M-%S).log"

  echo "==> END: $name"
}

# ChatGPT import disabled — Sebastian no longer uses ChatGPT (2026-03-26)
# run_step "import_chatgpt" ./scripts/import_chatgpt.sh
run_step "import_docs" ./scripts/import_docs.sh
run_step "import_email_spreadsheets" ./scripts/import_email_spreadsheets.sh
run_step "import_teams" ./scripts/import_teams.sh
run_step "import_teams_docs" ./scripts/import_teams_docs.sh
run_step "import_teams_spreadsheets" ./scripts/import_teams_spreadsheets.sh
run_step "import_whatsapp" ./scripts/import_whatsapp.sh

echo
echo "=================================================="
echo "==> ALL IMPORTS FINISHED"
echo "=================================================="

docker exec -i gilbertus-postgres psql -U gilbertus -d gilbertus -c \
"SELECT COUNT(*) AS total_sources FROM sources;"

docker exec -i gilbertus-postgres psql -U gilbertus -d gilbertus -c \
"SELECT COUNT(*) AS total_documents FROM documents;"

docker exec -i gilbertus-postgres psql -U gilbertus -d gilbertus -c \
"SELECT COUNT(*) AS total_chunks FROM chunks;"

du -sh data/processed/qdrant || true