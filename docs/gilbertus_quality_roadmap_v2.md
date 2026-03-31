# Gilbertus Quality Roadmap v2 — Pełny harmonogram wszystkich faz
*Wygenerowany: 2026-03-31 | Stan systemu zweryfikowany*

---

## 1. INWENTARZ ZADAŃ — wszystkie fazy

| ID | Zadanie | Faza | Szac. czas | Status |
|----|---------|------|-----------|--------|
| T1 | ENABLE_TOOL_ROUTING | F1 | 5 min | ⬜ todo |
| T2 | Log rotation (logrotate) | F1 | 30 min | ⬜ todo |
| T3 | PgBouncer setup | F1 | 2h | ⬜ todo |
| T4 | Qdrant drift fix (3313 orphans) | F1 | 1h | ⬜ todo |
| T5 | Credit alert (Anthropic/OpenAI) | F1 | 1h | ⬜ todo |
| T6 | Per-stage timing → PG | F1 | 2h | ⬜ todo |
| T7 | Interpretation cache → PG shared | F2 | 2h | ⬜ todo |
| T8 | Hybrid search BM25 (tsvector+GIN+RRF) | F2 | 3h | ⬜ todo |
| T9 | Email backfill (2023 luki) | F2 | 1h+auto | ⬜ todo |
| T10 | Top-k increase + BM25 reranking | F2 | 2h | ⬜ todo |
| T11 | Data coverage dashboard | F3 | 2h | ⬜ todo |
| T12 | User feedback loop (chat 👍/👎) | F3 | 3h | ⬜ todo |
| T13 | Answer cache TTL + verify | F3 | 30 min | ⬜ todo |
| T14 | Progressive context dla analysis | F3 | 2h | ⬜ todo |
| T15 | Retrieval quality alerts | F4 | 1h | ⬜ todo |
| T16 | Entity linking improvement | F4 | 2h | ⬜ todo |
| T17 | Weekly quality review automation | F5 | 3h | ⬜ todo |
| T18 | Chunking quality review & optimization | F5 | 4h | ⬜ todo |
| T19 | PG max_connections tuning | F5 | 1h | ⬜ todo |

**Total: ~33h pracy technicznej**

---

## 2. ANALIZA ZALEŻNOŚCI

### Zależności twarde (Y nie może startować bez X)

```
T3 (PgBouncer)
  └─► T7 (interp cache PG)   — T7 otwiera write/read per każde zapytanie;
  │                             bez connection poolera może wyczerpać limity
  └─► T8 (hybrid search)     — CREATE INDEX CONCURRENTLY na 105k wierszach
                                potrzebuje stabilnych połączeń PG

T8 (hybrid search)
  └─► T10 (top-k + reranking) — RRF łączy score z vectora + score z BM25;
                                 bez T8 nie ma drugiej nogi do RRF

T10 (top-k + reranking)
  └─► T14 (progressive ctx)  — progressive context pobiera 150 chunków,
                                 bez T10 nadmiar chunków = chaos bez sensu
                                 
T6 (per-stage timing PG)
  └─► T15 (retrieval alerts)  — alerty bazują na danych timing;
                                 bez T6 nie ma co alertować

T12 (user feedback loop)
  └─► T17 (weekly review)    — weekly review porównuje odpowiedzi vs oceny
                                 użytkownika; bez T12 tylko LLM-judge

T8 + T10
  └─► T18 (chunking review)  — potrzeba hybrid search jako baseline
                                 i większego top-k do testu re-chunk
```

### Zależności miękkie (lepiej w tej kolejności, ale nie blokuje)

```
T3 → T13  (answer cache już używa PG, ale TTL verify lepiej po stabilnym PgBouncer)
T9 → T16  (backfill daje świeże dane entity extraction; T16 lepszy po T9)
```

### W pełni niezależne (mogą startować od razu)

```
T1  ENABLE_TOOL_ROUTING     — zmiana .env, restart API
T2  Log rotation            — logrotate config
T4  Qdrant drift fix        — standalone Python script
T5  Credit alert            — nowy cron script
T9  Email backfill          — wywołanie istniejącego skryptu
T11 Coverage dashboard      — nowy endpoint + frontend, brak zależności
T13 Answer cache TTL verify — odczyt + poprawa istniejącego kodu
T16 Entity linking          — tabela people ma 17 rekordów, Anthropic OK
```

---

## 3. GRAF WIZUALNY

