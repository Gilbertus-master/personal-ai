#!/usr/bin/env bash
# Omnius One-Click Install & Launch
# Usage:
#   bash scripts/setup_omnius.sh ref        # Start REF tenant
#   bash scripts/setup_omnius.sh reh        # Start REH tenant
#   bash scripts/setup_omnius.sh all        # Start all tenants
#   bash scripts/setup_omnius.sh ref --no-browser
#
# Exit codes: 0 success, 1 missing prereqs, 2 build failed, 3 health check failed
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

OPEN_BROWSER=true
TENANT=""

# ── Parse args ────────────────────────────────────────────────────────
for arg in "$@"; do
    case "$arg" in
        --no-browser) OPEN_BROWSER=false ;;
        ref|reh|all)  TENANT="$arg" ;;
        -h|--help)
            echo "Usage: bash scripts/setup_omnius.sh <ref|reh|all> [--no-browser]"
            exit 0
            ;;
    esac
done

if [ -z "$TENANT" ]; then
    echo "Error: Specify tenant: ref, reh, or all"
    echo "Usage: bash scripts/setup_omnius.sh <ref|reh|all> [--no-browser]"
    exit 1
fi

# ── Colors ────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $*"; }

# ── 1. Check prerequisites ───────────────────────────────────────────
info "Checking prerequisites..."

MISSING=false

if ! command -v docker &>/dev/null; then
    fail "docker not found. Install: https://docs.docker.com/get-docker/"
    MISSING=true
fi

if ! docker compose version &>/dev/null 2>&1; then
    fail "docker compose (v2) not found. Install: https://docs.docker.com/compose/install/"
    MISSING=true
fi

if [ "$MISSING" = true ]; then
    exit 1
fi

ok "Prerequisites met."

# ── 2. Generate tenant .env files ─────────────────────────────────────
generate_tenant_env() {
    local tenant="$1"
    local env_file="$PROJECT_DIR/omnius/.env.${tenant}"
    local example_file=""

    # Pick the right example
    if [ "$tenant" = "reh" ] && [ -f "$PROJECT_DIR/omnius/.env.reh.example" ]; then
        example_file="$PROJECT_DIR/omnius/.env.reh.example"
    elif [ -f "$PROJECT_DIR/omnius/.env.example" ]; then
        example_file="$PROJECT_DIR/omnius/.env.example"
    fi

    if [ -f "$env_file" ]; then
        ok "Using existing $env_file"
        return
    fi

    if [ -z "$example_file" ]; then
        fail "No .env example found for tenant $tenant"
        return
    fi

    info "Generating $env_file from $(basename "$example_file")..."
    cp "$example_file" "$env_file"

    # Generate password
    local pw
    pw=$(openssl rand -hex 16)
    sed -i "s/POSTGRES_PASSWORD=CHANGE_ME/POSTGRES_PASSWORD=${pw}/" "$env_file"

    # Set tenant name if using generic template for ref
    if [ "$tenant" = "ref" ] && [ "$(basename "$example_file")" = ".env.example" ]; then
        sed -i "s/OMNIUS_TENANT=.*/OMNIUS_TENANT=ref/" "$env_file"
        sed -i "s/OMNIUS_POSTGRES_DB=.*/OMNIUS_POSTGRES_DB=omnius_ref/" "$env_file"
    fi

    ok "Generated $env_file"
    warn "Review $env_file and add API keys (ANTHROPIC_API_KEY, etc.)"
}

if [ "$TENANT" = "all" ]; then
    generate_tenant_env "ref"
    generate_tenant_env "reh"
else
    generate_tenant_env "$TENANT"
fi

# ── 3. Build & Start ─────────────────────────────────────────────────
info "Building and starting Omnius ($TENANT)..."

COMPOSE_ARGS=(-f docker-compose.omnius.yml --profile "$TENANT")

docker compose "${COMPOSE_ARGS[@]}" up -d --build 2>&1 || { fail "Docker build/start failed."; exit 2; }

ok "Containers started."

# ── 4. Wait for health checks ────────────────────────────────────────
info "Waiting for services..."

