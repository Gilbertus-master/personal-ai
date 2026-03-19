#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
source .venv/bin/activate

LIMIT="${1:-50}"

python -m app.extraction.events "$LIMIT"