```
DZIEŃ 0 ──────────────────────────────────────────────────────────
T1 [5min]   ●━━━●  niezależny
T2 [30min]  ●━━━━━━━━━━━━━━━━●  niezależny
T13 [30min] ●━━━━━━━━━━━━━━━━●  niezależny

DZIEŃ 1 ──────────────────────────────────────────────────────────
T3 [2h]  ●━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━●─────────────────► odblokuje T7, T8
T4 [1h]  ●━━━━━━━━━━━━━━━━●  niezależny
T5 [1h]  ●━━━━━━━━━━━━━━━━●  niezależny
T6 [2h]  ●━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━●─────────────────────► odblokuje T15
T9 [1h]  ●━━━━━━━━━━━━━━━━● (+ runs overnight) niezależny

DZIEŃ 2 ──────────────────────────────────────────────────────────
T7 [2h]  ━━━━━━━━━━(po T3)━━━●━━━━━━━━━━━━━━━━━━━━━━━━━━━━━●  niezależny dalej
T8 [3h]  ━━━━━━━━━━(po T3)━━━●━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━●─► odblokuje T10, T18
T11 [2h] ●━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━●  niezależny
T16 [2h] ●━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━●  niezależny

DZIEŃ 3 ──────────────────────────────────────────────────────────
T10 [2h] ━━━━━━━━━━(po T8)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━●━━━━━━━━━●─► odblokuje T14, T18
T12 [3h] ●━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━●  niezależny
T15 [1h] ━━━━━━━━━━(po T6)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━●

DZIEŃ 4 ──────────────────────────────────────────────────────────
T14 [2h] ━━━━━━━━━━(po T10)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━●
T19 [1h] ●━━━━━━━━━━━━━━━━●  po T3 (weryfikacja)

TYDZIEŃ 2 (07-10.04) ─────────────────────────────────────────────
T17 [3h] ━━━━━━━━━━(po T12+T6)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━●
T18 [4h] ━━━━━━━━━━(po T8+T10)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━●
```

---

## 4. HARMONOGRAM DZIENNY — szczegółowy

### DZIEŃ 0 — 31.03 (dziś) | ~1h pracy

**Równolegle:**

**T1 — ENABLE_TOOL_ROUTING** `5 min`
Dodanie flagi do `.env`, restart API. Natychmiastowy efekt: pytania o WhatsApp trafiają do WA, o email do email — nie wszędzie naraz.

**T2 — Log rotation** `30 min`
Konfiguracja `/etc/logrotate.d/gilbertus`: weekly, compress, retain 4 tygodnie, dla wszystkich plików w `logs/`. Eliminuje ryzyko zapełnienia dysku.

**T13 — Answer cache verify + TTL** `30 min`
Answer cache **już używa PG** (`answer_cache` tabela). Sprawdzenie TTL (aktualnie 1h), poprawienie do 30 min dla user queries, 6h dla `/brief`. Upewnienie się że cross-worker cache działa.

---

### DZIEŃ 1 — 01.04 | ~7h pracy (4 wątki równolegle)

**T3 — PgBouncer setup** `2h`
Instalacja (`apt install pgbouncer`), konfiguracja transaction pooling mode: max_client_conn=200, default_pool_size=15, port 5433. Cron joby → port 5433. Uvicorn workers → port 5432 bezpośrednio (session mode). Restart PG z max_connections=150. Eliminuje "too many clients".

**T4 — Qdrant drift fix** `1h`
Script Python: pobierz wszystkie `embedding_id` z PG (105,776), pobierz wszystkie ID z Qdrant (109,089), diff = 3,313 orphaned. Batch DELETE przez Qdrant API. Czystsza kolekcja, lżejszy search.

**T5 — Credit alert** `1h`
Nowy cron co 6h: test query do Anthropic API → jeśli 400 credit error → natychmiastowy alert WA do Sebastiana. Próg: $20 (jeśli API balance endpoint dostępny). Failsafe: jeśli extraction nie działała >2h → alert.

**T6 — Per-stage timing → PG** `2h`
Nowa tabela `query_stage_times (id, request_id, stage, duration_ms, question_type, created_at)`. Modyfikacja `/ask`: po każdym StageTimer.end() → INSERT. Endpoint `GET /performance/stats?days=7` → p50/p95/p99 per stage. Baza dla T15 (alertów).

**T9 — Email backfill** `1h setup + overnight`
Uruchomienie `backfill_email_gap.py` + sprawdzenie jakie daty zostały pominięte. Restart `turbo_extract` na brakujących datach. Działa w tle przez noc.

---

### DZIEŃ 2 — 02.04 | ~8h pracy (4 wątki równolegle)

**T7 — Interpretation cache → PG shared** `2h` *(wymaga T3)*
Nowa tabela `interpretation_cache (query_hash TEXT PK, result_json JSONB, expires_at TIMESTAMPTZ)`. Modyfikacja `query_interpreter.py`: `_cache_get()` → najpierw in-memory (L1, 5 min), potem PG (L2, 15 min). `_cache_put()` → zapis do obu. Wszystkie 4 workery współdzielą L2. Efekt: 4x mniej Anthropic API calls dla tych samych pytań.

