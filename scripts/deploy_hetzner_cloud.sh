#!/usr/bin/env bash
# deploy_hetzner_cloud.sh — Provision a Hetzner Cloud VPS and deploy Gilbertus.
#
# Usage:
#   ./scripts/deploy_hetzner_cloud.sh <HETZNER_API_TOKEN>
#
# What it does:
#   1. Creates/uploads an SSH key to Hetzner
#   2. Creates a CAX31 ARM VPS (8 vCPU, 32GB RAM, 320GB SSD) in Falkenstein
#   3. Waits for the server to boot and become reachable
#   4. SSHs in and sets up the full Gilbertus stack
#   5. Prints connection info and next steps
#
# Prerequisites:
#   - curl and jq installed locally
#   - A Hetzner Cloud API token (https://console.hetzner.cloud → API tokens)
#
# Cost: ~EUR 16/month for CAX31
#
set -euo pipefail

# ── Args ──────────────────────────────────────────────────────────────────────

if [ $# -lt 1 ]; then
    echo "Usage: $0 <HETZNER_API_TOKEN>"
    echo ""
    echo "Get your token at: https://console.hetzner.cloud → select project → API Tokens"
    exit 1
fi

HETZNER_TOKEN="$1"
SERVER_NAME="gilbertus"
SERVER_TYPE="cax31"          # ARM64, 8 vCPU, 32GB RAM, 320GB SSD — EUR 16/mo
LOCATION="fsn1"              # Falkenstein, Germany (closest to Poland)
IMAGE="ubuntu-24.04"
SSH_KEY_NAME="gilbertus-deploy"
SSH_KEY_PATH="$HOME/.ssh/gilbertus_hetzner"

HETZNER_API="https://api.hetzner.cloud/v1"

# ── Helper functions ──────────────────────────────────────────────────────────

hcloud_api() {
    local method="$1"
    local endpoint="$2"
    shift 2
    curl -sf -X "$method" \
        -H "Authorization: Bearer $HETZNER_TOKEN" \
        -H "Content-Type: application/json" \
        "$HETZNER_API$endpoint" "$@"
}

log() { echo "[$(date '+%H:%M:%S')] $*"; }
die() { echo "ERROR: $*" >&2; exit 1; }

# ── Preflight checks ─────────────────────────────────────────────────────────

for cmd in curl jq ssh-keygen ssh scp; do
    command -v "$cmd" >/dev/null 2>&1 || die "$cmd is required but not installed"
done

# Validate token
log "Validating Hetzner API token..."
TOKEN_CHECK=$(hcloud_api GET "/servers?per_page=1" 2>/dev/null || echo "FAIL")
if [ "$TOKEN_CHECK" = "FAIL" ] || echo "$TOKEN_CHECK" | jq -e '.error' >/dev/null 2>&1; then
    die "Invalid Hetzner API token. Check your token and try again."
fi
log "Token OK."

# ── Step 1: SSH key ──────────────────────────────────────────────────────────

if [ ! -f "$SSH_KEY_PATH" ]; then
    log "Generating SSH key at $SSH_KEY_PATH..."
    ssh-keygen -t ed25519 -f "$SSH_KEY_PATH" -N "" -C "gilbertus-deploy"
else
    log "SSH key already exists at $SSH_KEY_PATH"
fi

SSH_PUB_KEY=$(cat "${SSH_KEY_PATH}.pub")

# Check if this key is already uploaded to Hetzner
log "Checking for existing SSH key in Hetzner..."
EXISTING_KEY_ID=$(hcloud_api GET "/ssh_keys" | \
    jq -r --arg name "$SSH_KEY_NAME" '.ssh_keys[] | select(.name == $name) | .id' 2>/dev/null || echo "")

if [ -n "$EXISTING_KEY_ID" ]; then
    SSH_KEY_ID="$EXISTING_KEY_ID"
    log "Using existing SSH key (ID: $SSH_KEY_ID)"
else
    log "Uploading SSH key to Hetzner..."
    SSH_KEY_RESP=$(hcloud_api POST "/ssh_keys" \
        -d "{\"name\": \"$SSH_KEY_NAME\", \"public_key\": \"$SSH_PUB_KEY\"}")
    SSH_KEY_ID=$(echo "$SSH_KEY_RESP" | jq -r '.ssh_key.id')
    if [ -z "$SSH_KEY_ID" ] || [ "$SSH_KEY_ID" = "null" ]; then
        die "Failed to upload SSH key: $SSH_KEY_RESP"
    fi
    log "SSH key uploaded (ID: $SSH_KEY_ID)"
fi

# ── Step 2: Check if server already exists ───────────────────────────────────

EXISTING_SERVER=$(hcloud_api GET "/servers?name=$SERVER_NAME" | \
    jq -r '.servers[0].id // empty' 2>/dev/null || echo "")

if [ -n "$EXISTING_SERVER" ]; then
    SERVER_ID="$EXISTING_SERVER"
    SERVER_IP=$(hcloud_api GET "/servers/$SERVER_ID" | jq -r '.server.public_net.ipv4.ip')
    log "Server '$SERVER_NAME' already exists (ID: $SERVER_ID, IP: $SERVER_IP)"
    log "Skipping creation — proceeding to setup."
else
    # ── Step 2b: Create the VPS ──────────────────────────────────────────────
    log "Creating VPS: $SERVER_NAME ($SERVER_TYPE in $LOCATION)..."

    CREATE_RESP=$(hcloud_api POST "/servers" -d "{
        \"name\": \"$SERVER_NAME\",
        \"server_type\": \"$SERVER_TYPE\",
        \"location\": \"$LOCATION\",
        \"image\": \"$IMAGE\",
        \"ssh_keys\": [$SSH_KEY_ID],
        \"public_net\": {
            \"enable_ipv4\": true,
            \"enable_ipv6\": true
        }
    }")

    SERVER_ID=$(echo "$CREATE_RESP" | jq -r '.server.id')
    SERVER_IP=$(echo "$CREATE_RESP" | jq -r '.server.public_net.ipv4.ip')

    if [ -z "$SERVER_ID" ] || [ "$SERVER_ID" = "null" ]; then
        die "Failed to create server: $CREATE_RESP"
    fi

    log "Server created (ID: $SERVER_ID, IP: $SERVER_IP)"

    # ── Step 3: Wait for server to boot ──────────────────────────────────────
    log "Waiting for server to become ready..."
    for i in $(seq 1 60); do
        STATUS=$(hcloud_api GET "/servers/$SERVER_ID" | jq -r '.server.status')
        if [ "$STATUS" = "running" ]; then
            log "Server status: running"
            break
        fi
        if [ "$i" -eq 60 ]; then
            die "Server did not become ready after 5 minutes"
        fi
        sleep 5
    done

    # Wait for SSH to become available
    log "Waiting for SSH to become reachable..."
    for i in $(seq 1 60); do
        if ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 \
               -o BatchMode=yes -i "$SSH_KEY_PATH" \
               root@"$SERVER_IP" "echo OK" >/dev/null 2>&1; then
            log "SSH is up."
            break
        fi
        if [ "$i" -eq 60 ]; then
            die "SSH not reachable after 5 minutes"
        fi
        sleep 5
    done
