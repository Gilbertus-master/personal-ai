# Gilbertus Improvements Research

Data: 2026-03-29

## 1. Observability

### Stan obecny
- Tabela `ask_runs` posiada 35+ kolumn, w tym `stage_ms` (JSONB) przechowujacy czasy poszczegolnych etapow.
- Klasa `StageTimer` w `app/db/stage_timer.py` mierzy etapy: interpret, retrieve, answer, orchestrator, evaluate.
- Dashboard observability: `/observability/dashboard` odpytuje `ask_runs` o percentyle latencji, rozklad etapow, koszty, najwolniejsze zapytania.
- Cron `/observability/alert-check` co 30 min sprawdza wolne zapytania i skoki bledow.
- `run_id` jest zwracany w `AskResponse` do klienta.
- Brak integracji z LangSmith/LangChain tracing.

### Architektura
- `ask_run_id` NIE jest propagowany miedzy modulami — tworzony dopiero na koncu via `persist_ask_run_best_effort()`.
- Oznacza to, ze posrednie etapy (interpret, retrieve) nie maja dostepu do wspolnego identyfikatora trace.

### Braki
- Brak propagacji `run_id` do sub-modulow (interpret, retrieve, answer).
- Brak endpointu per-request trace (GET /observability/trace/{run_id}).
- Brak headera `X-Gilbertus-Run-ID` w odpowiedzi HTTP.

---

## 2. Tool Routing

### Stan obecny
- `query_router.py` istnieje z flaga `ENABLE_DEEP_ROUTING`.
- `interpret_query` uzywa Claude Haiku — `source_types` NIE sa automatycznie wnioskowane z tresci pytania, tylko wyciagane jesli uzytkownik je poda explicite.
- Filtrowanie odbywa sie post-retrieval w `retriever.py` (linie 290-291): `if source_types and match.source_type not in source_types: continue`.
- `ALLOWED_SOURCE_TYPES` zawiera 9 typow, ale ingestion tworzy 12+ typow.
- Routing dispatches wg `question_type`: chronology, analysis, summary, retrieval.

### Braki
- Brak inteligentnego mapowania wzorcow pytan na grupy source type.
- Jesli uzytkownik nie poda source_types, odpytywane sa wszystkie zrodla (brak optymalizacji).
- Niezgodnosc miedzy ALLOWED_SOURCE_TYPES (9) a faktycznymi typami w ingestion (12+).

---

## 3. Circuit Breakers

### Stan obecny
- Klasa `CircuitBreaker` z `resilience.py` NIE jest uzywana w pipeline /ask (tylko w `data_guardian`).
- `check_budget` blokuje gdy `hard_limit=True` i `pct>=100`, zwraca HTTP error.
- Trzy-warstwowy system kosztow: budget check + logging + per-request capture.

### Ryzyka
- **embed_texts**: nieobsluzone typy wyjatkow w petli while moga powodowac infinite loop.
- **voice_ws**: ryzyko async hang bez timeout.
- **Answer evaluator**: `should_retry` moze retryowac w nieskonczonosc (brak limitu iteracji).

### Braki
- Brak circuit breakera w /ask pipeline.
- Brak limitu retry w evaluation loop.
- Brak safety catch-all w embed_texts.

---

## 4. Decision Journal

### Stan obecny
- Tabela `decisions`: id, decision_text, context, expected_outcome, area, confidence, decided_at, created_at, source_event_id, review_status, next_review_at.
- Tabela `decision_outcomes` do sledzenia wynikow (oceny 1-5).
- Auto-capture JUZ ISTNIEJE w `decision_intelligence.py`: skanuje tabele events pod katem typow 'decision'/'approval'.
- Przypomnienia o review via WhatsApp juz zaimplementowane.
- Kalibracja pewnosci, analiza wzorcow, wzbogacanie kontekstem rynkowym — wszystko istnieje.
- Endpointy: POST /decision, POST /decision/{id}/outcome, GET /decisions, GET /decisions/patterns.

### Braki
- Brak dedykowanego endpointu POST /decisions/scan (auto_capture jest embedded w pipeline, nie wystawiony jako API).
- Brak endpointu GET /decisions/pending (decyzje wymagajace review).
