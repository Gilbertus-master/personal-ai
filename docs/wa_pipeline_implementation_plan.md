# WA Pipeline Implementation Plan — 2026-03-29

## 2A. Hotfix (< 1h, zrób NAJPIERW)

### H1. Reset offset w importer_state.json
- **Zmiana:** `last_offset: 0`
- **Uzasadnienie:** Offset na EOF, żadne nowe wiadomości nie będą przechwycone. Reset pozwoli reimportować wszystkie 2354 messages.
- **Efekt:** 74 istniejących dokumentów zostanie zaktualizowanych (chunks deleted + recreated), nowe dokumenty dla chatów dotąd pominiętych.
- **Test:** `python -m app.ingestion.whatsapp_live.importer` → output "X new messages" + "Imported: Y documents, Z chunks"

### H2. Dodać cron entry
- **Zmiana:** Dodać do crontab:
  ```
  */5 * * * * cd /home/sebastian/personal-ai && source .venv/bin/activate && python -m app.ingestion.whatsapp_live.importer >> logs/whatsapp_import.log 2>&1
  ```
- **Uzasadnienie:** Importer zaprojektowany na cron co 5 min, ale brak wpisu.
- **Efekt:** Automatyczny import nowych wiadomości co 5 min.
- **Test:** `crontab -l | grep whatsapp`

---

## 2B. Stabilność listenera (listener.js)

### B1. Exponential backoff na reconnect
- **Co zmienić:** W `connection.update` handler, zamienić flat delay na exponential:
  ```
  delay = min(BASE_DELAY * 2^attempt, MAX_DELAY)  // BASE=3s, MAX=60s
  ```
- **Logika:**
  - Dodać `reconnectAttempt` counter (global, resetowany na `connection === "open"`)
  - Status 408 (QR timeout): zachować 30s flat
  - Status 515 (server restart): zachować 5s flat
  - Inne: `Math.min(3000 * Math.pow(2, reconnectAttempt), 60000)` + jitter (±1s random)
- **Uzasadnienie:** Przy disconnects co 50 min, flat 3s to 20 reconnects/min na backoff. Exponential = łagodny recovery.

### B2. Health check endpoint (:9393/health)
- **Co dodać:** Prosty HTTP server na porcie 9393
- **Response:** `{"status": "connected"|"disconnected", "last_msg_at": "ISO8601", "uptime_s": N, "msgs_today": N}`
- **Tracking:** Inkrementować `msgCount` i ustawiać `lastMsgAt` w `messages.upsert` handler
- **Uzasadnienie:** Pozwala monitoringowi wykryć "connected but corrupted" state (connected ale lastMsgAt stale)

### B3. Phone number w JSONL (dla entity linking)
- **Co zmienić:** W `messages.upsert` handler, dodać pole `phoneJid` do record:
  - Dla `@s.whatsapp.net` JIDs: sam JID (zawiera phone)
  - Dla `@lid` JIDs: `null` (na razie; later: Baileys contact resolution)
  - Dla `@g.us` JIDs (grupy): `null` (participant JIDs mogą być phone-based)
- **Nowe pole w record:** `phoneJid: string | null`
- **Uzasadnienie:** LID nie zawiera phone number, ale wiele chatów nadal używa `@s.whatsapp.net` formatu. Zachowanie phone number gdy dostępny.

---

## 2C. Odporność importera (importer.py)

### C1. File rotation detection
- **Co zmienić:** W `read_new_messages()`, przed `f.seek(offset)`:
  ```python
  file_size = MESSAGES_FILE.stat().st_size
  if offset > file_size:
      logger.warning("JSONL file rotated: offset %d > file_size %d, resetting to 0", offset, file_size)
      offset = 0
  ```
- **Uzasadnienie:** Jeśli plik się skurczy (rotacja/truncate), seek za EOF = 0 messages silently.
- **Test:** Truncate plik do 100 bajtów, ustaw offset na 1000, uruchom importer → powinien zresetować offset i importować.

