#!/bin/bash
set -e

export TAURI_BUILD=1

cd "$(dirname "$0")/../../.."
pnpm --filter @gilbertus/web build

cd apps/desktop
cargo tauri build --config tauri-omnius.conf.json --features omnius
