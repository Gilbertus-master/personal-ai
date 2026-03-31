# Gilbertus Quality Roadmap — Harmonogram Wdrożeń
*Wygenerowany: 2026-03-31*

## Graf zależności

```
[A0] Anthropic credit (Sebastian, manual)
      └──► [T9]  Backfill email extraction
      └──► [T16] Entity linking improvement

[T1] ENABLE_TOOL_ROUTING (.env)          ← NIEZALEŻNE
[T2] Log rotation                        ← NIEZALEŻNE
[T4] Qdrant drift fix                    ← NIEZALEŻNE
[T5] Anthropic/OpenAI credit alert       ← NIEZALEŻNE
[T6] Per-stage timing → PG              ← NIEZALEŻNE
[T11] Data coverage dashboard            ← NIEZALEŻNE
[T12] Feedback loop (frontend+backend)   ← NIEZALEŻNE
[T13] Shared answer cache (PG)           ← NIEZALEŻNE (tabela istnieje)

[T3]  PgBouncer setup
      └──► [T7]  Interpretation cache → PG shared
      └──► [T8]  Hybrid search BM25 (GIN index)
                  └──► [T10] Top-k + reranking
                              └──► [T14] Progressive context

[T6] Per-stage timing
      └──► [T15] Retrieval quality alerts

[T12] Feedback loop
      └──► [T17] Weekly quality review automation

[T8] + [T10]
      └──► [T18] Chunking quality review
```

---

## Harmonogram tygodniowy

### DZIEŃ 0 — Teraz (31.03.2026)

| # | Zadanie | Kto | Czas | Blokuje |
|---|---------|-----|------|---------|
| A0 | Doładuj Anthropic credit | **SEBASTIAN** | 5 min | T9, T16 |
| T1 | ENABLE_TOOL_ROUTING | Gilbertus | 5 min | — |
| T2 | Log rotation (logrotate) | Gilbertus | 30 min | — |

**T1 i T2 równolegle.**

---

### DZIEŃ 1 — 01.04.2026

| # | Zadanie | Kto | Czas | Blokuje |
|---|---------|-----|------|---------|
| T3 | PgBouncer setup | Gilbertus | 2h | T7, T8 |
| T4 | Qdrant drift fix | Gilbertus | 1h | — |
| T5 | Credit alert (Anthropic/OpenAI) | Gilbertus | 1h | — |
| T6 | Per-stage timing → PG aggregation | Gilbertus | 2h | T15 |

**T3, T4, T5, T6 równolegle.**

---

### DZIEŃ 2 — 02.04.2026

| # | Zadanie | Kto | Czas | Blokuje |
|---|---------|-----|------|---------|
| T7 | Interpretation cache → PG shared | Gilbertus | 2h | — |
| T8 | Hybrid search BM25 (tsvector + GIN) | Gilbertus | 3h | T10, T18 |
| T9 | Uruchom backfill email (po credit A0) | Gilbertus | 1h (+auto) | — |
| T11 | Data coverage dashboard | Gilbertus | 2h | — |

**T7, T8, T9, T11 równolegle. T7 i T8 wymagają T3.**

---

### DZIEŃ 3 — 03.04.2026

| # | Zadanie | Kto | Czas | Blokuje |
|---|---------|-----|------|---------|
| T10 | Top-k increase + BM25 reranking | Gilbertus | 2h | T14 |
| T12 | Feedback loop (frontend + backend) | Gilbertus | 3h | T17 |
| T13 | Shared answer cache → PG (tabela istnieje) | Gilbertus | 1h | — |

**T10 wymaga T8. T12 i T13 równolegle z T10.**

---

### DZIEŃ 4 — 04.04.2026

| # | Zadanie | Kto | Czas | Blokuje |
|---|---------|-----|------|---------|
| T14 | Progressive context dla analysis queries | Gilbertus | 2h | — |
| T15 | Retrieval quality alerts | Gilbertus | 1h | — |
| T16 | Entity linking improvement | Gilbertus | 2h | — |

