#!/usr/bin/env bash
# ============================================================================
# fix_wsl2_mtu.sh -- Fix WSL2 SSL DECRYPTION_FAILED_OR_BAD_RECORD_MAC errors
#
# Root cause:
#   WSL2's virtual network adapter defaults to MTU 1500. The Hyper-V vSwitch
#   can silently corrupt large TLS records during IP fragmentation, causing:
#     ssl.SSLError: [SSL: DECRYPTION_FAILED_OR_BAD_RECORD_MAC]
#   This only hits large downloads (>1 MB) because small responses fit in a
#   single TLS record that doesn't get fragmented.
#
# Fix:
#   Lower MTU to 1400 so packets stay under the internal vSwitch MTU.
#
# Usage:
#   sudo bash scripts/fix_wsl2_mtu.sh          # apply now
#   sudo bash scripts/fix_wsl2_mtu.sh --persist # apply now + make permanent
# ============================================================================
set -euo pipefail

TARGET_MTU=1400
IFACE="eth0"

# Detect WSL2
if ! grep -qi "microsoft\|wsl" /proc/version 2>/dev/null; then
    echo "Not running on WSL2 -- nothing to do."
    exit 0
fi

CURRENT_MTU=$(cat /sys/class/net/$IFACE/mtu 2>/dev/null || echo "unknown")
echo "Current MTU on $IFACE: $CURRENT_MTU"

if [ "$CURRENT_MTU" -le "$TARGET_MTU" ] 2>/dev/null; then
    echo "MTU already <= $TARGET_MTU -- OK."
else
    echo "Setting MTU to $TARGET_MTU..."
    ip link set dev "$IFACE" mtu "$TARGET_MTU"
    echo "Done. New MTU: $(cat /sys/class/net/$IFACE/mtu)"
fi

# Persist via wsl.conf networkingMode or /etc/network/interfaces.d/
if [ "${1:-}" = "--persist" ]; then
    echo ""
    echo "Making MTU fix permanent..."

    # Method 1: /etc/wsl.conf [network] section (WSL2 2.0+)
    # This is the cleanest approach but requires recent WSL2.
    # Method 2: Post-up script via /etc/network/interfaces.d/ (more compatible)

    PERSIST_SCRIPT="/etc/network/if-up.d/fix-mtu"
    cat > "$PERSIST_SCRIPT" << 'INNER_EOF'
#!/bin/sh
# Fix WSL2 MTU for SSL compatibility
if [ "$IFACE" = "eth0" ]; then
    ip link set dev eth0 mtu 1400
fi
INNER_EOF
    chmod +x "$PERSIST_SCRIPT"
    echo "Created $PERSIST_SCRIPT -- MTU will be fixed on every network-up."

    # Also add to .bashrc as belt-and-suspenders for shells that start
    # before networking hooks fire.
    PROFILE_LINE='# WSL2 MTU fix for SSL'
    BASHRC="$HOME/.bashrc"
    if [ -f "$BASHRC" ] && ! grep -q "fix-mtu\|mtu 1400" "$BASHRC" 2>/dev/null; then
        echo "" >> "$BASHRC"
        echo "$PROFILE_LINE" >> "$BASHRC"
        echo 'sudo -n ip link set dev eth0 mtu 1400 2>/dev/null || true' >> "$BASHRC"
        echo "Added MTU fix to $BASHRC"
    fi

    echo ""
    echo "Persistent fix applied. Verify after WSL restart with:"
    echo "  cat /sys/class/net/eth0/mtu"
fi

echo ""
echo "Test with a large download:"
echo "  python -c \"import requests; r = requests.get('https://speed.hetzner.de/1GB.bin', stream=True, timeout=30); [None for _ in zip(range(200), r.iter_content(65536))]; print('OK')\""
