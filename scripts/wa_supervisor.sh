#!/usr/bin/env bash
# WhatsApp Live Pipeline Supervisor
# Quick health check — delegates repair logic to wa_repair_monitor.py.
# Cron: */5 * * * * cd /home/sebastian/personal-ai && bash scripts/wa_supervisor.sh
#
# This script handles basic liveness checks. For Bad MAC / session drift
# detection and automated re-pair, see wa_repair_monitor.py (cron */3).

set -euo pipefail

LOGFILE="/home/sebastian/personal-ai/logs/wa_supervisor.log"
PID_FILE="$HOME/.gilbertus/whatsapp_listener/listener.pid"
HEALTH_URL="http://127.0.0.1:9393/health"
NEEDS_REPAIR_FLAG="$HOME/.gilbertus/whatsapp_listener/needs_repair.flag"
REPAIR_MONITOR="cd /home/sebastian/personal-ai && .venv/bin/python -m app.ingestion.whatsapp_live.wa_repair_monitor"
RESTART_COUNTER="/tmp/wa_supervisor_restart_count"

log() {
    echo "[$(date -u '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOGFILE"
}

record_restart() {
    COUNT=$(cat "$RESTART_COUNTER" 2>/dev/null || echo 0)
    COUNT=$((COUNT + 1))
    echo $COUNT > "$RESTART_COUNTER"
    log "RESTART_COUNT: $COUNT"
    if [ "$COUNT" -ge 3 ]; then
        curl -s -X POST http://127.0.0.1:8000/internal/notify \
            -H 'Content-Type: application/json' \
            -d '{"msg":"wa_supervisor: 3+ restarts in succession — possible crash-loop"}' \
            --max-time 5 || true
        echo 0 > "$RESTART_COUNTER"
    fi
}

# 0. If needs_repair.flag exists, delegate to repair monitor immediately
if [ -f "$NEEDS_REPAIR_FLAG" ]; then
    log "REPAIR: needs_repair.flag detected — delegating to wa_repair_monitor.py"
    eval "$REPAIR_MONITOR" 2>&1 | while read -r line; do log "REPAIR_MONITOR: $line"; done
    exit 0
fi

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
QR_PENDING=false
if HEALTH_RESPONSE=$(curl -s --max-time 5 "$HEALTH_URL" 2>/dev/null); then
    HEALTH_OK=true
    read -r CONNECTED LAST_MSG QR_PENDING < <(echo "$HEALTH_RESPONSE" | .venv/bin/python -c "
import sys, json
d = json.load(sys.stdin)
print(str(d.get('connected', False)), d.get('last_msg_at', '') or '', str(d.get('qr_pending', False)))
" 2>/dev/null || echo "false  false")
fi

# 4. If QR pending, let repair monitor handle it
if [ "$QR_PENDING" = "True" ] || [ "$QR_PENDING" = "true" ]; then
    log "INFO: QR pending — repair monitor will handle alerting"
    exit 0
fi

# Decision logic
if [ "$SERVICE_ACTIVE" = "false" ]; then
    log "RESTART: systemd service not active. Starting..."
    systemctl --user start whatsapp-listener.service
    log "RESTART: service start command issued"
    record_restart
elif [ "$PID_ALIVE" = "false" ] && [ "$HEALTH_OK" = "false" ]; then
    log "RESTART: PID dead and health check failed. Restarting service..."
    systemctl --user restart whatsapp-listener.service
    log "RESTART: service restart command issued"
    record_restart
elif [ "$CONNECTED" = "False" ] || [ "$CONNECTED" = "false" ]; then
    log "WARN: listener running but not connected to WhatsApp Web"
else
    # Check staleness (warn only — repair monitor handles alerts)
    if [ -n "$LAST_MSG" ] && [ "$LAST_MSG" != "null" ] && [ "$LAST_MSG" != "None" ]; then
        LAST_EPOCH=$(date -d "$LAST_MSG" +%s 2>/dev/null || echo 0)
        NOW_EPOCH=$(date +%s)
        AGE=$((NOW_EPOCH - LAST_EPOCH))
        if [ "$AGE" -gt 3600 ]; then
            log "WARN: last message ${AGE}s ago (>3600s). Repair monitor will alert if stale."
        fi
    fi
    # All OK — silent (don't spam log)
fi