**T14 wymaga T10. T15 wymaga T6. T16 wymaga A0. Wszystkie równolegle.**

---

### TYDZIEŃ 2 — 07-11.04.2026

| # | Zadanie | Kto | Czas | Blokuje |
|---|---------|-----|------|---------|
| T17 | Weekly quality review automation | Gilbertus | 3h | — |
| T18 | Chunking quality review & optimization | Gilbertus | 4h | — |
| T19 | PG tuning + connection monitoring | Gilbertus | 1h | — |

**Wszystkie równolegle. T17 wymaga T12. T18 wymaga T8+T10.**

---

## Szczegółowy opis każdego zadania

### A0 — Doładuj Anthropic credit *(Sebastian, manual)*
**Problem:** `turbo_extract` i `auto_extract` crashują z `credit balance too low`. Extraction nowych encji/eventów/commitmentów = wyłączone.
**Akcja:** Console Anthropic → Plans & Billing → Purchase credits.
**Efekt:** `turbo_extract` wraca do życia, T9 (backfill) i T16 (entity linking) stają się możliwe.

---

### T1 — ENABLE_TOOL_ROUTING *(5 minut)*
**Problem:** Query router jest napisany i przetestowany, ale wyłączony. Pytania o WhatsApp szukają w emailach i Teams. Pytania o email trafiają do spreadsheetów.
**Implementacja:**
```bash
# Dodać do .env:
ENABLE_TOOL_ROUTING=true
# Restart API
systemctl --user restart gilbertus-api
```
**Efekt:** Source routing per zapytanie. Pytania o komunikację z Rochem → email + WA, nie spreadsheet.

---

### T2 — Log rotation *(30 minut)*
**Problem:** 273 pliki logów, 91 MB. Bez rotacji za kilka tygodni zapełni się dysk i system przestanie pisać logi.
**Implementacja:** `/etc/logrotate.d/gilbertus` z konfiguracją weekly, 4 rotacje, compress, missingok, notifempty.
**Efekt:** Dysk pod kontrolą, logi zachowane 4 tygodnie.

---

### T3 — PgBouncer setup *(2h)*
**Problem:** 47/100 aktywnych połączeń PG teraz. 59 cron jobów + 4 uvicorn workers. W szczycie: każdy worker ma pulę min 5 = 20 połączeń samego API + 30+ z cron = potencjalnie >80. "Too many clients" pojawia się już w logach `auto_embed`.
**Implementacja:**
- `apt install pgbouncer`
- Konfiguracja: transaction pooling mode, max_client_conn=200, default_pool_size=20, docelowy port 5433
- Cron jobs: zmiana połączeń na port 5433 (przez PgBouncer)
- Uvicorn: zostawić na 5432 bezpośrednio (transakcje wymagają session mode → szybciej bez bouncer)
- Restart PG z max_connections=150 (margines)
**Efekt:** Cron jobs przestają konkurować z API o połączenia. "Too many clients" eliminowane.

---

### T4 — Qdrant drift fix *(1h)*
**Problem:** Qdrant ma 109,089 wektorów, PG ma 105,776 chunków z embedding_id. Różnica: ~3,313 orphaned wektorów w Qdrant. Nie są używane (PG nie ma do nich referencji) ale zaśmiecają kolekcję i spowalniają search.
**Implementacja:**
```python
# Skrypt: pobierz wszystkie embedding_id z PG
# Porównaj z ID w Qdrant
# DELETE orphany z Qdrant batch
```
**Efekt:** Czystsza kolekcja, lekkie przyśpieszenie search.

---

