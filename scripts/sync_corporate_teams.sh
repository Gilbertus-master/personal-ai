#!/usr/bin/env bash
# sync_corporate_teams.sh — Sync Teams chats via Microsoft Graph API
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Syncing Teams chats"
.venv/bin/python -m app.ingestion.graph_api.teams_sync "$@"

echo "==> Done"
