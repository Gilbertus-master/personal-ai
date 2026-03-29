# WA Pipeline Research — 2026-03-29

## Aktualne problemy

1. **Bad MAC / sesja zdekryptowana** — Listener łączy się z WA Web ale nie może deszyfrować wiadomości (40k+ "Bad MAC" errors w logach). Messages.jsonl stale od 2026-03-27. — **Severity: CRITICAL**
2. **Brak wpisu cron dla importera** — `importer.py` zaprojektowany na cron co 5 min, ale brak wpisu w crontab. Import działa tylko ręcznie. — **Severity: CRITICAL**
3. **Offset na EOF** — `last_offset=1065365`, plik=1065365 bajtów. Nie bug sam w sobie (offset = file_size), ale brak detekcji rotacji pliku. Jeśli plik się skurczy (rotacja/truncate), seek pójdzie za EOF → 0 wiadomości. — **Severity: HIGH**
4. **Brak exponential backoff** — Listener disconnectuje co ~50 min (status 500). Reconnect z flat 3s delay. Przy częstych failach to hammering. — **Severity: HIGH**
5. **LID format zamiast numerów tel.** — Baileys 6.7.16 używa LID (Linked Identity): `214198726455434@lid` zamiast `48731066373@s.whatsapp.net`. chatName to LID, nie numer. — **Severity: HIGH** (utrudnia entity linking)
6. **Brak dedup cross-run** — Reset offsetu → ALL messages reimported. Document-level upsert (delete chunks + recreate) jest idempotentny ale niewydajny. — **Severity: MEDIUM**
7. **O(N*file_size) dla update** — `_read_all_messages_for_key()` skanuje cały plik JSONL per group. Przy 50MB+ będzie wolno. — **Severity: MEDIUM** (1MB teraz)
8. **contacts tabela pusta** — Schema contacts/document_contacts/contact_link_log istnieje (migration 015) ale 0 wierszy. Brak resolwera. — **Severity: MEDIUM**
9. **Brak health check** — Nie da się sprawdzić czy listener faktycznie odbiera wiadomości (vs connected but corrupted). — **Severity: LOW**

## Obecna architektura — mocne strony

1. **Czysta separacja listener/importer** — JS listener pisze JSONL, Python importer czyta. Loose coupling, łatwe debugowanie.
2. **Obsługa wielu typów wiadomości** — text, image, video, audio, sticker, document, contact, location, live location. Reakcje i protocol messages poprawnie pomijane.
3. **Chat+day grouping** — Naturalne grupowanie wiadomości w dokumenty. Upsert istniejących dokumentów (nowe wiadomości tego samego dnia aktualizują dokument).
4. **Self-chat filtering** — Wiadomości z self-chat pomijane (już przechwycone przez OpenClaw).
5. **Group metadata caching** — Nazwy grup cache'owane, minimalizuje API calls.
6. **Reconnect na disconnect** — Listener automatycznie reconnectuje (poza loggedOut). Systemd `Restart=always` jako backup.
7. **Bogate metadane** — pushName, fromMe, isGroup, mediaType, type (notify/append) zachowane w JSONL.

## Obecna architektura — słabe strony

1. **Brak file rotation** — messages.jsonl rośnie w nieskończoność. Brak mechanizmu rotacji/archiwizacji.
2. **appendFileSync blokujący** — OK przy 2354 msg, bottleneck przy high throughput.
3. **Każdy insert = osobne connection z pool** — `insert_chunk()` i `insert_document()` każdy bierze connection. Przy 10 chunks = 10 connections. Powinno być batch w jednym conn.
4. **Brak retry na DB errors** — Jeden failed insert = lost data.
5. **LID ↔ phone mapping brakuje** — Listener dostaje `peer_recipient_pn` w logach (np. `48731066373@s.whatsapp.net`) ale NIE zapisuje go do JSONL. To phone number jest dostępny w retry receipt metadata.
6. **imported_docs w state nieużywany** — State ma pole `imported_docs: {}` ale nigdy nie jest wypełniane.
7. **60+ historycznych exportów WA** — Bogata baza kontaktów w `source_name` (imię + opis relacji), ale niepodłączona do contacts.

