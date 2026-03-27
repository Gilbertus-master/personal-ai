# Gilbertus Albans — Ewidencja Prac B+R (IP Box)

## Informacje ogólne

- **Projekt:** Gilbertus Albans — Prywatny System AI do Zarządzania Spółkami
- **Właściciel IP:** Sebastian Jabłoński (osoba fizyczna)
- **Spółki korzystające:** REH (Respect Energy Holding), REF (Respect Energy Fuels)
- **Okres:** od 2026-03-20 (kontynuacja)
- **Kwalifikowany dochód z IP:** Software development — autorskie prawo do programu komputerowego

---

## Opis projektu B+R

### Problem badawczy
Zaprojektowanie i implementacja systemu sztucznej inteligencji (AI mentat), który:
1. Integruje dane z 11+ heterogenicznych źródeł (email, Teams, WhatsApp, audio, kalendarz, dokumenty)
2. Ekstrahuje encje (osoby, organizacje, produkty) i zdarzenia (konflikty, decyzje, zobowiązania) z tekstu naturalnego
3. Proaktywnie generuje analizy, raporty i alerty dla właściciela grupy spółek
4. Monitoruje rynek energetyczny (ceny, regulacje, konkurencja) i generuje strategic intelligence
5. Symuluje scenariusze "co jeśli?" z oceną wpływu na 5 wymiarów biznesowych

### Nowość / twórczość
- Unikalna architektura federacyjna: Gilbertus (master) + Omnius (agenci firmowi per spółka)
- System self-improving: automatyczna ekstrakcja reguł z nagrań audio właściciela (529 reguł)
- Multi-source extraction pipeline: 12 parallel workers, entity/event extraction z LLM
- Real-time competitive intelligence z RSS + internal archive cross-referencing
- Scenario analyzer z LLM-driven impact simulation

### Niepewność technologiczna
- Optymalizacja extraction coverage na heterogenicznych źródłach (email vs audio vs chat)
- Reliable structured output z LLM (JSON parsing, markdown stripping)
- WSL2 SSL compatibility dla external API calls
- Entity deduplication across sources (fuzzy matching)
- Cost-efficient LLM usage (Haiku vs Sonnet partitioning)

---

## Rejestr prac B+R

### Sesja 1: 2026-03-23 — 2026-03-24 (~20h)
**Temat:** Od pustej bazy do operational mentata
- Architektura: PostgreSQL + Qdrant + FastAPI + Claude
- Ingestion pipeline: email (Graph API), Teams, WhatsApp (OpenClaw), Plaud (audio)
- Entity extraction (5 typów) + Event extraction (15 typów)
- 18 MCP tools, QC pipeline

**Wynik:** 96k chunków, 35k encji, 92k eventów zindeksowanych

### Sesja 2: 2026-03-26 (~14h)
**Temat:** Stabilizacja i plan rozwoju
- Connection pooling, Teams grouping, entity dedup
- Bridge people↔entities
- Plan 5 faz A-E (ROI-driven)
- Bugfixy extraction (dedup, linkback)
- Ingestion Health Monitor

**Wynik:** 95 plików zmodyfikowanych, 5 commitów

### Sesja 3: 2026-03-27a (~4h)
**Temat:** Bugfixy + demo prep
- Dedup fixes, Plaud pipeline improvements
- Demo preparation for Krystian (REF)

### Sesja 4: 2026-03-27b (~8h)
**Temat:** Intelligence Layer — 13 modułów
- Commitments tracking, meeting prep, meeting minutes
- Response drafter, weekly synthesis, sentiment analysis
- Wellbeing monitor, contracts, delegation tracker
- Blind spots, network graph, predictive alerts
- Cron registry (centralized job management)
- Wave 1-3 "Jedna Pięść": feedback loops, authority framework, delegation chain, financial framework, calendar manager, strategic goals, org health

**Wynik:** 28 nowych modułów, 36 MCP tools, 64 tabele DB

