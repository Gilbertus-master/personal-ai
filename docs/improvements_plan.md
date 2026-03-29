# Gilbertus Improvements Plan

Data: 2026-03-29

## Kolejnosc implementacji

1. Circuit Breakers — safety, zero risk
2. Tool Router — nowy modul, feature flagged
3. Decision endpoints — cienkie wrappery na istniejacym kodzie
4. Observability trace — integracja z istniejacym pipeline

---

## 1. Circuit Breakers (uzupelnienie)

**Priority:** HIGH | **Risk:** LOW

### Zadania

- **max_eval_retries=2** — dodac limit retry do answer evaluator retry loop w `main.py`. Jesli evaluator zwroci should_retry po 2 probach, zaakceptowac ostatnia odpowiedz i zalogowac warning.
- **catch-all w embed_texts** — dodac ogolny exception handler do petli while w `index_chunks.py`, zeby nieobsluzone wyjatki nie powodowaly infinite loop. Logowac blad i przejsc dalej.
- **iteration counter w orchestratorze** — dodac max_iterations do wszystkich multi-step orchestrator loops. Domyslnie 5 iteracji.
- **Context size guard** — przed odpowiadaniem, jesli total context > 20000 znakow (~5000 tokenow), obciac do top-N chunkow i zalogowac warning. Zapobiega to przesylaniu zbyt duzego kontekstu do LLM.
- **Feature flag:** brak potrzeby (safety fixes, zawsze aktywne).

---

## 2. Tool Router (nowy modul)

**Priority:** MEDIUM | **Risk:** LOW (feature flagged)

### Architektura

Nowy plik: `app/retrieval/tool_router.py`

### Grupy zrodel

| Grupa | Source types |
|---|---|
| personal_comms | whatsapp, whatsapp_live, email |
| business_comms | email, teams, audio_transcript |
| trading | document, spreadsheet, email |
| knowledge | document, chatgpt, audio_transcript, pdf |
| all | brak filtra |

### Logika

1. Jesli interpreter zwrocil `source_types` -> uzyj ich (user explicite podal).
2. Jesli `source_types` jest null -> wnioskuj grupe z `question_type` + keywords.

### Wzorce keyword

- "WhatsApp", "wiadomosc", "napisal" -> personal_comms
- "spotkanie", "teams", "call", "rozmowa" -> business_comms
- "trading", "cena", "PPA", "kontrakt", "wolumen" -> trading
- "dokument", "raport", "analiza" -> knowledge
- Brak dopasowania -> all

### Integracja

- Punkt wpiecia: w `main.py` /ask, po interpret, przed retrieve.
- Feature flag: `ENABLE_TOOL_ROUTING=true` w `.env` (domyslnie false).
- Gdy flaga wylaczona, zachowanie bez zmian (all sources).

---

## 3. Decision Auto-scan Endpoints

**Priority:** MEDIUM | **Risk:** LOW

### Nowe endpointy

**POST /decisions/scan**
- Wywoluje `auto_capture_decisions()` z `decision_intelligence.py`.
- Zwraca liczbe przechwyconych decyzji.
- Brak nowego crona (istniejacy `decision_enrichment` cron o 22:00 juz uruchamia auto-capture).

**GET /decisions/pending**
- Odpytuje decisions gdzie `review_status='pending'` AND `confidence < 0.8`.
- Zwraca liste decyzji auto-wykrytych wymagajacych manualnego review.
- Sortowanie: po confidence ASC (najmnniej pewne pierwsze).

### Uwagi
- Oba endpointy wykorzystuja istniejaca infrastrukture.
- Nie wymagaja zmian w schemacie DB.

---

## 4. Observability Tracing

**Priority:** MEDIUM | **Risk:** LOW

### Zadania

**Propagacja run_id**
- Generowac UUID na poczatku /ask (zamiast na koncu).
- Przekazywac run_id przez caly pipeline: interpret -> retrieve -> answer.
- Uzyc tego samego run_id jako ask_runs.id.

**Response header**
- Dodac `X-Gilbertus-Run-ID` header do odpowiedzi HTTP /ask.
- Pozwala klientowi odwolac sie do konkretnego zapytania w debugowaniu.

**Trace endpoint**
- GET /observability/trace/{run_id}
- Zwraca pelny waterfall: stage_ms breakdown, liczba matchow, uzyty model, koszt, info o bledach.
- Brak zmian w schemacie (ask_runs juz ma wszystkie potrzebne dane, run_id = ask_runs.id).
