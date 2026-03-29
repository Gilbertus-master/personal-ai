#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

cd "$REPO_DIR"
source .venv/bin/activate

echo "=============================================="
echo "  Gilbertus/Omnius Frontend App Builder"
echo "  Hierarchical Orchestrator (10 parts)"
echo "=============================================="
echo "  Repo: $REPO_DIR"
echo "  Frontend: $REPO_DIR/frontend"
echo ""

python3 "$SCRIPT_DIR/master.py" "$@"
