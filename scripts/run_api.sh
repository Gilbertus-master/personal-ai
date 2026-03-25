#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/.."
source .venv/bin/activate

# Fix WSL2 MTU to prevent SSL errors on large downloads
sudo -n ip link set dev eth0 mtu 1400 2>/dev/null || true

uvicorn app.api.main:app --reload