### C2. Message-level dedup via DB
- **Co zmienić:** Dodać kolumnę `wa_message_ids jsonb` do tabeli `documents` (migration).
- **W import_group():** Po buildowaniu dokumentu, zapisać listę message IDs w wa_message_ids. Przy update: porównać stare vs nowe ID — skip jeśli identyczne.
- **Alternatywna prostszy approach:** Zachować obecny upsert (delete+recreate chunks) ale dodać early exit: jeśli dokument istnieje i `len(full_text)` == stary `len(full_text)`, skip.
- **Uzasadnienie:** Unikamy niepotrzebnego delete+insert chunks gdy nie ma nowych wiadomości.

### C3. Batch DB operations
- **Co zmienić:** W `import_group()`, zamiast osobnego `insert_chunk()` per chunk (osobne połączenie z pool!), użyć jednego connection:
  ```python
  with get_pg_connection() as conn:
      with conn.cursor() as cur:
          for ci, chunk in enumerate(chunks):
              cur.execute("INSERT INTO chunks ...")
      conn.commit()
  ```
- **Uzasadnienie:** 10 chunks = 10 connections z pool → 1 connection. Mniej overhead, atomiczność.

### C4. Structured logging
- **Co zmienić:** Dodać `structlog` logger zamiast `print()`:
  ```python
  import structlog
  logger = structlog.get_logger("whatsapp_live.importer")
  ```
- **Uzasadnienie:** Spójność z resztą codebase. Lepsze logowanie do plików.

---

## 2D. Entity linking — schemat DB

Schema contacts/document_contacts/contact_link_log **już istnieje** (migration 015). Nie trzeba tworzyć nowych tabel.

### Dodatkowa kolumna do documents (migration 016):
```sql
-- Track WA message IDs for dedup
ALTER TABLE documents ADD COLUMN IF NOT EXISTS wa_message_ids jsonb;
CREATE INDEX IF NOT EXISTS idx_documents_wa_message_ids ON documents USING gin(wa_message_ids) WHERE wa_message_ids IS NOT NULL;
```

### Istniejące tabele (z migration 015):

```sql
-- contacts: cross-source person identity
CREATE TABLE contacts (
  id SERIAL PRIMARY KEY,
  canonical_name TEXT NOT NULL,        -- "Zofia Godula"
  whatsapp_jid TEXT,                   -- "214198726455434@lid"
  whatsapp_phone TEXT,                 -- "+48731066373"
  whatsapp_push_name TEXT,             -- "🌸"
  email_address TEXT,                  -- z Graph API
  teams_upn TEXT,                      -- z Teams
  teams_display_name TEXT,
  notes TEXT,                          -- np. "partnerka od 2023"
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- document_contacts: M:N link
CREATE TABLE document_contacts (
  document_id BIGINT REFERENCES documents(id),
  contact_id INTEGER REFERENCES contacts(id),
  role TEXT,                           -- 'sender', 'recipient', 'participant'
  PRIMARY KEY (document_id, contact_id)
);

-- contact_link_log: audit trail
CREATE TABLE contact_link_log (
  id SERIAL PRIMARY KEY,
  contact_id INTEGER REFERENCES contacts(id),
  source_type TEXT NOT NULL,           -- 'whatsapp_live', 'whatsapp', 'email'
  matched_field TEXT,                  -- 'phone', 'name_fuzzy', 'jid'
  matched_value TEXT,
  confidence REAL,                     -- 0.0-1.0
  created_at TIMESTAMPTZ DEFAULT now()
);
```

### Indeksy do dodania (migration 016):
```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_contacts_whatsapp_jid ON contacts(whatsapp_jid) WHERE whatsapp_jid IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_contacts_whatsapp_phone ON contacts(whatsapp_phone) WHERE whatsapp_phone IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_contacts_canonical_name ON contacts(canonical_name);
```

---

## 2E. Contact resolver — API modułu

### Moduł: `app/ingestion/whatsapp_live/contact_resolver.py`

**Publiczne funkcje:**

