#!/usr/bin/env bash
# import_plaud.sh — Import Plaud Pin S transcriptions
# Usage:
#   ./scripts/import_plaud.sh <directory_with_transcripts>
#   ./scripts/import_plaud.sh ~/plaud_exports
#   ./scripts/import_plaud.sh ~/plaud_exports --limit 10
set -euo pipefail
cd "$(dirname "$0")/.."

if [ $# -lt 1 ]; then
    echo "Usage: $0 <path_to_transcripts> [--limit N] [--source-name NAME]"
    exit 1
fi

echo "==> Importing Plaud Pin S transcriptions from: $1"
.venv/bin/python -m app.ingestion.audio.importer "$@"
echo "==> Done"
