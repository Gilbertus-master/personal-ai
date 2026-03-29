# WhatsApp Pipeline Changelog

## 2026-03-29 — Major Pipeline Overhaul

### Etap 0: Hotfix — Importer Offset Reset
- Reset `last_offset` from 1065365 to 0 in `importer_state.json`
- Re-imported 2354 messages -> 74 documents, 224 chunks (Mar 24-27)
- Root cause: offset at EOF, no new messages written for 48h+ due to Bad MAC errors

### Etap 1: Audit
- Full audit report: `docs/whatsapp_live_audit.md`
- Discovered: 40K Bad MAC errors (corrupted Signal session), no importer cron, no file rotation handling
- Listener running via systemd (`whatsapp-listener.service`) but can't decrypt messages

### Etap 2: Robust Live WA Pipeline

#### 2A. Listener Stability (`listener.js`)
- Added exponential backoff on reconnect (3s -> 6s -> 12s -> ... max 300s with jitter)
- Added health check endpoint: `GET http://127.0.0.1:9393/health`
- Added JSONL file rotation at 50MB (rename to `.1`)
- Added PID file: `~/.gilbertus/whatsapp_listener/listener.pid`
- Added message metrics: `lastMsgAt`, `msgCountSinceStart`

#### 2B. Importer Robustness (`importer.py`)
- Added file rotation detection: if `file_size < last_offset` -> auto-reset to 0
- Added import metrics in state file: `last_import_at`, `messages_this_run`, etc.
- Migrated logging to structlog

#### 2C. Supervisor + Cron
- Created `scripts/wa_supervisor.sh` — checks PID, health endpoint, staleness
- Added cron entries:
  - `*/5 * * * *` — importer (whatsapp_live.importer)
  - `*/5 * * * *` — supervisor (wa_supervisor.sh)

### Etap 3: Cross-Source Entity Linking

#### 3A. Database
- Migration `015_contacts.sql`: `contacts`, `document_contacts`, `contact_link_log` tables
- 82 contacts bootstrapped

#### 3B. Contact Resolver (`app/analysis/contact_resolver.py`)
- `resolve_wa_jid()` — JID -> phone -> name fuzzy match -> create contact
- `link_person_across_sources()` — cross-match email, Teams, WA historical
- `enrich_document_contacts()` — link documents to contacts
- `bootstrap_contacts_from_wa_export()` — parse WA history filenames

#### 3C. Backfill (`scripts/backfill_contacts.py`)
- 64 contacts from WA historical exports
- 18 additional from WA live messages
- 26 cross-source links (email + Teams)
- 163 document-contact links (92 WA live + 49 WA historical)

### Etap 4: Non-Regression
- `non_regression_gate.py check` -> OK (15 metrics)
- API `/health` -> OK
- Importer runs clean with no new messages

### Known Issues
- Listener needs re-pair (`node listener.js --pair`) — Bad MAC errors
- Some duplicate contacts from WA export filenames (e.g., "Dariusz Blizniak" x2)
- Fuzzy matching on single first names (e.g., "Kasia", "Piotr") may cause false positives