fi

# ── SSH helper ────────────────────────────────────────────────────────────────

remote() {
    ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 \
        -i "$SSH_KEY_PATH" root@"$SERVER_IP" "$@"
}

# ── Step 4: Server setup ─────────────────────────────────────────────────────

log "Starting server setup on $SERVER_IP..."

remote bash -s <<'SETUP_SCRIPT'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

echo "==> Updating system packages..."
apt-get update -qq
apt-get upgrade -y -qq

# ── Docker ────────────────────────────────────────────────────────────────────
echo "==> Installing Docker..."
if ! command -v docker >/dev/null 2>&1; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable --now docker
fi
docker --version

# docker compose plugin (comes with Docker install above, but verify)
docker compose version || {
    apt-get install -y -qq docker-compose-plugin
}

# ── Python 3.12 ──────────────────────────────────────────────────────────────
echo "==> Installing Python 3.12..."
apt-get install -y -qq python3.12 python3.12-venv python3.12-dev python3-pip git

# ── Clone the repo ───────────────────────────────────────────────────────────
echo "==> Cloning personal-ai..."
PROJECT_DIR="/opt/personal-ai"
if [ -d "$PROJECT_DIR" ]; then
    echo "    Repo already exists, pulling latest..."
    cd "$PROJECT_DIR"
    git pull --ff-only || true
