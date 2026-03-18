#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/.."
source .venv/bin/activate

for file in data/raw/docs/*.pdf; do
  echo "Importing: $file"
  python -m app.ingestion.docs.importer "$file"
done

echo "PDF document import finished."