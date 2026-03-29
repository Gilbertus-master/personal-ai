#!/bin/bash
set -e

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
PKG_DIR=$(dirname "$SCRIPT_DIR")

# Fetch latest OpenAPI spec
echo "Fetching OpenAPI spec from backend..."
curl -sf http://127.0.0.1:8000/openapi.json -o "$PKG_DIR/openapi.json"

# Generate client
cd "$PKG_DIR" && npx orval

echo "API client generated successfully"