**T8 — Hybrid search BM25** `3h` *(wymaga T3)*
3 kroki:
1. `ALTER TABLE chunks ADD COLUMN text_tsv tsvector GENERATED ALWAYS AS (to_tsvector('polish', text)) STORED` — ~10 min generowania
2. `CREATE INDEX CONCURRENTLY idx_chunks_tsv ON chunks USING GIN(text_tsv)` — ~15 min w tle
3. Modyfikacja `retriever.py`: nowa funkcja `_bm25_search()` używająca `to_tsvector` + `ts_rank`. Funkcja `search_chunks()`: uruchamia vector search i BM25 równolegle, łączy przez RRF: `score = 1/(60+rank_v) + 1/(60+rank_bm25)`, sort DESC.
Efekt: +30-40% recall dla nazw własnych (Roch, Diana, REH, GoldenPeaks, Kuźmiński).

**T11 — Data coverage dashboard** `2h` *(niezależny)*
Backend: `GET /coverage/heatmap` → zapytanie SQL grupujące dokumenty per (source_type, rok, miesiąc). Frontend: nowa strona w sekcji Intelligence → "Pokrycie danych" z tabelą heatmap. Kolory: <10 docs = czerwony, 10-50 = żółty, >50 = zielony. Widać luki na pierwszy rzut oka.

**T16 — Entity linking improvement** `2h` *(niezależny)*
Problem: tabela `people` ma **17 rekordów** przy 37,678 entities. Kluczowe osoby nie mają aliasów ani entity_id. Kroki:
1. Import kluczowych osób z entities do people (Roch Baranowski, Diana Skotnicka, Krystian Juchacz, Łukasz Jankowski, Makaruk, Natalka, etc.)
2. Dodanie aliasów (Roch = Baranowski = prezes REH)
3. Dodanie org-level expansion: "REH" → ["Respect Energy Holding", "Respect Energy S.A.", "RE"]
4. Modyfikacja `resolve_person_aliases()`: fuzzy matching zamiast substring (threshold 80%)
Efekt: "co mówił Roch" → rozszerzone do full name + rola → lepszy recall o 20-30%.

---

### DZIEŃ 3 — 03.04 | ~6h pracy (3 wątki równolegle)

**T10 — Top-k increase + BM25 reranking** `2h` *(wymaga T8)*
Modyfikacja `get_answer_match_limit()` i `get_prefetch_k()`:
- `retrieval`: 8→15, prefetch 30→60
- `summary`: 14→25, prefetch 50→120
- `analysis`: 18→30, prefetch 70→150
Po hybrid search: reranking przez RRF score już obliczony. Diversity filter: max 3 chunks per dokument (unika dominacji jednego źródła). Recency boost: docs z ostatnich 30 dni × 1.1. Efekt: odpowiedzi na złożone pytania finansowe z 3-4 źródeł zamiast 1.

**T12 — User feedback loop** `3h` *(niezależny)*
Problem: tabela `response_feedback` istnieje, backend `/feedback` istnieje, ale **chat nie ma UI do oceniania**.
1. Backend: endpoint `POST /feedback/chat {run_id, rating: 1|-1, comment?}` → INSERT do `response_feedback`
2. Frontend: `run_id` przekazywany w odpowiedzi chatu (już jest w `AskResponse.run_id`)
3. UI: pod każdą odpowiedzią chatu — dwa przyciski 👍 / 👎, optional pole komentarza, submit
4. State: po kliknięciu — feedback zablokowany (nie można zmienić), ikona podświetlona
Efekt: od tego momentu zbierane są dane o jakości odpowiedzi per pytanie/źródło.

**T15 — Retrieval quality alerts** `1h` *(wymaga T6)*
Nowy cron co godzinę: zapytanie do `query_stage_times` z ostatniej godziny:
- Jeśli `used_fallback=true` > 20% requestów → WA alert "⚠️ Query interpreter działa w trybie fallback (>20% requestów)"
- Jeśli avg `retrieved_count < 3` → WA alert "⚠️ Retrieval zwraca mało chunków — możliwa luka danych lub problem Qdrant"
- Jeśli p95 `latency_ms > 30,000` → WA alert "⚠️ System wolny — p95 >30s"

---

### DZIEŃ 4 — 04.04 | ~3h pracy (2 wątki)

**T14 — Progressive context dla analysis queries** `2h` *(wymaga T10)*
Modyfikacja pipeline w `main.py` dla `question_type=analysis` lub `analysis_depth=high`:
1. Pierwsze retrieval: top 30 chunków (standardowy hybrid search)
2. Extract: kluczowe encje z top 10 chunków (regex + entity lookup)
3. Targeted follow-up: `f"{query} {entity} {extracted_date}"` → dodatkowe 15 chunków
4. Merge + deduplika → max 35 unikalnych chunków do answering
5. Gate: tylko jeśli pierwsze retrieval zwróciło <5 chunków lub question_type=analysis
Efekt: "cashflow REH Q4 2025" → chunk 1 wskazuje na Dianę → follow-up "Diana Skotnicka cashflow Q4 2025" → raporty finansowe wchodzą do kontekstu.

