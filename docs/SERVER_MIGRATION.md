# Gilbertus Albans -- Server Migration Plan

**Created:** 2026-03-25
**Status:** PLANNING (Master Plan tasks I1, I2)
**Author:** Sebastian + Claude

---

## 1. Why Migrate

The current runtime environment is Sebastian's laptop running Windows 11 + WSL2 (Ubuntu).
This works for development but has real problems for a production personal AI system:

| Problem | Impact |
|---------|--------|
| WSL2 MTU bug causes SSL failures on large TLS records | Breaks API calls to Anthropic/OpenAI for payloads >1MB; requires `fix_wsl2_mtu.sh` workaround every boot |
| No static IP | Cannot receive webhooks (Plaud, MS Graph notifications) without ngrok tunnel |
| Laptop must stay on and open | Downtime whenever Sebastian closes the lid, reboots Windows, or travels |
| 14 cores / 31GB RAM shared with Windows | Not enough headroom for Omnius REH + REF alongside Gilbertus |
| No GPU | Whisper runs on CPU (slow); self-hosted LLM inference not viable |
| No encryption at rest | Sensitive personal data on an unencrypted consumer SSD |

A dedicated server eliminates all of these.

---

## 2. Requirements Analysis

### 2.1 Gilbertus Albans (primary workload)

| Component | Resource needs |
|-----------|---------------|
| **Postgres 16** | ~2-4GB RAM, ~20GB disk (current), growing ~2GB/month |
| **Qdrant** | ~4GB RAM per 100k vectors (text-embedding-3-large, 3072 dims). Current: ~50k vectors = ~2GB. Target 200k+ = 8GB+ |
| **Whisper (faster-whisper)** | CPU-only today. GPU would enable real-time transcription of Plaud recordings |
| **FastAPI** | Minimal (~256MB). Serves MCP, WhatsApp webhook, REST API |
| **OpenClaw / clawdbot** | Runs on Sebastian's machine, talks to server API. No server-side resource need |
| **Extraction pipelines** | Burst CPU/RAM when running entity/event extraction (Anthropic API calls + Postgres writes) |
| **Raw data storage** | ~60GB today (WhatsApp media, Plaud audio, email attachments, documents). Growing ~5GB/month |

### 2.2 Omnius REH + REF (future tenants)

Each Omnius instance needs its own isolated:
- Postgres database (separate DB or separate container)
- Qdrant collection (can share the Qdrant process, separate collections)
- FastAPI instance (separate port, auth-gated)

Estimated additional load per instance: ~4GB RAM, ~20GB disk.

### 2.3 Future: Self-hosted LLM

| Use case | Model size | GPU VRAM needed |
|----------|-----------|-----------------|
| Real-time Whisper (large-v3) | ~3GB | 6GB+ (RTX 4000 Ada: 20GB -- plenty) |
| Local embeddings (e5-large, BGE) | ~1-2GB | 4GB+ |
| Local LLM inference (Llama 3.1 70B Q4) | ~40GB | Not on a single RTX 4000 (20GB). Would need 2x or cloud fallback |
| Local LLM inference (Llama 3.1 8B Q4) | ~5GB | Fits in 20GB easily |

**Conclusion:** An RTX 4000 Ada (20GB) covers Whisper + embeddings + small LLM. For 70B+ models, continue using Anthropic/OpenAI APIs.

### 2.4 Total Resource Budget

| Resource | Gilbertus | Omnius x2 | GPU workloads | Buffer | **Total** |
|----------|-----------|-----------|---------------|--------|-----------|
| **RAM** | 12GB | 8GB | 4GB (shared with VRAM) | 8GB | **32-40GB min** |
| **CPU cores** | 4-6 | 2-4 | 2 (GPU offload) | 2 | **12-16 cores** |
| **Disk** | 100GB | 40GB | 20GB (models) | 100GB | **260GB min** |
| **GPU VRAM** | -- | -- | 20GB | -- | **20GB** |

---

## 3. Server Options

### 3.1 Hetzner AX52 (no GPU)

| Spec | Value |
|------|-------|
| CPU | AMD Ryzen 5 3600 (6c/12t) |
| RAM | 64GB DDR4 ECC |
| Storage | 2 x 512GB NVMe SSD |
| Network | 1 Gbit/s |
| Price | ~EUR 59/mo + EUR 39 setup |
| Location | Falkenstein / Helsinki |

