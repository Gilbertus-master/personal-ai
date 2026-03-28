#!/usr/bin/env bash
# health_check.sh — Monitor all Gilbertus services.
# Runs via cron every 5 minutes. Logs issues and optionally restarts services.
# Works on both laptop (WSL2) and Hetzner server.
set -euo pipefail

cd "$(dirname "$0")/.."
PROJECT="$(pwd)"

TIMESTAMP="$(date '+%F %T')"
ISSUES=0

log() { echo "[$TIMESTAMP] $*"; }
warn() { echo "[$TIMESTAMP] WARNING: $*"; ISSUES=$((ISSUES + 1)); }
ok() { echo "[$TIMESTAMP] OK: $*"; }

log "=== Health check starting ==="

# 1. Check Docker containers
for container in gilbertus-postgres gilbertus-qdrant gilbertus-whisper; do
    STATUS=$(docker inspect --format='{{.State.Status}}' "$container" 2>/dev/null || echo "missing")
    if [ "$STATUS" = "running" ]; then
        ok "$container is running"
    else
        warn "$container is $STATUS — attempting restart"
        docker compose up -d 2>&1 || true
    fi
done

# 2. Check Postgres connectivity
if docker exec gilbertus-postgres pg_isready -U gilbertus >/dev/null 2>&1; then
    ok "Postgres is accepting connections"
else
    warn "Postgres is not accepting connections"
fi

# 3. Check Qdrant API
if curl -sf http://localhost:6333/healthz >/dev/null 2>&1; then
    ok "Qdrant is healthy"
else
    warn "Qdrant healthz failed"
fi

# 4. Check Whisper API
if curl -sf http://localhost:9090/health >/dev/null 2>&1; then
    ok "Whisper is healthy"
else
    warn "Whisper health check failed"
fi

# 5. Check Gilbertus API
if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
    ok "Gilbertus API is healthy"
else
    warn "Gilbertus API is down — attempting restart"
    systemctl restart gilbertus-api 2>&1 || systemctl --user restart gilbertus-api 2>&1 || true
fi

# 6. Check OpenClaw gateway
if systemctl is-active --quiet openclaw-gateway 2>/dev/null || systemctl --user is-active --quiet openclaw-gateway 2>/dev/null; then
    ok "OpenClaw gateway is running"
else
    warn "OpenClaw gateway is down — attempting restart"
    systemctl restart openclaw-gateway 2>&1 || systemctl --user restart openclaw-gateway 2>&1 || true
fi

# 7. Check WhatsApp listener
if systemctl is-active --quiet whatsapp-listener 2>/dev/null || systemctl --user is-active --quiet whatsapp-listener 2>/dev/null; then
    ok "WhatsApp listener is running"
else
    # Don't auto-restart — may need QR pairing
    warn "WhatsApp listener is not running (may need QR pairing)"
fi

# 8. Check Caddy (server only)
if command -v caddy >/dev/null 2>&1; then
    if systemctl is-active --quiet caddy 2>/dev/null; then
        ok "Caddy is running"
    else
        warn "Caddy is down — attempting restart"
        systemctl restart caddy 2>&1 || true
    fi
fi

# 9. Check disk space
DISK_PCT=$(df / --output=pcent | tail -1 | tr -d ' %')
if [ "$DISK_PCT" -lt 85 ]; then
    ok "Disk usage: ${DISK_PCT}%"
else
    warn "Disk usage is high: ${DISK_PCT}%"
fi

# 10. Check memory
MEM_PCT=$(free | awk '/Mem:/ {printf "%d", $3/$2 * 100}')
if [ "$MEM_PCT" -lt 90 ]; then
    ok "Memory usage: ${MEM_PCT}%"
else
    warn "Memory usage is high: ${MEM_PCT}%"
fi

# Summary
if [ "$ISSUES" -eq 0 ]; then
    log "=== All checks passed ==="
else
    log "=== $ISSUES issue(s) detected ==="
fi

# 11. Python-based deep health check (DB baseline, extraction, API costs, WhatsApp alerts)
log "Running deep health check..."
"$PROJECT/.venv/bin/python" -c "
from app.analysis.health_monitor import run_health_check
import json
result = run_health_check(send_alerts=True)
print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
" 2>&1 || log "Deep health check failed"
