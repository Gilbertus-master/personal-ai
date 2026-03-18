#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/.."
source .venv/bin/activate

ROOT="data/raw/teams/export_20260310"

count=0
imported=0
skipped_or_empty=0
failed=0

while IFS= read -r -d '' file; do
  count=$((count + 1))
  echo
  echo "[$count] Processing: $file"

  if python -m app.ingestion.docs.importer "$file"; then
    imported=$((imported + 1))
  else
    failed=$((failed + 1))
  fi
done < <(find "$ROOT" -type f \( -iname "*.pdf" -o -iname "*.txt" -o -iname "*.docx" \) -print0)

echo
echo "Teams documents import finished."
echo "Processed: $count"
echo "Imported/attempted OK: $imported"
echo "Failed: $failed"