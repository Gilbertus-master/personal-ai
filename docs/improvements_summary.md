# Gilbertus Improvements — 2026-03-29

## Zaimplementowane

### 1. Circuit Breakers

**Eval retry limit** (`app/api/main.py`):
- Evaluator-Optimizer pattern ograniczony do `MAX_EVAL_RETRIES=2` (env var)
- Przed zmiana: evaluator mogl retry w nieskonczonosc
- Po zmianie: max 2 retry, potem akceptuje odpowiedz

**Embed catch-all** (`app/retrieval/index_chunks.py`):
- Dodano `except Exception` catch-all na koncu `embed_texts()` while loop
- Przed zmiana: nieobsluzony exception powodowal nieskonczona petle (brak break/raise)
- Po zmianie: loguje structlog error i reraise

**Context size guard** (`app/api/main.py`):
- Przed wywolaniem `answer_question()` sprawdza laczny rozmiar kontekstu
- Jesli >80000 znakow (~20k tokenow): tnie do top-N wg score, loguje warning
- Konfiguracja: `MAX_CONTEXT_CHARS=80000` (env var)

**Test:** Brak feature flaga — bezposrednie poprawki bezpieczenstwa. Non-regression gate OK.

---

### 2. Tool Router

**Nowy modul:** `app/retrieval/tool_router.py`

**Jak wlaczyc:** `ENABLE_TOOL_ROUTING=true` w `.env` (domyslnie false)

**Grupy zrodel:**
| Grupa | Source types |
|-------|-------------|
| personal_comms | whatsapp, whatsapp_live |
| business_comms | email, teams, audio_transcript, calendar |
| trading | document, spreadsheet, email, pdf |
| knowledge | document, chatgpt, audio_transcript, pdf |
| all | brak filtra (fallback) |

**Logika:**
1. Jesli interpreter zwrocil source_types -> respektuj (passthrough)
2. Jesli null -> dopasuj grupe na podstawie keyword patterns w query
3. Jesli brak keyword match -> uzyj domyslnej grupy wg question_type

**Keyword patterns:** whatsapp/wiadomosc -> personal_comms, spotkanie/teams/call -> business_comms, trading/cena/PPA/kontrakt -> trading, dokument/raport/pdf -> knowledge

**Integracja:** `app/api/main.py` — po interpret, przed retrieve.

---

### 3. Decision Auto-scan

**POST `/decisions/scan`** (`app/api/decisions.py`):
- Parametr: `hours` (1-168, domyslnie 24)
- Wywoluje istniejacy `auto_capture_decisions()` z `decision_intelligence.py`
- Skanuje tabele events po event_type IN ('decision', 'approval')
- Zwraca: `{captured: N, decisions: [...], hours_scanned: N}`

**GET `/decisions/pending`** (`app/api/decisions.py`):
- Parametry: `max_confidence` (0-1, domyslnie 0.8), `limit` (1-200, domyslnie 50)
- Zwraca decyzje z `review_status IN ('pending', 'reminded')` i `confidence < max_confidence`
- Uzycie: przeglad auto-wykrytych decyzji o niskiej pewnosci

**Cron:** Istniejacy decision_enrichment cron (22:00 CET) juz uruchamia auto-capture. Endpoint `/decisions/scan` sluzy do recznego triggera.

---

### 4. Observability Tracing

**GET `/observability/trace/{run_id}`** (`app/api/observability.py`):
- Pelny waterfall jednego /ask requesta
- Zwraca: stage_ms breakdown z procentami, bottleneck, model, tokens, cost, error info
- Dolacza matches z tabeli `ask_run_matches` (rank, score, source_type, excerpt)

**X-Gilbertus-Run-ID header** (`app/api/main.py`):
- Kazda odpowiedz /ask zawiera header `X-Gilbertus-Run-ID: <id>`
- Umozliwia trace-by-header w logach/monitoring

**Uzycie:**
```bash
# Wyslij zapytanie i odczytaj run_id z headera
curl -v http://127.0.0.1:8000/ask -d '{"query":"test"}' 2>&1 | grep X-Gilbertus

# Pelen trace
curl http://127.0.0.1:8000/observability/trace/12345 | python3 -m json.tool
```

---

## Nieimplementowane (z uzasadnieniem)

### run_id propagacja do sub-modulow
- **Powod:** Wymaga zmian sygnatur w 6+ modulach (interpret_query, search_chunks, answer_question, etc.)
- **Obecne rozwiazanie:** run_id tworzony na koncu w `persist_ask_run_best_effort()`, stage_ms zbierane przez StageTimer w /ask endpoint — wystarczajace do trace per-request
- **Rekomendacja:** Zaimplementowac gdy potrzebne bedzie per-module distributed tracing (np. z OpenTelemetry)

### CircuitBreaker w /ask pipeline
- **Powod:** CircuitBreaker z resilience.py jest zaprojektowany do external service health checks (half-open/closed states). /ask pipeline ma juz budget check + retry limits — dodanie CB bylby redundantne
- **Istniejace zabezpieczenia:** check_budget (hard block), eval retry limit, context trim, request rate limiter (30/min)

---

## Zmodyfikowane pliki
- `app/api/main.py` — circuit breakers, tool routing integration, X-Gilbertus-Run-ID
- `app/api/decisions.py` — POST /decisions/scan, GET /decisions/pending
- `app/api/observability.py` — GET /observability/trace/{run_id}
- `app/retrieval/tool_router.py` — **NOWY** modul smart source routing
- `app/retrieval/index_chunks.py` — embed_texts catch-all exception

## Non-regression
- Gate: 15/15 metrics OK
- Lint: 0 nowych bledow (4 pre-existing E402 w main.py)