### T5 — Anthropic/OpenAI credit alert *(1h)*
**Problem:** System przestał ekstrakcji bez żadnego alertu. Sebastian dowiedział się przypadkowo.
**Implementacja:** Cron co 6h:
- Anthropic: GET `/v1/organizations/me` (lub proxy przez koszt tracker)
- Alternatywnie: jeśli `auto_extract` rzuca credit error → natychmiastowy WA alert do Sebastiana
- Próg: < $20 balance → alert
**Efekt:** Nigdy więcej cichego śmierci extraction pipeline.

---

### T6 — Per-stage timing → PG aggregation *(2h)*
**Problem:** `StageTimer` istnieje i mierzy etapy (`interpret`, `retrieve`, `answer`), ale wyniki nie są zapisywane. Nie wiadomo gdzie tracimy czas.
**Implementacja:**
- Tabela `query_performance (date, hour, stage, p50_ms, p95_ms, count)`
- Po każdym `/ask`: INSERT do tabeli stage times
- Endpoint `/performance/stats?days=7` → dane dla frontendu
**Efekt:** Widać dokładnie: ile ms zajmuje interpret, retrieve, answer. Można targetować bottleneck.
**Blokuje:** T15 (alerty jakości)

---

### T7 — Interpretation cache → PG shared *(2h)*
**Problem:** Cache query interpretera jest in-memory w każdym workerze. 4 workery = 4 niezależne cache. To samo pytanie → 4 API calls do Anthropic zamiast 1.
**Implementacja:**
- Tabela `interpretation_cache (query_hash TEXT PK, result_json JSONB, expires_at TIMESTAMPTZ)`
- Modyfikacja `query_interpreter.py`: `_cache_get()` → SELECT z PG, `_cache_put()` → UPSERT
- TTL: 15 minut (zamiast 5 min w-memory)
- Zachować in-memory jako L1 cache (sprawdź in-memory najpierw, potem PG)
**Efekt:** 4x mniej API calls do Anthropic dla interpretacji. Szybciej przy powtarzających się pytaniach.

---

### T8 — Hybrid search BM25 (tsvector + GIN index) *(3h)*
**Problem:** Tylko vector search (semantic). Zapytania z konkretnymi nazwami ("Diana", "REH Q4 2024", "GoldenPeaks") często przegrywają z semantyką gdy embedding nie wyłapie exact match.
**Implementacja:**
1. Dodaj kolumnę: `ALTER TABLE chunks ADD COLUMN text_tsv tsvector GENERATED ALWAYS AS (to_tsvector('polish', text)) STORED`
2. Dodaj GIN index: `CREATE INDEX CONCURRENTLY idx_chunks_text_tsv ON chunks USING GIN(text_tsv)`
3. Modyfikacja `retriever.py`: funkcja `_bm25_search(query, top_k, filters)` → FTS query
4. Reciprocal Rank Fusion (RRF): score_final = 1/(60 + rank_vector) + 1/(60 + rank_bm25)
5. Merge results → sort by RRF score → top_k
**Czas indeksowania:** ~10 min dla 105k chunków.
**Efekt:** +30-40% recall dla zapytań z nazwami własnymi i specjalistycznym słownictwem. Kluczowe dla "cashflow REH", "Roch styczeń", "GoldenPeaks oferta".

---

### T9 — Backfill email gap *(1h setup + auto)*
**Problem:** Email 2023 I półrocze: styczeń-lipiec = kilka maili, nie reprezentatywne. PST pliki mają dane ale nie wszystkie przeszły ekstrakcję.
**Implementacja:**
- `backfill_email_gap.py` już istnieje — uruchomić
- Sprawdzić logi które emaile zostały pominięte
- Re-extraction przez `turbo_extract` na pominięte daty
**Wymaga:** A0 (Anthropic credit)
**Efekt:** Pełniejszy coverage 2023, lepsze odpowiedzi na pytania historyczne.

---

