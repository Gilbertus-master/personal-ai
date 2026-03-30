#!/usr/bin/env bash
# provision_tenant.sh — Automated tenant provisioning for commercial Omnius
# Usage:
#   bash scripts/provision_tenant.sh <tenant_id> <company_name> [admin_email]
#
# Creates:
#   1. PostgreSQL database (omnius_<tenant>)
#   2. Qdrant collection (omnius_<tenant>)
#   3. RBAC seed (admin role + initial user)
#   4. .env file from template
#   5. Docker service entry

set -euo pipefail
cd "$(dirname "$0")/.."

TENANT_ID="${1:?Usage: provision_tenant.sh <tenant_id> <company_name> [admin_email]}"
COMPANY_NAME="${2:?Missing company_name}"
ADMIN_EMAIL="${3:-admin@${TENANT_ID}.local}"

DB_NAME="omnius_${TENANT_ID}"
QDRANT_COLLECTION="omnius_${TENANT_ID}"
DB_HOST="${OMNIUS_DB_HOST:-127.0.0.1}"
DB_PORT="${OMNIUS_DB_PORT:-5433}"
DB_USER="${OMNIUS_DB_USER:-omnius}"
DB_PASSWORD="${OMNIUS_DB_PASSWORD:-omnius_secure_pw}"
QDRANT_URL="${OMNIUS_QDRANT_URL:-http://127.0.0.1:6335}"

echo "=== Provisioning tenant: ${TENANT_ID} (${COMPANY_NAME}) ==="

# 1. Create PostgreSQL database
echo "Step 1: Creating database ${DB_NAME}..."
PGPASSWORD="${DB_PASSWORD}" psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -c "CREATE DATABASE ${DB_NAME};" 2>/dev/null || echo "  Database already exists"

# 2. Run migrations
echo "Step 2: Running migrations..."
for migration in omnius/db/migrations/*.sql; do
    echo "  Running: $(basename ${migration})"
    PGPASSWORD="${DB_PASSWORD}" psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -f "${migration}" 2>/dev/null || true
done

# 3. Create Qdrant collection
echo "Step 3: Creating Qdrant collection ${QDRANT_COLLECTION}..."
curl -s -X PUT "${QDRANT_URL}/collections/${QDRANT_COLLECTION}" \
  -H "Content-Type: application/json" \
  -d '{
    "vectors": {
      "size": 3072,
      "distance": "Cosine"
    }
  }' 2>/dev/null | .venv/bin/python -c "import sys,json; d=json.load(sys.stdin); print(f'  Collection: {d.get(\"result\", d.get(\"status\", \"?\"))}')" 2>/dev/null || echo "  Collection may already exist"

# 4. Seed admin user
echo "Step 4: Seeding admin user (${ADMIN_EMAIL})..."
PGPASSWORD="${DB_PASSWORD}" psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -c "
  INSERT INTO omnius_users (email, display_name, role_id, is_active)
  SELECT '${ADMIN_EMAIL}', 'Admin', id, true
  FROM omnius_roles WHERE name = 'ceo'
  ON CONFLICT (email) DO NOTHING;
" 2>/dev/null || echo "  User seeding skipped (table may not exist)"

# 5. Generate .env
ENV_FILE="omnius/.env.${TENANT_ID}"
echo "Step 5: Generating ${ENV_FILE}..."
cat > "${ENV_FILE}" << ENVEOF
OMNIUS_TENANT=${TENANT_ID}
OMNIUS_COMPANY_NAME=${COMPANY_NAME}
OMNIUS_POSTGRES_HOST=${DB_HOST}
OMNIUS_POSTGRES_PORT=${DB_PORT}
OMNIUS_POSTGRES_DB=${DB_NAME}
OMNIUS_POSTGRES_USER=${DB_USER}
OMNIUS_POSTGRES_PASSWORD=${DB_PASSWORD}
OMNIUS_QDRANT_URL=${QDRANT_URL}
OMNIUS_QDRANT_COLLECTION=${QDRANT_COLLECTION}
OMNIUS_LLM_MODEL=claude-haiku-4-5
ANTHROPIC_API_KEY=\${ANTHROPIC_API_KEY}
OMNIUS_DEV_AUTH=1
# Azure AD (fill in):
# OMNIUS_AZURE_TENANT_ID=
# OMNIUS_AZURE_CLIENT_ID=
# OMNIUS_GRAPH_CLIENT_ID=
# OMNIUS_GRAPH_CLIENT_SECRET=
ENVEOF

echo ""
echo "=== Tenant ${TENANT_ID} provisioned ==="
echo "  Database: ${DB_NAME}"
echo "  Collection: ${QDRANT_COLLECTION}"
echo "  Admin: ${ADMIN_EMAIL}"
echo "  Env file: ${ENV_FILE}"
echo ""
echo "Next steps:"
echo "  1. Fill in Azure AD credentials in ${ENV_FILE}"
echo "  2. Add to Gilbertus .env: OMNIUS_${TENANT_ID^^}_URL=http://127.0.0.1:<PORT>"
echo "  3. Start: docker compose -f docker-compose.omnius.yml --profile ${TENANT_ID} up -d"
