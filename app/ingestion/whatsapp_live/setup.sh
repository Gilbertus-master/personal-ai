#!/usr/bin/env bash
# Setup script for the WhatsApp live listener.
#
# Run once:
#   bash app/ingestion/whatsapp_live/setup.sh
#
# This will:
# 1. Install Node.js dependencies (Baileys)
# 2. Create ~/.gilbertus/whatsapp_listener/ directory
# 3. Install systemd user service for the listener daemon
# 4. Install cron job for the Python importer (every 5 minutes)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

echo "=== WhatsApp Live Listener Setup ==="
echo "Script dir:  $SCRIPT_DIR"
echo "Project dir: $PROJECT_DIR"
echo

# ── 1. Install Node.js dependencies ──────────────────────────────────

echo "Installing Node.js dependencies..."
cd "$SCRIPT_DIR"
npm install
echo "Done."
echo

# ── 2. Create runtime directories ────────────────────────────────────

echo "Creating runtime directories..."
mkdir -p "$HOME/.gilbertus/whatsapp_listener/auth"
echo "Done."
echo

# ── 3. Create systemd user service ──────────────────────────────────

SYSTEMD_DIR="$HOME/.config/systemd/user"
mkdir -p "$SYSTEMD_DIR"

SERVICE_FILE="$SYSTEMD_DIR/whatsapp-listener.service"
cat > "$SERVICE_FILE" << SERVICEEOF
[Unit]
Description=WhatsApp Message Listener for Gilbertus Albans
After=network.target

[Service]
Type=simple
WorkingDirectory=$SCRIPT_DIR
ExecStart=/usr/bin/node $SCRIPT_DIR/listener.js
Restart=always
RestartSec=10
StandardOutput=append:$HOME/.gilbertus/whatsapp_listener/service.log
StandardError=append:$HOME/.gilbertus/whatsapp_listener/service.log

# Environment
Environment=NODE_ENV=production
Environment=HOME=$HOME

[Install]
WantedBy=default.target
SERVICEEOF

echo "Systemd service created at: $SERVICE_FILE"
echo

# ── 4. Set up cron for the Python importer ───────────────────────────

CRON_CMD="cd $PROJECT_DIR && /usr/bin/python3 -m app.ingestion.whatsapp_live.importer >> $HOME/.gilbertus/whatsapp_listener/importer.log 2>&1"
CRON_LINE="*/5 * * * * $CRON_CMD"

# Check if cron entry already exists
if crontab -l 2>/dev/null | grep -qF "app.ingestion.whatsapp_live.importer"; then
    echo "Cron job already exists — skipping."
else
    (crontab -l 2>/dev/null || true; echo "$CRON_LINE") | crontab -
    echo "Cron job installed (every 5 minutes)."
fi
echo

# ── 5. Instructions ──────────────────────────────────────────────────

echo "=== Setup Complete ==="
echo
echo "NEXT STEPS:"
echo
echo "1. Start the listener for initial pairing:"
echo "   cd $SCRIPT_DIR && node listener.js"
echo "   (Scan the QR code with WhatsApp > Linked Devices)"
echo
echo "2. After pairing succeeds, enable the systemd service:"
echo "   systemctl --user daemon-reload"
echo "   systemctl --user enable whatsapp-listener"
echo "   systemctl --user start whatsapp-listener"
echo
echo "3. The Python importer runs via cron every 5 minutes."
echo "   To run manually:"
echo "   cd $PROJECT_DIR && python -m app.ingestion.whatsapp_live.importer"
echo
echo "4. Monitor:"
echo "   tail -f ~/.gilbertus/whatsapp_listener/listener.log"
echo "   tail -f ~/.gilbertus/whatsapp_listener/importer.log"
echo "   journalctl --user -u whatsapp-listener -f"