**Verdict:** Enough RAM for Gilbertus + one Omnius instance. CPU is adequate. No GPU means Whisper stays on CPU. Storage is tight long-term (1TB usable in RAID1 = 512GB, or 1TB in JBOD). Good starter option if GPU is deferred.

### 3.2 Hetzner AX102 (no GPU) -- RECOMMENDED FOR NON-GPU

| Spec | Value |
|------|-------|
| CPU | AMD Ryzen 9 7950X3D (16c/32t) |
| RAM | 128GB DDR5 |
| Storage | 2 x 1TB NVMe SSD |
| Network | 1 Gbit/s |
| Price | ~EUR 109/mo + EUR 39 setup |
| Location | Falkenstein |

**Verdict:** Plenty of RAM for Gilbertus + both Omnius instances + large Qdrant indexes. Fast CPU handles extraction pipelines well. 2TB raw storage (or 1TB RAID1). No GPU.

### 3.3 Hetzner GEX44 (with GPU)

| Spec | Value |
|------|-------|
| CPU | Intel Core i5-13500 (14c/20t) |
| RAM | 64GB DDR4 |
| GPU | NVIDIA RTX 4000 SFF Ada (20GB GDDR6 ECC) |
| Storage | 2 x 1.92TB NVMe SSD |
| Network | 1 Gbit/s |
| Price | ~EUR 184/mo + EUR 79 setup |
| Location | Falkenstein |

**Verdict:** The GPU option. RTX 4000 Ada handles Whisper real-time, local embeddings, and small LLM inference. 64GB RAM is enough for Gilbertus + one Omnius. Storage is generous (3.84TB total). The i5-13500 is weaker than the Ryzen 9 for pure CPU tasks but the GPU offloads the heavy work. Best option if GPU workloads are a priority.

### 3.4 Alternatives

| Provider | Server | Specs | Price | Notes |
|----------|--------|-------|-------|-------|
| **OVH Rise-4** | Ryzen 5 7600, 64GB, 2x1TB NVMe | ~EUR 80/mo | No GPU option. Comparable to AX52 but pricier |
| **OVH Scale GPU** | Various with L4/A2000 | ~EUR 200-400/mo | More expensive than Hetzner for similar specs |
| **Scaleway Elastic Metal** | EM-B220E-NVME, 128GB | ~EUR 130/mo | Good specs but no GPU addon. Paris/Amsterdam DC |
| **Scaleway GPU** | L4 instances | ~EUR 1500/mo | Cloud GPU, way too expensive for always-on |

**Conclusion:** Hetzner dominates on price/performance for bare metal in Europe. OVH and Scaleway are viable fallbacks but offer no clear advantage.

---

## 4. Migration Checklist

### Phase 0: Pre-migration (on laptop)

- [ ] Run full backup: `scripts/backup_db.sh` (Postgres dump + Qdrant snapshots)
- [ ] Verify backup integrity: restore to a test container locally
- [ ] Export list of Docker volumes and their sizes
- [ ] Document all `.env` values (sanitized) needed on the server
- [ ] Tar the `data/raw/` directory for transfer
- [ ] Note current Qdrant collection schemas (dimensions, distance metric, payload indexes)
- [ ] Run `scripts/run_migrations.sh` to confirm all migrations are applied
- [ ] Tag the current Git commit as `pre-migration`

### Phase 1: Server Setup

- [ ] Order server (Hetzner Robot panel)
- [ ] Install Ubuntu 24.04 LTS via Hetzner installimage
- [ ] Set up LUKS full-disk encryption (task I6)
- [ ] Create non-root user `sebastian` with SSH key auth
- [ ] Disable password auth in sshd_config
- [ ] Configure UFW firewall:
  ```
  ufw default deny incoming
  ufw allow 22/tcp        # SSH
  ufw allow 80/tcp        # HTTP (Let's Encrypt challenge)
  ufw allow 443/tcp       # HTTPS
  ufw allow from <home-ip> to any port 5432   # Postgres (restricted)
  ufw allow from <home-ip> to any port 6333   # Qdrant (restricted)
  ufw enable
  ```
- [ ] Install Docker Engine (not Docker Desktop) + docker-compose plugin
- [ ] Install NVIDIA Container Toolkit (if GPU server)
- [ ] Set up fail2ban
- [ ] Configure automatic security updates (`unattended-upgrades`)
- [ ] Set hostname to `gilbertus` or `mentat-01`

### Phase 2: Application Deployment