else
    git clone https://github.com/gilbertus-master/personal-ai.git "$PROJECT_DIR"
    cd "$PROJECT_DIR"
fi

# ── Python venv ──────────────────────────────────────────────────────────────
echo "==> Setting up Python venv..."
if [ ! -d .venv ]; then
    python3.12 -m venv .venv
fi
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q

# ── .env file ────────────────────────────────────────────────────────────────
echo "==> Setting up .env..."
if [ ! -f .env ]; then
    cp .env.example .env
    # Generate a random Postgres password
    PG_PASS=$(openssl rand -base64 24 | tr -d '/+=')
    sed -i "s/POSTGRES_PASSWORD=REPLACE_ME/POSTGRES_PASSWORD=$PG_PASS/" .env
    echo "    .env created from template — you MUST fill in API keys manually."
else
    echo "    .env already exists, skipping."
fi

# ── Docker services (Postgres, Qdrant, Whisper) ─────────────────────────────
echo "==> Starting Docker services..."
# Source .env for docker compose
set -a; source .env; set +a
docker compose up -d
echo "    Waiting for services to become healthy..."
sleep 10
docker compose ps

# ── Run migrations ───────────────────────────────────────────────────────────
echo "==> Running database migrations..."
if [ -f scripts/run_migrations.sh ]; then
    bash scripts/run_migrations.sh || echo "    WARNING: migrations had issues (may be first run)"
fi

# ── Systemd service: gilbertus-api ───────────────────────────────────────────
echo "==> Creating systemd service: gilbertus-api..."
cat > /etc/systemd/system/gilbertus-api.service <<EOF
[Unit]
Description=Gilbertus API (uvicorn)
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/personal-ai
EnvironmentFile=/opt/personal-ai/.env
ExecStart=/opt/personal-ai/.venv/bin/uvicorn app.api.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable gilbertus-api
systemctl start gilbertus-api || echo "    WARNING: API may fail until .env is configured"

# ── Systemd service: openclaw (MCP server) ───────────────────────────────────
echo "==> Creating systemd service: openclaw (MCP)..."
cat > /etc/systemd/system/openclaw.service <<EOF
[Unit]
Description=OpenClaw MCP Server (Gilbertus)
After=network.target gilbertus-api.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/personal-ai
EnvironmentFile=/opt/personal-ai/.env
ExecStart=/opt/personal-ai/.venv/bin/python -m mcp_gilbertus.server
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable openclaw
systemctl start openclaw || echo "    WARNING: MCP server may fail until .env is configured"

# ── Cron jobs ────────────────────────────────────────────────────────────────
echo "==> Setting up cron jobs..."
CRON_FILE="/etc/cron.d/gilbertus"
cat > "$CRON_FILE" <<'CRONEOF'
# Gilbertus cron jobs
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
TIKTOKEN_CACHE_DIR=/tmp/tiktoken_cache
PROJECT=/opt/personal-ai

# Morning brief — daily at 7:00 CET
0 7 * * * root cd $PROJECT && bash scripts/morning_brief.sh >> logs/morning_brief.log 2>&1

# Corporate data sync — hourly at :15
15 * * * * root cd $PROJECT && bash scripts/sync_corporate_data.sh >> logs/sync_corporate.log 2>&1

# Plaud monitor — every 15 minutes
*/15 * * * * root cd $PROJECT && bash scripts/plaud_monitor.sh >> logs/plaud_monitor.log 2>&1

