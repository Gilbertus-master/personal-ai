#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/.."

PST_FILE="${1:-data/raw/teams/pst/teams_archive.pst}"
OUT_DIR="data/processed/teams/extracted"

mkdir -p "$OUT_DIR"

readpst -M -r -o "$OUT_DIR" "$PST_FILE"

echo "Teams PST extracted to: $OUT_DIR"