- [ ] Clone `personal-ai` repo on server
- [ ] Copy `.env` file with production values
- [ ] Update `docker-compose.yml` for production:
  - Add restart policies (already `unless-stopped` -- good)
  - Add GPU passthrough for Whisper container (if GPU):
    ```yaml
    whisper:
      deploy:
        resources:
          reservations:
            devices:
              - driver: nvidia
                count: 1
                capabilities: [gpu]
    ```
  - Add Caddy or Traefik reverse proxy service for HTTPS
  - Add resource limits per container
  - Bind Postgres/Qdrant to 127.0.0.1 (not 0.0.0.0)
- [ ] `docker compose up -d`
- [ ] Run `scripts/run_migrations.sh`
- [ ] Verify all services healthy: `scripts/test_services.sh`

### Phase 3: Data Transfer

- [ ] Transfer Postgres dump to server:
  ```bash
  rsync -avz --progress backups/db/<latest>/postgres.dump sebastian@<server>:/tmp/
  ```
- [ ] Restore Postgres:
  ```bash
  docker exec -i gilbertus-postgres pg_restore \
    -U gilbertus -d gilbertus -c --if-exists /tmp/postgres.dump
  ```
- [ ] Transfer Qdrant snapshots:
  ```bash
  rsync -avz --progress backups/db/<latest>/qdrant_snapshots/ sebastian@<server>:/tmp/qdrant_snapshots/
  ```
- [ ] Restore Qdrant collections via API:
  ```bash
  curl -X POST "http://localhost:6333/collections/gilbertus_chunks/snapshots/upload" \
    -H "Content-Type: multipart/form-data" \
    -F "snapshot=@/tmp/qdrant_snapshots/gilbertus_chunks.snapshot"
  ```
- [ ] Transfer raw data:
  ```bash
  rsync -avz --progress data/raw/ sebastian@<server>:~/personal-ai/data/raw/
  ```
- [ ] Verify document counts match: compare `SELECT count(*) FROM documents` on both sides
- [ ] Verify Qdrant vector counts match: compare collection info on both sides
- [ ] Run a few test queries through the API to confirm retrieval quality

### Phase 4: Networking & SSL

- [ ] Point DNS A record to server's static IP:
  - `gilbertus.yourdomain.com` -> server IP
  - `api.gilbertus.yourdomain.com` -> server IP (optional)
