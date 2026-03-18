#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Usuwam backupy starsze niz 30 dni"
find backups/db -mindepth 1 -maxdepth 1 -type d -mtime +30 -print -exec rm -rf {} \;

echo "==> Gotowe"