# DB backup — daily at 3:00
0 3 * * * root cd $PROJECT && bash scripts/backup_db.sh >> logs/backup.log 2>&1

# Backup pruning — weekly Sunday at 4:00
0 4 * * 0 root cd $PROJECT && bash scripts/prune_backups.sh >> logs/prune.log 2>&1
CRONEOF
chmod 644 "$CRON_FILE"

mkdir -p /opt/personal-ai/logs

# ── Firewall (ufw) ──────────────────────────────────────────────────────────
echo "==> Configuring firewall..."
apt-get install -y -qq ufw
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment "SSH"
ufw allow 80/tcp comment "HTTP (Caddy)"
ufw allow 443/tcp comment "HTTPS (Caddy)"
ufw allow 8000/tcp comment "Gilbertus API (direct)"
echo "y" | ufw enable
ufw status

# ── Caddy (HTTPS reverse proxy) ─────────────────────────────────────────────
echo "==> Installing Caddy..."
apt-get install -y -qq debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | \
    gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg 2>/dev/null
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | \
    tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
apt-get update -qq
apt-get install -y -qq caddy

# Caddyfile — reverse proxy to the API
# Uses IP-based config initially; replace YOUR_DOMAIN with real domain for auto-HTTPS
cat > /etc/caddy/Caddyfile <<'CADDY'
# Gilbertus API reverse proxy
#
# Option A: IP-only (no HTTPS, for testing)
:80 {
    reverse_proxy localhost:8000
}

# Option B: Domain with auto-HTTPS (uncomment and set your domain)
# gilbertus.example.com {
#     reverse_proxy localhost:8000
# }
CADDY

systemctl enable caddy
systemctl restart caddy

# ── Set timezone ─────────────────────────────────────────────────────────────
timedatectl set-timezone Europe/Warsaw

echo ""
echo "============================================"
echo "  Server setup complete!"
echo "============================================"
SETUP_SCRIPT

# ── Step 5: Print connection info ─────────────────────────────────────────────

echo ""
echo "================================================================"
echo "  GILBERTUS VPS DEPLOYED"
echo "================================================================"
echo ""
echo "  Server IP:     $SERVER_IP"
echo "  Server ID:     $SERVER_ID"
echo "  Server type:   $SERVER_TYPE (8 vCPU, 32GB RAM, 320GB SSD)"
echo "  Location:      $LOCATION (Falkenstein, DE)"
echo "  Cost:          ~EUR 16/month"
echo ""
echo "  SSH:           ssh -i $SSH_KEY_PATH root@$SERVER_IP"
echo "  API:           http://$SERVER_IP:8000"
echo "  API (Caddy):   http://$SERVER_IP"
echo ""
echo "================================================================"
echo "  NEXT STEPS"
echo "================================================================"
echo ""
echo "  1. Configure API keys in .env:"
echo "     ssh -i $SSH_KEY_PATH root@$SERVER_IP"
echo "     nano /opt/personal-ai/.env"
echo "     # Fill in: OPENAI_API_KEY, ANTHROPIC_API_KEY, etc."
echo "     systemctl restart gilbertus-api"
echo ""
echo "  2. Set up GitHub deploy key (for private repo):"
echo "     ssh -i $SSH_KEY_PATH root@$SERVER_IP"
echo "     ssh-keygen -t ed25519 -f ~/.ssh/github_deploy -N ''"
echo "     cat ~/.ssh/github_deploy.pub"
echo "     # Add to GitHub repo → Settings → Deploy keys"
echo ""
echo "  3. Migrate data from laptop:"
echo "     ./scripts/migrate_data_to_server.sh $SERVER_IP"
echo ""
echo "  4. Set up domain + HTTPS:"
echo "     # Point DNS A record to $SERVER_IP"
echo "     # Edit /etc/caddy/Caddyfile on server"
echo "     # Uncomment the domain block, set your domain"
echo "     # systemctl restart caddy"
echo ""
echo "  5. Verify everything works:"
echo "     curl http://$SERVER_IP:8000/health"
echo ""
echo "================================================================"
