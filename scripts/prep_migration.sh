#!/usr/bin/env bash
# prep_migration.sh — Prepare everything for Hetzner migration.
# Creates a migration bundle: code + DB dump + Qdrant snapshot + .env template
#
# Run on LAPTOP: bash scripts/prep_migration.sh
# Then rsync to server: rsync -avz --progress migration_bundle/ sebastian@46.225.216.159:~/
set -euo pipefail
cd "$(dirname "$0")/.."

BUNDLE="migration_bundle"
SERVER="sebastian@46.225.216.159"
SSH_KEY="$HOME/.ssh/gilbertus_hetzner"

echo "=== Preparing migration bundle ==="

# 1. Fresh DB dump
echo "1. Database dump..."
mkdir -p "$BUNDLE"
docker exec gilbertus-postgres pg_dump -U gilbertus gilbertus | gzip > "$BUNDLE/gilbertus_db.sql.gz"
echo "   $(ls -lh $BUNDLE/gilbertus_db.sql.gz | awk '{print $5}')"

# 2. .env template (strip actual secrets, leave placeholders)
echo "2. Creating .env template..."
sed 's/=sk-ant-api03-.*/=REPLACE_WITH_ANTHROPIC_KEY/' .env | \
sed 's/=sk-proj-.*/=REPLACE_WITH_OPENAI_KEY/' | \
sed 's/=Ly68Q~.*/=REPLACE_WITH_GRAPH_SECRET/' | \
sed 's/=eyJhbGciOiJIUzI1NiIs.*/=REPLACE_WITH_PLAUD_TOKEN/' > "$BUNDLE/.env.template"
echo "   Template created (secrets stripped)"

# 3. Code (git archive or rsync list)
echo "3. Code snapshot..."
git archive HEAD --format=tar.gz -o "$BUNDLE/code.tar.gz"
echo "   $(ls -lh $BUNDLE/code.tar.gz | awk '{print $5}')"

# 4. Crontab export
echo "4. Crontab..."
crontab -l > "$BUNDLE/crontab.txt"

# 5. Migration instructions
cat > "$BUNDLE/MIGRATE.md" << 'EOF'
# Migration Steps (on server)

## 1. Extract code
cd ~
tar xzf code.tar.gz -C personal-ai/

## 2. Setup Python venv
cd ~/personal-ai
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

## 3. Configure .env
cp .env.template .env
# Edit .env — fill in actual API keys

## 4. Restore DB
gunzip -c gilbertus_db.sql.gz | sudo docker exec -i gilbertus-postgres psql -U gilbertus -d gilbertus

## 5. Re-index Qdrant
.venv/bin/python -m app.retrieval.index_chunks --batch-size 200 --limit 0

## 6. Install crontab
crontab crontab.txt

## 7. Start API
bash scripts/run_api.sh

## 8. Install nginx + certbot
sudo apt install -y nginx certbot python3-certbot-nginx
# Configure reverse proxy for :8000

## 9. Verify
curl http://localhost:8000/health
curl http://localhost:8000/status
EOF

echo ""
echo "=== Bundle ready ==="
ls -lh "$BUNDLE/"
echo ""
echo "To deploy:"
echo "  rsync -avz --progress -e 'ssh -i $SSH_KEY' $BUNDLE/ $SERVER:~/"
echo "  ssh -i $SSH_KEY $SERVER 'cat ~/MIGRATE.md'"