### Sesja 5: 2026-03-27c — 2026-03-28 (~6h)
**Temat:** Wave 4 + Etap 0 + Etap 1
- **Wave 4 (Proaktywne Dowodzenie):**
  - Scenario analyzer: symulacja "co jeśli?" na 5 wymiarach
  - Market intelligence: 6 RSS źródeł energetycznych, auto-insights
  - Competitor intelligence: 7 konkurentów, SWOT analysis
- **Etap 0 (Fixy):** WhatsApp delivery, Plaud SSL, self-improving, Teams sync
- **Etap 1 (Delivery):**
  - Morning brief z market/competitor/predictive data
  - Weekly synthesis z competitive landscape + scenarios
  - Smart alert delivery (market/competitor/predictive → WhatsApp)
  - WhatsApp command interface (7 komend)
- **Voice pipeline:** STT (Whisper) → classify → execute → TTS (pluggable)

**Wynik:** 39 MCP tools, 74 tabele, morning brief na WhatsApp z danymi rynkowymi

---

## Metryki projektu (stan na 2026-03-28)

| Metryka | Wartość |
|---------|---------|
| Commitów | 83 |
| Plików zmodyfikowanych | 2,716 |
| Linii kodu dodanych | ~671,000 |
| Linii kodu usuniętych | ~2,190 |
| Modułów Python | 130+ |
| Skryptów bash | 85+ |
| Tabel DB | 74 |
| MCP tools | 39 |
| Cron jobs | 30+ |
| API endpoints | ~110 |
| Źródeł danych | 11 |
| Chunków w DB | 96,678 |
| Eventów wyekstrahowanych | 92,737 |
| Encji wyekstrahowanych | 35,467 |
| Self-rules z audio | 529 |

---

## Technologie zastosowane

| Warstwa | Technologia |
|---------|------------|
| Backend | Python 3.12, FastAPI |
| Baza danych | PostgreSQL 16 (Docker) |
| Vector store | Qdrant (Docker) |
| LLM | Claude Sonnet 4.6, Claude Haiku 4.5 (Anthropic API) |
| Embeddings | OpenAI text-embedding-3-small |
| STT | Whisper (local, model: small) |
| TTS | edge-tts (Microsoft, pluggable) |
| Ingestion | Graph API (email, Teams, calendar), OpenClaw (WhatsApp), Plaud API |
| Delivery | WhatsApp (OpenClaw), Teams Bot, HTTP API |
| MCP | Model Context Protocol (Claude Code integration) |

---

## Dowody prac B+R

### Automatyczne
1. **Git history:** `git log --since=2026-03-20 --stat` — 83 commitów z pełnym diffem
2. **Dev logi:** `logs/dev_log_*.md` — 4 szczegółowe logi sesji
3. **Session summaries:** `memory/session_*.md` — 5 podsumowań sesji
4. **JSONL:** `logs/claude_code_sessions.jsonl` — maszynowo parsowalne logi
5. **API cost tracking:** tabela `api_costs` w DB — każde wywołanie LLM logowane

### Do uzupełnienia
- [ ] Ewidencja czasu pracy (godziny per sesja)
- [ ] Faktury za API (Anthropic, OpenAI)
- [ ] Umowa licencyjna na IP (REH/REF ← Sebastian)
- [ ] Zgłoszenie IP Box do US

---

## Kwalifikacja IP Box

### Art. 24d ust. 2 ustawy o PIT
Kwalifikowane IP: **autorskie prawo do programu komputerowego** (Gilbertus Albans + Omnius)

### Nexus (wskaźnik kwalifikowany)
- **a)** Wydatki na działalność B+R bezpośrednio: czas pracy Sebastiana (~50h), koszty API (~$XX)
- **b)** Nabycie wyników B+R od podmiotów niepowiązanych: brak
- **c)** Nabycie wyników B+R od podmiotów powiązanych: brak
- **d)** Nabycie kwalifikowanego IP: brak

Nexus = (a + b) × 1.3 / (a + b + c + d) = **1.3** (maksymalny)

### Preferencyjna stawka
**5% PIT** od dochodu z kwalifikowanego IP (zamiast standardowego 19% lub 32%)