### T10 — Top-k increase + BM25 reranking *(2h)*
**Problem:** Default: 8 chunków do odpowiedzi dla `retrieval`, 14 dla `summary`. Za mało kontekstu dla złożonych pytań finansowych i strategicznych.
**Implementacja:**
- `analysis` i `summary`: answer_match_limit 14→25, prefetch_k 70→150
- Po hybrid search (T8): bierz top 150 z vector+BM25, rerank przez:
  1. RRF score (już z T8)
  2. Diversity filter: max 3 chunks z tego samego dokumentu
  3. Recency boost: dokumenty z ostatnich 30 dni +10% score
- Do answering: top 25 chunks
**Wymaga:** T8 (hybrid search)
**Efekt:** Pełniejsza analiza dla złożonych pytań. "Cashflow REH" dostaje 25 fragmentów z raportów, emaili, Teams — nie 8.

---

### T11 — Data coverage dashboard *(2h)*
**Problem:** Nie wiadomo które miesiące mają luki bez ręcznej analizy SQL.
**Implementacja:**
- Endpoint: `GET /coverage/heatmap` → macierz {source_type, year_month, doc_count}
- Frontend: tabela/heatmap w sekcji Intelligence → Data Coverage
- Highlight: miesiące < 10 docs jako "luka" (czerwony), 10-50 jako "partial" (żółty)
**Efekt:** Wizualizacja luk danych. Wiadomo gdzie backfillować.

---

### T12 — Feedback loop (frontend + backend) *(3h)*
**Problem:** 0 zebranego feedbacku. System nie wie czy odpowiedzi są dobre czy złe. Brak danych do poprawy jakości.
**Implementacja:**
- Backend: endpoint `POST /feedback {run_id, rating: 1|-1, comment?}` → INSERT do `response_feedback`
- Frontend: przyciski 👍 / 👎 pod każdą odpowiedzią w chacie + opcjonalny komentarz
- Weekly cron: analiza złych odpowiedzi → identyfikacja wzorców (jaki source_type, question_type, analysis_depth)
**Efekt:** Dane do trendu jakości. Podstawa T17 (weekly review).

---

### T13 — Shared answer cache → PG *(1h)*
**Problem:** Answer cache jest in-memory per worker (tabela PG `answer_cache` istnieje ale cache write/read też jest w-memory). Cache nie jest współdzielony między workerami.
**Implementacja:**
- Sprawdzić czy `_check_answer_cache()` i `_write_answer_cache()` w `main.py` używają PG czy in-memory
- Jeśli in-memory: przenieść do PG (tabela istnieje)
- TTL: 30 min dla zapytań user, 6h dla /brief
**Efekt:** 4 workery współdzielą cache. Odpowiedzi na te same pytania natychmiastowe.

---

### T14 — Progressive context dla analysis queries *(2h)*
**Problem:** Dla pytań `analysis`/`summary` system bierze chunki jednorazowo i odpowiada. Przy złożonych pytaniach często brakuje kontekstu z konkretnych źródeł.
**Implementacja:**
- Po pierwszym retrieval: wyodrębnij key entities/dates z top chunks
- Targeted follow-up query: `f"{query} {entity} {date_range}"`
- Merge obu zbiorów chunków → deduplika → do answering
- Limit: tylko dla question_type=analysis lub analysis_depth=high
**Wymaga:** T10 (powiększony top-k)
**Efekt:** Pytanie "co wiem o cashflow REH w Q4 2025" → najpierw generalne chunks, potem targeted "Diana Skotnicka cashflow Q4" → pełniejsza odpowiedź.

---

### T15 — Retrieval quality alerts *(1h)*
**Problem:** Brak monitoringu jakości w czasie rzeczywistym. Nie wiadomo kiedy retrieval degraduje.
**Implementacja:**
- Jeśli `used_fallback=true` > 20% requestów w ostatniej godzinie → alert
- Jeśli `retrieved_count < 3` > 30% queries → alert "luka danych"
- Jeśli `latency_ms > 30000` p95 → alert "system wolny"
- Delivery: WhatsApp do Sebastiana
**Wymaga:** T6 (per-stage timing w PG)

---

