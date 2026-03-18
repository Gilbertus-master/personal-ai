#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/.."
source .venv/bin/activate

for file in data/raw/whatsapp/*.txt; do
  echo "Importing: $file"
  python -m app.ingestion.whatsapp.importer "$file"
done

echo "WhatsApp import finished."