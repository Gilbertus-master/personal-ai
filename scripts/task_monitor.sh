#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.npm-global/bin:$PATH"
.venv/bin/python -m app.orchestrator.task_monitor >> logs/task_monitor.log 2>&1