**T19 — PG tuning + connection monitoring** `1h` *(po T3)*
Po tygodniu z PgBouncer: analiza `pg_stat_activity`. Dostrojenie `default_pool_size` w PgBouncer (jeśli idle>40% → zmniejszyć, jeśli wait>0 → zwiększyć). Dodanie do `architecture_review.sh`: sprawdzenie avg active connections, alert jeśli >80% max_connections. Optymalizacja `PG_POOL_MIN_SIZE` w uvicorn workers.

---

### TYDZIEŃ 2 — 07-10.04 | ~7h pracy

**T17 — Weekly quality review automation** `3h` *(wymaga T12 + T6)*
Nowy skrypt `scripts/weekly_quality_review.sh`, cron w piątki 17:00:
1. Losowe 30 zapytań z `ask_runs` z ostatnich 7 dni
2. Każde zapytanie → odpowiedź systemem (cache disabled)
3. LLM-judge (Haiku): oceń odpowiedź w skali 1-5 na 3 wymiary: completeness, accuracy, conciseness
4. Porównanie z poprzednim tygodniem
5. WA raport: "Jakość odpowiedzi ten tydzień: avg 3.8/5 (poprzednio: 3.2, +19%)"
6. Weak areas: które source_types i question_types mają najniższe oceny
Efekt: obiektywna metryka postępu + kierunek kolejnych улучшений.

**T18 — Chunking quality review & optimization** `4h` *(wymaga T8 + T10)*
Analiza istniejących chunków per source_type:
- Email: avg X chars, coherence score (embedding cosine similarity sąsiadów)
- Teams: avg Y chars, coherence
- WA: avg Z chars
- Documents: avg W chars
Identyfikacja zbyt długich (>1500 tokens → info loss przy retrieval) i zbyt krótkich (<50 chars → no-signal).
Test: re-chunk 500 losowych docs z nowymi parametrami per source_type. Porównaj recall@10 na zestawie 20 reference queries.
Jeśli recall wyższy o >5%: wdróż nowe parametry + rechunk all documents (w tle, ~2h).
Efekt: długoterminowa poprawa jakości search foundation.

---

## 5. ŚCIEŻKA KRYTYCZNA (Critical Path)

```
T3 (2h) → T8 (3h) → T10 (2h) → T14 (2h)
= 9h sekwencji = minimum 2 dni robocze
```

**Pozostałe 10 zadań** nie są na critical path i idą równolegle.

---

## 6. CO ROBIĘ RÓWNOLEGLE (widok na wątki)

```
Wątek A [Critical Path]:    T3 ──► T8 ──► T10 ──► T14
Wątek B [Cache/Perf]:       T1, T13 ──► T7 ──► T15
Wątek C [Data Quality]:     T4, T9 ──► T16 ──► T18
Wątek D [Monitoring]:       T2, T5, T6 ──► T19 ──► T17
Wątek E [UX/Frontend]:      T11, T12
```

---

## 7. SZACOWANE EFEKTY

| Metryka | Teraz | Po Dniu 2 | Po Dniu 4 | Po Tygodniu 2 |
|---------|-------|-----------|-----------|----------------|
| Latencja p50 `/ask` | ~10s | ~7s | ~5s | ~4s |
| Recall nazwy własne | ~60% | ~80% | ~85% | ~90% |
| Chunki per odpowiedź | 8-14 | 8-14 | 20-30 | 20-30 (better quality) |
| "Too many clients" errors | tak | nie | nie | nie |
| Qdrant orphans | 3313 | 0 | 0 | 0 |
| Shared interp cache | nie | tak | tak | tak |
| User feedback zbierany | nie | nie | tak | tak |
| Data coverage visible | nie | tak | tak | tak |
| Credit alert | nie | tak | tak | tak |
| Chunki quality | mixed | mixed | mixed | optimized |

---

## 8. ZADANIA SEBASTIANA (manualnie, poza harmonogramem)

| Akcja | Kiedy | Po co |
|-------|-------|-------|
| Auto-reload credit w Anthropic Console (próg $50) | Dziś | Nigdy więcej silent extraction death |
| Przeglądaj coverage dashboard po T11 | Po dniu 2 | Zidentyfikuj jakie dodatkowe dane warto importować |
| Klikaj 👍/👎 w chacie po T12 | Po dniu 3 | Dane do T17 (weekly review) — im więcej ocen, tym lepszy review |
| Review weekly quality report | Co piątek po T17 | Decyzja co poprawiać w kolejnym tygodniu |