- [ ] Set up Caddy as reverse proxy (auto-HTTPS with Let's Encrypt):
  ```
  # Caddyfile
  gilbertus.yourdomain.com {
      reverse_proxy localhost:8000
  }
  ```
  Or use Traefik with Docker labels.
- [ ] Verify HTTPS works end-to-end (no more MTU/SSL bugs)
- [ ] Update MS Graph redirect URI to new domain
- [ ] Update Plaud webhook URL to new domain
- [ ] Update WhatsApp bot webhook URL
- [ ] Test ngrok is no longer needed -- remove it

### Phase 5: Monitoring & Operations

- [ ] Set up Uptime Kuma (self-hosted) or Hetrixtools (free tier):
  - Monitor HTTPS endpoint
  - Monitor Postgres health
  - Monitor Qdrant health
  - Alert via WhatsApp/Telegram/email
- [ ] Set up automated backups:
  - Cron: `scripts/backup_db.sh` daily at 03:00
  - Cron: `scripts/prune_backups.sh` weekly (keep 7 daily, 4 weekly, 3 monthly)
  - Off-site backup to Hetzner Storage Box (BX11, EUR 3.81/mo for 1TB) or Backblaze B2
- [ ] Set up log rotation for Docker containers
- [ ] Set up `scripts/continuous_improvement.sh` as cron job
- [ ] Set up morning brief cron: `scripts/morning_brief.sh` at 06:30
- [ ] Monitor disk usage alerts (warn at 80%)
- [ ] Test full restore procedure on a separate Docker network

### Phase 6: Omnius Deployment (after Gilbertus is stable)

- [ ] Create separate `docker-compose.omnius-reh.yml` and `docker-compose.omnius-ref.yml`
- [ ] Each gets its own Postgres DB (can share the Postgres container, separate databases)
- [ ] Each gets its own Qdrant collections (share the Qdrant container)
- [ ] Each gets its own FastAPI instance on a separate port
- [ ] Set up auth/RBAC per Omnius instance (task O6)
- [ ] Import corporate data for REH and REF

---

## 5. Monthly Cost Estimate

### Option A: AX102 (no GPU) -- Conservative Start

| Item | Monthly cost |
|------|-------------|
| Hetzner AX102 (Ryzen 9, 128GB, 2x1TB) | EUR 109 |
| Hetzner Storage Box BX11 (1TB off-site backup) | EUR 4 |
| Domain (amortized) | EUR 1 |
| Anthropic API (extraction, answering) | EUR 30-80 |
| OpenAI API (embeddings) | EUR 5-15 |
| **Total** | **EUR 149-209/mo** |

### Option B: GEX44 (with GPU) -- Full Capability

| Item | Monthly cost |
|------|-------------|
| Hetzner GEX44 (i5-13500, 64GB, RTX 4000 Ada, 2x1.92TB) | EUR 184 |
| Hetzner Storage Box BX11 (1TB off-site backup) | EUR 4 |
| Domain (amortized) | EUR 1 |
| Anthropic API (extraction, answering) | EUR 30-80 |
| OpenAI API (embeddings -- partially replaced by local) | EUR 0-10 |
| **Total** | **EUR 219-279/mo** |

### Option C: AX52 (budget) -- Minimum Viable

| Item | Monthly cost |
|------|-------------|
| Hetzner AX52 (Ryzen 5, 64GB, 2x512GB) | EUR 59 |
| Hetzner Storage Box BX11 (1TB off-site backup) | EUR 4 |
| Domain (amortized) | EUR 1 |
| Anthropic/OpenAI API | EUR 35-95 |
| **Total** | **EUR 99-159/mo** |

---

## 6. Recommendation

### What to buy: Hetzner AX102 (EUR 109/mo)

**Reasoning:**

1. **RAM is the bottleneck, not GPU.** Qdrant with 200k+ vectors at 3072 dimensions needs 8-12GB RAM. With Gilbertus + two Omnius instances + Postgres, 64GB is tight. 128GB gives comfortable headroom.

2. **GPU can wait.** Whisper on CPU is slow but functional (transcription happens async, not real-time). Self-hosted LLM is a nice-to-have, not a blocker. The Ryzen 9 7950X3D is a significantly better CPU than the i5-13500 in the GEX44, which matters for extraction pipelines.

3. **Upgrade path is clear.** Start with AX102. If GPU becomes critical (real-time Whisper for meetings, local embeddings to cut OpenAI costs), either:
   - Add a GEX44 as a dedicated GPU worker node
   - Migrate to GEX44 when Hetzner offers higher-RAM GPU configs
   - Use Hetzner Cloud GPU instances on-demand for burst workloads

4. **Storage is adequate.** 2x1TB NVMe in RAID1 gives 1TB usable. With current data at ~80GB and growing ~5GB/month, this lasts 18+ months. JBOD (no RAID) gives 2TB if needed.

### When to buy

**Now.** The WSL2 SSL bug, lack of static IP, and laptop dependency are active blockers for:
- Reliable webhook reception (Plaud, MS Graph)
- Morning brief cron reliability
- Omnius deployment for Roch and Krystian
- General system stability

The migration itself takes 1-2 days of focused work. The server pays for itself in reliability from day one.

### Migration timeline

| Week | Action |
|------|--------|
| Week 1 | Order AX102. Set up OS, Docker, firewall, LUKS |
| Week 1-2 | Deploy Gilbertus. Transfer data. Verify |
| Week 2 | DNS, SSL, webhooks. Kill ngrok |
| Week 2-3 | Monitoring, automated backups, cron jobs |
| Week 3-4 | Deploy Omnius REH + REF |
| Month 2+ | Evaluate GPU needs based on usage patterns |

---

## References

- [Hetzner AX52 product page](https://www.hetzner.com/dedicated-rootserver/ax52/)
- [Hetzner AX102 product page](https://www.hetzner.com/dedicated-rootserver/ax102)
- [Hetzner AX server configurations and addons](https://docs.hetzner.com/robot/dedicated-server/server-lines/ax-server/)
- [Hetzner GEX44 GPU server](https://www.hetzner.com/dedicated-rootserver/gex44/)
- [Hetzner GPU server matrix](https://www.hetzner.com/dedicated-rootserver/matrix-gpu/)
- [Hetzner server addon pricing](https://docs.hetzner.com/robot/dedicated-server/dedicated-server-hardware/price-server-addons/)
- [OVH bare metal pricing](https://www.ovhcloud.com/en/bare-metal/prices/)
- [Scaleway Elastic Metal](https://www.scaleway.com/en/elastic-metal/)
- [Hetzner April 2026 price adjustment notice](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/)
