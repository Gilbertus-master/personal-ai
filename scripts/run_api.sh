#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/.."
source .venv/bin/activate
uvicorn app.api.main:app --reload