```python
def bootstrap_contacts_from_exports() -> int:
    """Parse 60+ historical WA exports z source_name → utwórz contacts.

    source_name format: '_chat Zofia Godula - partnerka od sierpnia 2023'
    Parsuje: canonical_name = 'Zofia Godula', notes = 'partnerka od sierpnia 2023'

    Returns: number of contacts created.
    """

def resolve_contact(
    jid: str | None,
    phone: str | None,
    push_name: str | None,
) -> int | None:
    """Resolve a WA participant to a contact_id.

    Algorithm:
    1. If phone → normalize (+48xxx format) → SELECT by whatsapp_phone (confidence=1.0)
    2. If jid → SELECT by whatsapp_jid (confidence=1.0)
    3. If push_name → fuzzy match vs canonical_name (Levenshtein, threshold=0.8) (confidence=0.7)
    4. If no match → create new contact (canonical_name=push_name or phone or jid)

    Returns: contact_id
    Logs: contact_link_log entry with matched_field + confidence
    """

def link_document_contacts(
    document_id: int,
    messages: list[dict],
) -> int:
    """Link document to contacts based on message participants.

    For each unique sender in messages:
      - resolve_contact(jid, phone, push_name)
      - INSERT INTO document_contacts (document_id, contact_id, 'participant')
        ON CONFLICT DO NOTHING

    Returns: number of contacts linked
    """

def normalize_phone(raw: str) -> str:
    """Normalize phone: remove +, spaces, dashes. Add +48 for 9-digit Polish numbers.

    '48505441635' → '+48505441635'
    '505441635' → '+48505441635'
    '+48 505 441 635' → '+48505441635'
    """
```

### Algorytm matching (szczegóły):

1. **Phone normalization:** Strip wszystko poza cyframi. Jeśli 9 cyfr → prefix +48 (Polska). Jeśli starts with 48 i 11 cyfr → +48xxx.
2. **JID → phone:** `@s.whatsapp.net` → extract number. `@lid` → null (nie da się).
3. **Fuzzy name:** `python-Levenshtein` lub `difflib.SequenceMatcher`. Threshold ratio >= 0.8.
4. **Auto-create:** Jeśli brak match → nowy contact z minimal data. `canonical_name` = push_name or phone or jid.

### Integracja z pipeline:

W `import_group()`, po insert/update dokumentu:
```python
link_document_contacts(doc_id, msgs)
```

---

## 2F. Non-regression strategy

### Przed każdym etapem:
1. `SELECT count(*) FROM documents WHERE raw_path LIKE 'whatsapp_live://%%'` — nie powinno spaść
2. `SELECT count(*) FROM chunks c JOIN documents d ON c.document_id=d.id JOIN sources s ON d.source_id=s.id WHERE s.source_type='whatsapp_live'` — nie powinno spaść (po etapie 1 wzrośnie)
3. `python scripts/non_regression_gate.py` — musi pass

### Rollback:
- Każdy etap = osobny git commit
- Rollback = `git revert <commit>`
- State file backup przed zmianą: `cp importer_state.json importer_state.json.bak`

---

## 2G. Kolejność wdrożenia

### Etap 0: Hotfix (H1 + H2)
- Reset offset → test import → dodać cron
- **Zależności:** Brak
- **Test:** Import > 0 documents, crontab ma wpis

### Etap 1: Odporność importera (C1 + C3 + C4)
- File rotation detection + batch DB + structured logging
- **Zależności:** Etap 0 (import działa)
- **Test:** Truncate file test, import jeszcze działa, logi structured

### Etap 2: Listener stabilność (B1 + B2)
- Exponential backoff + health endpoint
- **Zależności:** Brak (ale Etap 0 powinien być gotowy)
- **Test:** `curl localhost:9393/health` → JSON response

### Etap 3: Listener phone field (B3)
- Dodanie phoneJid do JSONL output
- **Zależności:** Etap 2
- **Test:** Nowe messages w JSONL mają pole phoneJid

### Etap 4: Contact bootstrap + resolver (pełny 2E)
- Bootstrap contacts z exportów + resolver + link_document_contacts w importerze
- Migration 016 (indeksy + wa_message_ids)
- **Zależności:** Etap 1 (importer stabilny) + Etap 3 (phone field)
- **Test:** `SELECT count(*) FROM contacts` > 0, `SELECT count(*) FROM document_contacts` > 0

### Etap 5: Dedup (C2)
- wa_message_ids tracking + early exit on no-change
- **Zależności:** Etap 4 (migration 016)
- **Test:** Uruchom import 2x — drugi run powinien skip most docs
