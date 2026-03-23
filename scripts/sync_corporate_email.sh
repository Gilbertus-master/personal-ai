#!/usr/bin/env bash
# sync_corporate_email.sh — Sync corporate email via Microsoft Graph API
# First run: full sync. Subsequent runs: incremental (delta query).
#
# Setup:
#   1. Register app in Azure Portal (App registrations → New → Public client)
#   2. Add permissions: Mail.Read, Chat.Read, Calendars.Read
#   3. Set MS_GRAPH_CLIENT_ID in .env
#   4. Run: python -m app.ingestion.graph_api.auth (one-time device code login)
#   5. Then run this script
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Syncing corporate email (inbox)"
.venv/bin/python -m app.ingestion.graph_api.email_sync --folder inbox "$@"

echo "==> Syncing corporate email (sentitems)"
.venv/bin/python -m app.ingestion.graph_api.email_sync --folder sentitems --source-name corporate_email_sent "$@"

echo "==> Done"
