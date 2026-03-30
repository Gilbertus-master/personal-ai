#!/usr/bin/env bash
set -euo pipefail

KEY_DIR="${HOME}/.tauri"
KEY_FILE="${KEY_DIR}/gilbertus.key"

echo "=== Tauri Update Signing Keys Generator ==="
echo ""

# Check if cargo-tauri is installed
if ! command -v cargo-tauri &>/dev/null; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] Installing tauri-cli..."
  cargo install tauri-cli
fi

# Check if key already exists
if [ -f "$KEY_FILE" ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WARN] Key already exists at $KEY_FILE"
  echo "       Delete it first if you want to regenerate."
  echo ""
  echo "=== Existing public key:"
  cat "${KEY_FILE}.pub"
  exit 0
fi

# Create directory
mkdir -p "$KEY_DIR"

# Generate key pair
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] Generating signing key pair..."
cargo tauri signer generate -w "$KEY_FILE"

echo ""
echo "=== DONE ==="
echo ""
echo "1. PUBLIC KEY (add to tauri.conf.json -> plugins.updater.pubkey):"
echo "   $(cat "${KEY_FILE}.pub")"
echo ""
echo "2. PRIVATE KEY (add to GitHub Secrets -> TAURI_SIGNING_PRIVATE_KEY):"
echo "   File: $KEY_FILE"
echo "   Run: cat '${KEY_FILE}' | base64"
echo ""
echo "3. KEY PASSWORD (add to GitHub Secrets -> TAURI_KEY_PASSWORD):"
echo "   The password you entered during generation"
