#!/bin/bash
# Deploy Omnius to remote server via rsync + SSH + docker compose
#
# Usage:
#   bash scripts/deploy_omnius.sh [tenant]
#   bash scripts/deploy_omnius.sh ref
#   bash scripts/deploy_omnius.sh reh
#
# Requires:
#   - SSH key at ~/.ssh/omnius_${TENANT}_deploy
#   - Remote server with Docker + docker compose
#   - OMNIUS_${TENANT^^}_DEPLOY_HOST in .env (or default from config below)

set -euo pipefail
cd /home/sebastian/personal-ai

TENANT="${1:-ref}"
TENANT_UPPER=$(echo "$TENANT" | tr '[:lower:]' '[:upper:]')

# Load config from .env
source .env 2>/dev/null || true

# Deploy config (override via env vars)
REMOTE_HOST="${!OMNIUS_${TENANT_UPPER}_DEPLOY_HOST:-}"
REMOTE_USER="${!OMNIUS_${TENANT_UPPER}_DEPLOY_USER:-omnius-deploy}"
SSH_KEY="${!OMNIUS_${TENANT_UPPER}_DEPLOY_KEY:-$HOME/.ssh/omnius_${TENANT}_deploy}"
REMOTE_DIR="${!OMNIUS_${TENANT_UPPER}_DEPLOY_DIR:-/opt/omnius}"

# Fallback defaults
if [ -z "$REMOTE_HOST" ]; then
    case "$TENANT" in
        ref) REMOTE_HOST="omnius-ref.re-fuels.com" ;;
        reh) REMOTE_HOST="omnius-reh.respect.energy" ;;
        *)   echo "ERROR: Unknown tenant '$TENANT' and no OMNIUS_${TENANT_UPPER}_DEPLOY_HOST set"; exit 1 ;;
    esac
fi

echo "═══════════════════════════════════════════════"
echo "  OMNIUS DEPLOY — tenant: $TENANT"
echo "  Host: $REMOTE_HOST"
echo "  User: $REMOTE_USER"
echo "  Dir:  $REMOTE_DIR"
echo "═══════════════════════════════════════════════"

# Verify SSH key exists
if [ ! -f "$SSH_KEY" ]; then
    echo "ERROR: SSH key not found: $SSH_KEY"
    echo "Create it with: ssh-keygen -t ed25519 -f $SSH_KEY -N ''"
    echo "Then add the public key to $REMOTE_USER@$REMOTE_HOST"
    exit 1
fi

SSH_OPTS="-i $SSH_KEY -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10"

# 1. Test SSH connection
echo ""
echo ">>> Testing SSH connection..."
if ! ssh $SSH_OPTS ${REMOTE_USER}@${REMOTE_HOST} "echo 'SSH OK'" 2>/dev/null; then
    echo "ERROR: Cannot connect via SSH to ${REMOTE_USER}@${REMOTE_HOST}"
    exit 1
fi

# 2. Sync omnius/ code via rsync
echo ""
echo ">>> Syncing code (omnius/ → ${REMOTE_HOST}:${REMOTE_DIR}/omnius/)..."
rsync -avz --delete \
    --exclude='__pycache__' \
    --exclude='.env' \
    --exclude='*.pyc' \
    -e "ssh $SSH_OPTS" \
    omnius/ ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}/omnius/

# 3. Run migrations
echo ""
echo ">>> Running migrations..."
ssh $SSH_OPTS ${REMOTE_USER}@${REMOTE_HOST} bash -s <<'REMOTE_SCRIPT'
cd /opt/omnius
for f in omnius/db/migrations/*.sql; do
    echo "  Migration: $f"
    docker exec omnius-postgres psql -U omnius -d omnius_ref -f /docker-entrypoint-initdb.d/$(basename $f) 2>&1 || true
done
REMOTE_SCRIPT

# 4. Rebuild and restart
echo ""
echo ">>> Rebuilding and restarting containers..."
ssh $SSH_OPTS ${REMOTE_USER}@${REMOTE_HOST} \
    "cd ${REMOTE_DIR} && docker compose -f omnius/docker-compose.yml up -d --build"

# 5. Wait and health check
echo ""
echo ">>> Waiting for startup (10s)..."
sleep 10

echo ">>> Health check..."
HEALTH=$(curl -sf --max-time 10 "https://${REMOTE_HOST}/health" 2>/dev/null || echo '{"status":"unreachable"}')
echo "  $HEALTH"

STATUS=$(echo "$HEALTH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null || echo "unknown")

if [ "$STATUS" = "ok" ]; then
    echo ""
    echo "✅ Deploy successful — Omnius $TENANT is healthy"
    COMMIT=$(git log --oneline -1 2>/dev/null || echo "unknown")
    echo "  Commit: $COMMIT"
    echo "  Time: $(date '+%Y-%m-%d %H:%M:%S %Z')"
else
    echo ""
    echo "⚠️  Deploy completed but health check returned: $STATUS"
    echo "  Check logs: ssh $SSH_OPTS ${REMOTE_USER}@${REMOTE_HOST} 'docker logs omnius-api --tail 50'"
fi
