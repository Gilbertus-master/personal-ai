#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
source .venv/bin/activate

RAW_DIR="data/raw/email"
EXTRACT_DIR="data/processed/email_extracted"
EMAIL_IMPORT_LIMIT="${EMAIL_IMPORT_LIMIT:-}"

mkdir -p "$EXTRACT_DIR"

if ! command -v readpst >/dev/null 2>&1; then
  echo "ERROR: readpst not found. Install pst-utils first."
  exit 1
fi

shopt -s nullglob
PST_FILES=("$RAW_DIR"/*.pst)

if [ ${#PST_FILES[@]} -eq 0 ]; then
  echo "No PST files found in $RAW_DIR"
  exit 1
fi

for pst in "${PST_FILES[@]}"; do
  base="$(basename "$pst")"
  stem="${base%.pst}"
  out_dir="$EXTRACT_DIR/$stem"

  echo
  echo "=================================================="
  echo "PST: $base"
  echo "=================================================="

  mkdir -p "$out_dir"

  if [ ! -f "$out_dir/.extract_done" ]; then
    echo "==> Extracting PST to EML: $pst"
    rm -rf "$out_dir"/*
    readpst -r -e -o "$out_dir" "$pst"
    touch "$out_dir/.extract_done"
  else
    echo "==> Extraction already done, skipping readpst"
  fi

  echo "==> Importing extracted emails to Postgres"

  if [ -n "$EMAIL_IMPORT_LIMIT" ]; then
    echo "==> EMAIL_IMPORT_LIMIT=$EMAIL_IMPORT_LIMIT"
    python -m app.ingestion.email.importer "$pst" "$out_dir" --limit "$EMAIL_IMPORT_LIMIT"
  else
    python -m app.ingestion.email.importer "$pst" "$out_dir"
  fi
done

echo
echo "Email PST import finished."
