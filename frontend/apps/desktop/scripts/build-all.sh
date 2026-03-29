#!/bin/bash
set -e

echo "=== Building web app (static export) ==="
cd "$(dirname "$0")/../../.." && pnpm --filter @gilbertus/web build

echo "=== Building Tauri desktop ==="
cd apps/desktop && pnpm tauri build

echo "=== Build complete! Artifacts in src-tauri/target/release/bundle/ ==="