### T16 — Entity linking improvement *(2h)*
**Problem:** Retriever rozszerza query o aliasy osób z tabeli `people`, ale linkowanie jest niepełne. Np. "Roch" nie zawsze łączy się z "Roch Baranowski" i jego historią w REH.
**Implementacja:**
- Przejrzyj tabelę `people` i `entities` — sprawdź coverage
- Dodaj brakujące aliasy dla kluczowych osób (Roch, Krystian, Diana, Makaruk, etc.)
- Modyfikacja `resolve_person_aliases()`: fuzzy match (threshold 0.8) zamiast substring
- Dodaj org-level expansion: "REH" → "Respect Energy Holding", "Respect Energy S.A." etc.
**Wymaga:** A0 (Anthropic credit — do re-extraction entity relationships)
**Efekt:** Lepszy recall dla zapytań per-osoba.

---

### T17 — Weekly quality review automation *(3h)*
**Problem:** Nie ma automatycznej oceny czy Gilbertus poprawia się czy pogarsza w czasie.
**Implementacja:**
- Cron co piątek 18:00: pobierz 30 losowych zapytań z ostatnich 7 dni
- Odpowiedz na każde dwoma metodami: current vs current+T10 (więcej kontekstu)
- LLM-as-judge (Haiku): oceń obie odpowiedzi 1-5
- Raport do WhatsApp: "Ten tydzień vs poprzedni: avg score 3.2 → 3.8 (+19%)"
**Wymaga:** T12 (feedback), T6 (timing)

---

### T18 — Chunking quality review *(4h)*
**Problem:** Obecne chunki mają różną optymalność dla różnych źródeł. Email chunk = inne optimum niż Teams chunk niż WA chunk.
**Implementacja:**
- Analiza: avg chunk size per source_type, semantic coherence (embedding cosine similarity adjacent chunks)
- Identyfikacja zbyt długich (>2000 tokens) i zbyt krótkich (<50 tokens) chunków
- Proposal: osobne chunk_size per source_type (email: 800, teams: 600, WA: 400, document: 1200)
- Test: re-chunk 5% losowych dokumentów → porównaj retrieval quality
**Wymaga:** T8 (hybrid search jako baseline do porównania)

---

### T19 — PG tuning + monitoring *(1h)*
**Problem:** Po T3 (PgBouncer) i 4 workerach potrzeba weryfikacji że PG jest stabilne.
**Implementacja:**
- Zwiększ `max_connections` do 150 w docker-compose (+ restart)
- Dodaj do architecture_review.sh: sprawdzenie avg connections, idle connections > 50%
- Alert jeśli connections > 80% max_connections

---

## Ścieżka krytyczna (Critical Path)

```
[Dziś] T1 + T2
    → [Dzień 1] T3 (PgBouncer)
        → [Dzień 2] T7 (shared interp cache) + T8 (hybrid search)
            → [Dzień 3] T10 (top-k + reranking)
                → [Dzień 4] T14 (progressive context)
```

**Total: 4 dni do pełnego retrieval upgrade.**

Równolegle (nie blokują critical path):
- A0 (Sebastian) → T9 → T16: email backfill + entity linking
- T4 + T5 + T6: qdrant, credit alert, timing
- T11 + T12 + T13: dashboard, feedback, answer cache
- T15: po T6
- T17 + T18 + T19: tydzień 2

---

## Szacowany efekt na jakość

| Metryka | Teraz | Po T1+T8+T10 | Po wszystkim |
|---------|-------|-------------|--------------|
| Latencja p50 | ~10s | ~6s | ~4s |
| Recall (zapytania z nazwami) | ~60% | ~80% | ~90% |
| Kontekst per odpowiedź (chunks) | 8-14 | 20-25 | 20-25 |
| Stabilność (uptime bez błędów) | ~70% | ~85% | ~95% |
| Data coverage widoczna | 0% | 80% | 100% |
| Feedback zbierany | 0 | 0 | 100% |
