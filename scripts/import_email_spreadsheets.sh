#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/.."
source .venv/bin/activate

ROOT="data/raw/email"

count=0
imported=0
failed=0

while IFS= read -r -d '' file; do
  count=$((count + 1))
  echo
  echo "[$count] Processing: $file"

  if python -m app.ingestion.spreadsheets.importer "$file"; then
    imported=$((imported + 1))
  else
    failed=$((failed + 1))
  fi
done < <(
  find "$ROOT" -type f \( -iname "*.xlsx" -o -iname "*.csv" \) \
    ! -path "*/Reports-Content_Search-*/*" \
    -print0
)

echo
echo "Email spreadsheets import finished."
echo "Processed: $count"
echo "Imported/attempted OK: $imported"
echo "Failed: $failed"