wait_for_service() {
    local name="$1"
    local check_cmd="$2"
    local max_attempts="${3:-30}"
    local attempt=0

    printf "  Waiting for %-16s " "$name..."
    while [ $attempt -lt $max_attempts ]; do
        if eval "$check_cmd" &>/dev/null 2>&1; then
            echo -e "${GREEN}OK${NC}"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
    echo -e "${RED}TIMEOUT${NC}"
    return 1
}

HEALTH_FAILED=false

wait_for_service "omnius-db" "docker compose -f docker-compose.omnius.yml exec -T db pg_isready -U omnius" 30 || HEALTH_FAILED=true

check_tenant_api() {
    local t="$1"
    local port
    case "$t" in
        reh) port=8001 ;;
        ref) port=8002 ;;
    esac
    wait_for_service "omnius-$t" "curl -sf http://localhost:${port}/health" 30 || HEALTH_FAILED=true
}

if [ "$TENANT" = "all" ]; then
    check_tenant_api "reh"
    check_tenant_api "ref"
else
    check_tenant_api "$TENANT"
fi

if [ "$HEALTH_FAILED" = true ]; then
    fail "Some services failed. Check logs:"
    echo "  docker compose -f docker-compose.omnius.yml logs --tail=50"
    exit 3
fi

ok "All services healthy."

# ── 5. Run migrations ────────────────────────────────────────────────
info "Running Omnius DB migrations..."

MIGRATION_DIR="$PROJECT_DIR/omnius/db/migrations"
if [ -d "$MIGRATION_DIR" ]; then
    run_migration_for_tenant() {
        local t="$1"
        local db="omnius_${t}"

        # Create database if not exists
        docker exec omnius-db psql -U omnius -tc "SELECT 1 FROM pg_database WHERE datname = '${db}'" | grep -q 1 || \
            docker exec omnius-db psql -U omnius -c "CREATE DATABASE ${db};" 2>/dev/null

        # Run migrations in order
        for migration in "$MIGRATION_DIR"/*.sql; do
            [ -f "$migration" ] || continue
            local fname
            fname=$(basename "$migration")
            info "  Applying $fname to $db..."
            if ! docker exec -i omnius-db psql -U omnius -d "$db" < "$migration" 2>&1 | grep -v "already exists" | grep -v "NOTICE"; then
                fail "Migration $fname failed on $db"
                HEALTH_FAILED=true
            fi
        done
        ok "Migrations applied to $db."
    }

    if [ "$TENANT" = "all" ]; then
        run_migration_for_tenant "ref"
        run_migration_for_tenant "reh"
    else
        run_migration_for_tenant "$TENANT"
    fi
else
    warn "No migrations directory found at $MIGRATION_DIR"
fi

if [ "$HEALTH_FAILED" = true ]; then
    fail "One or more migrations failed. Check output above."
    exit 3
fi

# ── 6. Print success ─────────────────────────────────────────────────
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Omnius is running! (tenant: $TENANT)${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

print_tenant_url() {
    local t="$1"
    local port
    case "$t" in
        reh) port=8001 ;;
        ref) port=8002 ;;
    esac
    echo -e "  Omnius ${t^^}:  ${BLUE}http://localhost:${port}${NC}"
}

if [ "$TENANT" = "all" ]; then
    print_tenant_url "reh"
    print_tenant_url "ref"
    OPEN_URL="http://localhost:8001"
else
    print_tenant_url "$TENANT"
    case "$TENANT" in
        reh) OPEN_URL="http://localhost:8001" ;;
        ref) OPEN_URL="http://localhost:8002" ;;
    esac
fi
echo ""

# ── 7. Open browser ──────────────────────────────────────────────────
if [ "$OPEN_BROWSER" = true ]; then
    if command -v xdg-open &>/dev/null; then
        xdg-open "$OPEN_URL" 2>/dev/null &
    elif command -v open &>/dev/null; then
        open "$OPEN_URL" 2>/dev/null &
    elif command -v start &>/dev/null; then
        start "$OPEN_URL" 2>/dev/null &
    else
        info "Open in your browser: $OPEN_URL"
    fi
fi

exit 0
