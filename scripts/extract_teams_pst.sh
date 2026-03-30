#!/usr/bin/env bash
set -e

trap 'echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) [ERROR] extract_teams_pst.sh failed at line $LINENO" >&2' ERR

cd "$(dirname "$0")/.."

PST_FILE="${1:-data/raw/teams/pst/teams_archive.pst}"
OUT_DIR="data/processed/teams/extracted"

mkdir -p "$OUT_DIR"

readpst -M -r -o "$OUT_DIR" "$PST_FILE"

echo "Teams PST extracted to: $OUT_DIR"
echo "Next step: run python -m app.ingestion.teams.importer to ingest extracted messages"