## Dane ilościowe

| Metryka | Wartość |
|---------|---------|
| Messages w JSONL | 2,354 |
| Unikalne chaty | 46 |
| WA live documents w DB | 74 |
| WA historical exports | 60+ (z pełnymi opisami relacji) |
| contacts w DB | 0 |
| Baileys version | ^6.7.16 |
| JSONL file size | 1.04 MB |
| Największy chat | 214198726455434@lid (1204 msgs) |

## Rekomendacje dla entity linking

### Opcja A: Phone-based resolver (WA JID → phone → contact)
- **Opis:** Wyciągać numer telefonu z JID (`48731066373@s.whatsapp.net` format) lub z LID-to-phone mapping. Match contacts po `whatsapp_phone`.
- **Plusy:** Deterministyczny match, jeden numer = jedna osoba. 60+ historycznych exportów mają imiona w source_name.
- **Minusy:** LID format (`214198726455434@lid`) NIE zawiera numeru telefonu. Baileys 6+ domyślnie używa LID. Wymaga albo: (a) patchowania listenera żeby zapisywał phone z `peer_recipient_pn`, (b) użycia Baileys API `sock.onWhatsApp()` do resolwowania LID→phone, (c) manualnego mappingu.
- **Złożoność:** MEDIUM — wymaga zmiany w listener.js + resolver logic

### Opcja B: Push-name fuzzy matching
- **Opis:** Match po `senderName` (push name z WA) do kontaktów z historycznych exportów.
- **Plusy:** Dostępny natychmiast w JSONL. Nie wymaga zmian w listenerze.
- **Minusy:** Push name może się zmienić, nie jest unikalny (np. "🌸"), może być null. Fuzzy matching jest podatny na fałszywe pozytywne.
- **Złożoność:** LOW ale LOW accuracy

### Opcja C: Hybrid — phone + push name + historical exports bootstrap
- **Opis:**
  1. Bootstrap contacts z 60+ historycznych exportów WA (source_name zawiera pełne imię + opis relacji)
  2. Patch listener.js żeby zapisywał phone number obok LID
  3. Resolver: najpierw match po phone (deterministic), potem po push name (fuzzy, z ręczną konfirmacją)
  4. contact_link_log loguje każdy match z confidence score
- **Plusy:** Łączy accuracy phone-based z coverage push-name. Bootstrap z istniejących danych. Audytowalny.
- **Minusy:** Wymaga zmiany listener + resolver + bootstrap script. Więcej kodu.
- **Złożoność:** MEDIUM-HIGH

### Opcja D: Minimal — JID-as-identifier + manual naming
- **Opis:** Tworzyć contact per unique JID. canonical_name ustawiony ręcznie lub z push_name. Bez phone resolution.
- **Plusy:** Najprostsze. Działa natychmiast.
- **Minusy:** Brak cross-source linking (WA ↔ email ↔ Teams). LID to opaque identifier.
- **Złożoność:** LOW

## Rekomendacja końcowa

**Opcja C (Hybrid)** w dwóch fazach:

**Faza Immediate (hotfix + stabilność):**
1. Reset offset + test import
2. Dodać cron entry
3. File rotation detection w imporcie
4. Exponential backoff w listenerze

**Faza Entity Linking:**
1. Bootstrap contacts z historycznych WA exportów (parse source_name → canonical_name + whatsapp_phone)
2. Patch listener.js — dodać `phoneNumber` field do JSONL (z `peer_recipient_pn` lub Baileys contact lookup)
3. Contact resolver w importerze — match po phone, fallback na push_name fuzzy
4. Link documents ↔ contacts via `document_contacts`

**Uzasadnienie:** Schema contacts/document_contacts już istnieje. 60+ exportów to gotowy bootstrap. Phone-based matching jest deterministyczny. Push-name fuzzy jako fallback pokrywa LID-only chaty. contact_link_log daje auditability.
