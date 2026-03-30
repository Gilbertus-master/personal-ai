#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

cd "$REPO_DIR"
source .venv/bin/activate

echo "=============================================="
echo "  Data Guardian — Self-Healing Pipeline Builder"
echo "=============================================="
echo "  Repo: $REPO_DIR"
echo "  Tasks: $(.venv/bin/python -c "import json; q=json.load(open('$SCRIPT_DIR/queue.json')); print(f\"{sum(1 for t in q['tasks'] if t['status']=='pending')} pending / {len(q['tasks'])} total\")")"
echo ""

.venv/bin/python "$SCRIPT_DIR/runner.py" "$@"
