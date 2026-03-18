#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/.."
source .venv/bin/activate

for file in data/raw/chatgpt/20260310/conversations-*.json; do
  echo "Importing file: $file"
  python -m app.ingestion.chatgpt.importer "$file"
done

echo "ChatGPT import finished."