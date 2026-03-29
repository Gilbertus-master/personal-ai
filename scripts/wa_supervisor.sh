#!/usr/bin/env bash
# WhatsApp Live Pipeline Supervisor
# Checks listener.js health and restarts if needed.
# Cron: */5 * * * * cd /home/sebastian/personal-ai && bash scripts/wa_supervisor.sh
#
# Checks:
# 1. PID file exists and process is alive
# 2. Health check endpoint responds
# 3. Last message not too stale (warn only — Bad MAC means re-pair needed)

set -euo pipefail

LOGFILE="/home/sebastian/personal-ai/logs/wa_supervisor.log"
PID_FILE="$HOME/.gilbertus/whatsapp_listener/listener.pid"
HEALTH_URL="http://127.0.0.1:9393/health"
STALE_THRESHOLD=3600  # 1 hour — warn if no messages for this long

log() {
    echo "[$(date -u '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOGFILE"
}

# 1. Check if systemd service is active
if systemctl --user is-active whatsapp-listener.service >/dev/null 2>&1; then
    SERVICE_ACTIVE=true
else
    SERVICE_ACTIVE=false
fi

# 2. Check PID file
PID_ALIVE=false
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        PID_ALIVE=true
    fi
fi

# 3. Health check
HEALTH_OK=false
CONNECTED=false
LAST_MSG=""
if HEALTH_RESPONSE=$(curl -s --max-time 5 "$HEALTH_URL" 2>/dev/null); then
    HEALTH_OK=true
    CONNECTED=$(echo "$HEALTH_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('connected', False))" 2>/dev/null || echo "false")
    LAST_MSG=$(echo "$HEALTH_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('last_msg_at', ''))" 2>/dev/null || echo "")
fi

# Decision logic
if [ "$SERVICE_ACTIVE" = "false" ]; then
    log "RESTART: systemd service not active. Starting..."
    systemctl --user start whatsapp-listener.service
    log "RESTART: service start command issued"
elif [ "$PID_ALIVE" = "false" ] && [ "$HEALTH_OK" = "false" ]; then
    log "RESTART: PID dead and health check failed. Restarting service..."
    systemctl --user restart whatsapp-listener.service
    log "RESTART: service restart command issued"
elif [ "$CONNECTED" = "False" ] || [ "$CONNECTED" = "false" ]; then
    log "WARN: listener running but not connected to WhatsApp Web"
else
    # Check staleness
    if [ -n "$LAST_MSG" ] && [ "$LAST_MSG" != "null" ] && [ "$LAST_MSG" != "None" ]; then
        LAST_EPOCH=$(date -d "$LAST_MSG" +%s 2>/dev/null || echo 0)
        NOW_EPOCH=$(date +%s)
        AGE=$((NOW_EPOCH - LAST_EPOCH))
        if [ "$AGE" -gt "$STALE_THRESHOLD" ]; then
            log "WARN: last message ${AGE}s ago (>${STALE_THRESHOLD}s). May need re-pair."
        fi
    fi
    # All OK — silent (don't spam log)
fi
