# WhatsApp Live Pipeline — Audit Report

**Date:** 2026-03-29
**Author:** Gilbertus (automated audit)

## 1. Architecture Overview

```
┌─────────────────┐     JSONL      ┌──────────────┐     PostgreSQL     ┌──────────────┐
│  listener.js    │ ──────────────→│  importer.py │ ──────────────────→│  documents   │
│  (Baileys/WA)   │  messages.jsonl│  (Python)    │                    │  chunks      │
│  systemd svc    │                │  cron (TBD)  │                    │              │
└─────────────────┘                └──────────────┘                    └──────────────┘
```

- **listener.js** — Baileys-based WhatsApp Web client, runs as `whatsapp-listener.service` (systemd user unit, `Restart=always`, `RestartSec=10`)
- **importer.py** — Python script that reads JSONL, groups messages by chat+day, creates documents/chunks. Designed for cron but **no cron entry exists**.
- **State tracking** — `importer_state.json` stores `last_offset` (byte offset into JSONL file)

## 2. Current Problems

### 2.1. CRITICAL: Bad MAC Errors — Session Corrupted
- **40,456 "Bad MAC" errors** in service.log
- The Signal protocol session is corrupted — listener connects to WA Web successfully but **cannot decrypt any messages**
- Messages.jsonl last modified: 2026-03-27 12:33 (>48h stale)
- **Fix required:** Re-pair the device (`node listener.js --pair`)

### 2.2. CRITICAL: No Importer Cron Entry
- `importer.py` was designed to run "as cron every 5 minutes" but **no crontab entry exists**
- Import only happens when manually triggered
- **Fix:** Add cron entry

### 2.3. HIGH: Recurring 500 Disconnects
- Listener disconnects every ~50 minutes with status 500 (server-side)
- Reconnect works (3s delay) but this is frequent
- Current reconnect: flat 3s for most cases, 5s for 515, 30s for 408
- **Missing:** Exponential backoff for repeated failures

### 2.4. HIGH: File Rotation Not Handled
- `importer.py` uses byte offset tracking (`f.seek(offset)`)
- If JSONL file is rotated/truncated and new file is smaller than `last_offset`, the seek goes past EOF → 0 messages imported silently
- This is exactly what happened: offset=1065365, file=1065365 bytes (file at EOF, no detection of rotation)
- **Fix:** Check `file_size < last_offset` → reset to 0

### 2.5. MEDIUM: No Deduplication
- If offset is reset (like we just did), ALL messages are re-imported
- `_read_all_messages_for_key()` deduplicates by message `id` within a single run
- But document-level: existing docs get chunks deleted and re-created (no true dedup)
- **Fix:** Track imported message IDs or use ON CONFLICT

### 2.6. MEDIUM: Large File Performance
- `_read_all_messages_for_key()` scans the ENTIRE JSONL file for each existing document group
- With N groups containing existing docs, this is O(N * file_size) reads
- Current file: 1MB / 2354 messages — not a problem yet
- At 50MB+ this will be very slow
- **Fix:** File rotation at 50MB threshold

### 2.7. LOW: No Health Check / Monitoring
- No way to check if listener is actually receiving messages (vs just connected but corrupted)
- `last_msg_at` not tracked
- No alerting on stale JSONL

### 2.8. LOW: No PID File
- Systemd manages the process, but external scripts can't easily check status
- PID file would complement health check endpoint

## 3. Listener.js Analysis

### What works well:
- Handles multiple message types (text, image, video, audio, sticker, document, contact, location)
- Skips reactions and protocol messages
- Caches group metadata
- QR code pairing with retry limit (3 attempts)
- Differentiates disconnect reasons (loggedOut vs reconnectable)

### What's missing:
- No exponential backoff on repeated reconnects
- No health check endpoint
- No file rotation
- No PID file
- No metric: `last_msg_at` timestamp
- `appendFileSync` is blocking — fine at current volume but will bottleneck at high throughput

## 4. Importer.py Analysis

### What works well:
- Clean chat+day grouping
- Proper document upsert (delete chunks → re-create)
- Handles both new and existing documents
- Dedup within a single run via message ID
- Self-chat filtering (Sebastian's own messages already captured by OpenClaw)

### What's missing:
- No file rotation detection (offset > file_size)
- No DB retry logic
- No import metrics/telemetry
- No message-level dedup across runs (only within-run)
- No cron entry

## 5. Systemd Service

```ini
# whatsapp-listener.service
Restart=always
RestartSec=10
```

- Adequate for crash recovery
- But does NOT detect "connected but corrupted" state
- A supervisor/health check that monitors `last_msg_at` would catch this

## 6. Recommendations (Implemented in Etap 2)

| Priority | Fix | Component |
|----------|-----|-----------|
| P0 | Re-pair device (Bad MAC) | Manual / listener.js |
| P0 | Add importer cron entry | crontab |
| P1 | File rotation detection in importer | importer.py |
| P1 | Exponential backoff reconnect | listener.js |
| P1 | Health check endpoint (:9393/health) | listener.js |
| P1 | JSONL file rotation at 50MB | listener.js |
| P2 | DB retry logic (3 attempts) | importer.py |
| P2 | Import metrics (last_import_at, msg_count) | importer.py |
| P2 | Message-level dedup | importer.py |
| P2 | Supervisor script (wa_supervisor.sh) | scripts/ |
| P3 | PID file | listener.js |

## 7. WA Historical Data

- 60+ chat export files in `data/raw/whatsapp/`
- Filenames contain person name + relationship description (rich metadata for contact bootstrapping)
- Format: `_chat [Name] - [description].txt`
- Already imported as `source_type=whatsapp` documents
