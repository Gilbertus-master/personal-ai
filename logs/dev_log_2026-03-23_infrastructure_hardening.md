# Development Log: Infrastructure Hardening
**Date:** 2026-03-23
**Session:** DB recovery + architecture fix
**Phase:** 10 (security, backup, porządkowanie)

## Root Cause Analysis

### Symptom
Postgres database was empty (0 tables) despite container running "healthy" for 4 hours.

### Diagnosis
1. Docker Compose used **bind-mount** (`./data/processed/postgres:/var/lib/postgresql/data`)
2. WSL2 restarted (likely Windows update/hibernation) around 05:00 UTC
3. Docker Desktop restarted and started containers with `restart: unless-stopped`
4. Postgres container started **before WSL2 filesystem was fully mounted** (race condition)
5. Postgres saw empty data directory → ran `initdb` → fresh empty database
6. Original data was effectively orphaned/overwritten

### Impact
- Postgres: all tables, 29k documents, 119k chunks, 3k entities, 6.7k events — LOST
- Qdrant: all collections/embeddings — LOST (same bind-mount issue)
- Backups: last good backup at 03:00 UTC (before reset) — INTACT

## Changes Made

### 1. Docker Named Volumes (replaces bind-mount)
**File:** `docker-compose.yml`

Before:
```yaml
volumes:
  - ./data/processed/postgres:/var/lib/postgresql/data
  - ./data/processed/qdrant:/qdrant/storage
```

After:
```yaml
volumes:
  - gilbertus_pgdata:/var/lib/postgresql/data
  - gilbertus_qdrant:/qdrant/storage

volumes:
  gilbertus_pgdata:
    name: gilbertus_pgdata
  gilbertus_qdrant:
    name: gilbertus_qdrant
```

**Why named volumes are safer:**
- Managed by Docker Engine, stored in `/var/lib/docker/volumes/`
- Survive WSL2 restarts — Docker Engine initializes them atomically
- No race condition with filesystem mounting
- `docker volume` commands for lifecycle management

### 2. Auto-Restore Guard
**File:** `scripts/pg_auto_restore.sh` + `@reboot` cron entry

Flow:
1. Wait for Postgres to accept connections (max 60s)
2. Check table count in public schema
3. If > 0 tables → exit OK
4. If 0 tables → find latest backup with dump > 1MB → auto pg_restore → verify

Trigger: `@reboot sleep 30 && cd /home/sebastian/personal-ai && bash scripts/pg_auto_restore.sh`

### 3. Backup Validation
**File:** `scripts/backup_db.sh` (rewritten)

New features:
- **Pre-flight check:** if DB has 0 tables, skip backup (don't overwrite good backups)
- **Dump size validation:** reject dumps < 1MB as empty/corrupt
- **Rich manifest:** includes postgres_dump_bytes, postgres_tables, postgres_documents, qdrant_snapshot_api
- **Qdrant snapshot via API:** uses `/collections/{name}/snapshots` endpoint instead of tarring storage dir

### 4. Qdrant Backup Fix
**Before:** `tar` of `data/processed/qdrant` directory → 392 bytes (empty)
**After:** Qdrant snapshot API per collection → proper binary snapshots

### 5. Restore Script Updated
**File:** `scripts/restore_db.sh`
- Dump size validation before restore
- Qdrant restore via snapshot upload API
- Post-restore verification

### 6. Re-index Script
**File:** `scripts/reindex_qdrant.sh`
- Resets `embedding_status` to 'pending'
- Runs `index_chunks.py` to re-embed and upsert to Qdrant
- Resumable (saves progress per batch)

## Current State
- Postgres: RESTORED (14 tables, 29810 docs, 119547 chunks) on named volume
- Qdrant: EMPTY — needs re-indexing via `scripts/reindex_qdrant.sh`
- Backup system: hardened with validation
- Auto-restore: active via @reboot cron

## Next Step
Run `bash scripts/reindex_qdrant.sh` to rebuild Qdrant index (~119k chunks, requires OpenAI API calls).
