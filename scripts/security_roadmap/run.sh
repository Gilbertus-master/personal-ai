#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

cd "$REPO_DIR"
source .venv/bin/activate

echo "Gilbertus Security Roadmap Runner"
echo "  Repo: $REPO_DIR"
echo ""

python3 "$SCRIPT_DIR/runner.py" "$@"
