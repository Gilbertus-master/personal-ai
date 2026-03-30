#!/usr/bin/env bash
# migrate_to_hetzner.sh — Migration script for WSL2 → Hetzner
#
# Pre-requisites on Hetzner:
#   - Docker + Docker Compose installed
#   - SSH access configured
#   - This repo cloned to /opt/gilbertus
#
# Usage:
#   1. On WSL2:  bash scripts/migrate_to_hetzner.sh --dump
#   2. SCP:      scp backups/migration/* hetzner:/opt/gilbertus/backups/migration/
#   3. On Hetzner: bash scripts/migrate_to_hetzner.sh --restore
#   4. On Hetzner: bash scripts/migrate_to_hetzner.sh --start

set -euo pipefail
cd "$(dirname "$0")/.."

ACTION="${1:---help}"

case "$ACTION" in
  --dump)
    echo "=== Step 1: Creating migration dump ==="
    mkdir -p backups/migration

    # Postgres full dump
    echo "Dumping Postgres..."
    docker exec gilbertus-postgres pg_dump -U "${POSTGRES_USER:-gilbertus}" \
      -d "${POSTGRES_DB:-gilbertus}" -Fc -f /tmp/migration.dump
    docker cp gilbertus-postgres:/tmp/migration.dump backups/migration/postgres.dump
    echo "  Postgres: $(du -h backups/migration/postgres.dump | cut -f1)"

    # Qdrant snapshot
    echo "Snapshotting Qdrant..."
    curl -s -X POST "http://127.0.0.1:6333/collections/gilbertus_chunks/snapshots" > /dev/null
    SNAP=$(curl -s "http://127.0.0.1:6333/collections/gilbertus_chunks/snapshots" | .venv/bin/python -c "import sys,json; snaps=json.load(sys.stdin)['result']; print(snaps[-1]['name'])" 2>/dev/null)
    curl -s "http://127.0.0.1:6333/collections/gilbertus_chunks/snapshots/${SNAP}" -o backups/migration/qdrant_snapshot.tar
    echo "  Qdrant: $(du -h backups/migration/qdrant_snapshot.tar | cut -f1)"

    # .env template (without secrets)
    echo "Creating .env template..."
    grep -v "PASSWORD\|KEY\|TOKEN\|SECRET" .env > backups/migration/env.template 2>/dev/null || true
    echo "  .env template created (fill in secrets manually)"

    # Config files
    cp -r scripts backups/migration/scripts_backup 2>/dev/null || true

    echo ""
    echo "=== Migration dump ready ==="
    echo "Files in backups/migration/:"
    ls -lh backups/migration/
    echo ""
    echo "Next: SCP to Hetzner and run --restore"
    ;;

  --restore)
    echo "=== Step 2: Restoring on Hetzner ==="

    # Start infra containers
    echo "Starting Postgres + Qdrant..."
    docker compose -f docker-compose.prod.yml up -d postgres qdrant
    sleep 10

    # Restore Postgres
    echo "Restoring Postgres..."
    docker cp backups/migration/postgres.dump gilbertus-postgres:/tmp/migration.dump
    docker exec gilbertus-postgres pg_restore -U "${POSTGRES_USER:-gilbertus}" \
      -d "${POSTGRES_DB:-gilbertus}" -c --if-exists /tmp/migration.dump || true
    echo "  Postgres restored"

    # Restore Qdrant
    if [ -f backups/migration/qdrant_snapshot.tar ]; then
      echo "Restoring Qdrant snapshot..."
      curl -s -X POST "http://127.0.0.1:6333/collections/gilbertus_chunks/snapshots/upload" \
        -H "Content-Type: multipart/form-data" \
        -F "snapshot=@backups/migration/qdrant_snapshot.tar"
      echo "  Qdrant restored"
    fi

    echo ""
    echo "=== Restore complete ==="
    echo "Next: Configure .env with secrets, then run --start"
    ;;

  --start)
    echo "=== Step 3: Starting all services ==="
    docker compose -f docker-compose.prod.yml up -d
    sleep 5

    echo "Checking health..."
    curl -sf http://127.0.0.1:8000/health && echo " API: OK" || echo " API: FAILED"
    curl -sf http://127.0.0.1:6333/health && echo " Qdrant: OK" || echo " Qdrant: FAILED"
    curl -sf http://127.0.0.1:9090/health && echo " Whisper: OK" || echo " Whisper: FAILED"

    echo ""
    docker compose -f docker-compose.prod.yml ps
    ;;

  --help|*)
    echo "Usage: bash scripts/migrate_to_hetzner.sh [--dump|--restore|--start]"
    echo ""
    echo "  --dump     Create migration dump (run on WSL2)"
    echo "  --restore  Restore from dump (run on Hetzner)"
    echo "  --start    Start all services (run on Hetzner)"
    ;;
esac
