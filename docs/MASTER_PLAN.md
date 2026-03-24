# Gilbertus Albans — Master Plan & Task Map

## Legenda
- 🔴 BLOCKER — blokuje inne zadania
- 🟠 HIGH — wysoka wartość
- 🟢 MEDIUM — średnia wartość
- ⚪ LOW — niska wartość / nice-to-have
- ✅ DONE
- 🔄 IN PROGRESS
- ⏳ WAITING (dependency)
- 📋 TODO

## Stream 1: DATA COMPLETENESS (Agent: DataOps)
Cel: Gilbertus wie WSZYSTKO co się dzieje w życiu Sebastiana.

| ID | Task | Priority | Status | Depends | Parallelizable |
|----|------|----------|--------|---------|----------------|
| D1 | WhatsApp live scraper (bieżące rozmowy) | 🔴 | 🔄 | - | ✅ |
| D2 | Azure Graph API auth + email sync | 🔴 | 🔄 | IT done | ✅ |
| D3 | Azure Teams chat sync | 🟠 | ⏳ | D2 | po D2 |
| D4 | Plaud auto-upload fix (telefon → cloud) | 🟠 | 📋 | - | ✅ |
| D5 | Plaud auto-transcription (trigger via API) | 🟠 | 🔄 | D4 | po D4 |
| D6 | ChatGPT periodic export auto-import | 🟢 | ✅ | - | - |
| D7 | Claude Code session auto-import | 🟢 | ✅ | - | - |
| D8 | Kalendarz sync (Google/Outlook) | 🟢 | 📋 | D2 | po D2 |
| D9 | Re-export WhatsApp (aktualizacja do marca 2026) | 🟠 | 📋 | - | ✅ |
| D10 | Notatki Obsidian/txt filesystem watcher | ⚪ | 📋 | - | ✅ |

## Stream 2: DATA QUALITY (Agent: QualityOps)
Cel: dane w bazie są czyste, kompletne, poprawnie zaindeksowane.

| ID | Task | Priority | Status | Depends | Parallelizable |
|----|------|----------|--------|---------|----------------|
| Q1 | Audyt jakości danych (coverage, gaps, duplicates) | 🔴 | 🔄 | - | ✅ |
| Q2 | Fix embedding gaps (jeśli są) | 🟠 | ⏳ | Q1 | po Q1 |
| Q3 | Fix chunk outliers (za duże/za małe) | 🟢 | ⏳ | Q1 | po Q1 |
| Q4 | Ekstrakcja encji — pokrycie do 20%+ | 🟠 | 🔄 | - | ✅ |
| Q5 | Ekstrakcja eventów — Tier 2 completion | 🟠 | 🔄 | - | ✅ |
| Q6 | Duplicate document detection + cleanup | 🟢 | ⏳ | Q1 | po Q1 |
| Q7 | Answer quality benchmark (10 pytań testowych) | 🟠 | 📋 | - | ✅ |

## Stream 3: USABILITY (Agent: ProductOps)
Cel: Gilbertus jest UŻYWALNY na co dzień przez Sebastiana.

| ID | Task | Priority | Status | Depends | Parallelizable |
|----|------|----------|--------|---------|----------------|
| U1 | WhatsApp interface (Gilbertus na self-chat) | 🔴 | ✅ | - | - |
| U2 | Multi-chat WhatsApp (równoległe rozmowy) | 🟠 | 📋 | U1 | ✅ |
| U3 | Morning brief generator (cron 7:00) | 🟠 | 📋 | D2, D8 | ✅ |
| U4 | Decision journal (log + track outcomes) | 🟠 | 📋 | - | ✅ |
| U5 | Quick commands na WhatsApp (/timeline, /summary, /search) | 🟢 | 📋 | U1 | ✅ |
| U6 | Proaktywne alerty (pattern detection) | 🟢 | 📋 | Q4, Q5 | po Q4 |
| U7 | Answer quality feedback loop (thumbs up/down) | 🟢 | 📋 | U1 | ✅ |

## Stream 4: OMNIUS (Agent: OmniusOps)
Cel: Roch i Krystian mają działającego asystenta w swoich spółkach.

| ID | Task | Priority | Status | Depends | Parallelizable |
|----|------|----------|--------|---------|----------------|
| O1 | Omnius MVP deploy (Docker, API, auth) | 🔴 | ✅ (repo) | - | - |
| O2 | Omnius REH — setup + dane Rocha | 🔴 | 📋 | O1 | ✅ |
| O3 | Omnius REF — setup + dane Krystiana | 🔴 | 📋 | O1 | ✅ |
| O4 | Import danych firmowych REH (email/Teams/docs) | 🟠 | ⏳ | O2 | po O2 |
| O5 | Import danych firmowych REF | 🟠 | ⏳ | O3 | po O3 |
| O6 | RBAC (role-based access per user) | 🟢 | 📋 | O2 | ✅ |
| O7 | Plaud Pin S dla Rocha/Krystiana | 🟢 | 📋 | O2, O3 | po O2 |

## Stream 5: INFRASTRUCTURE (Agent: InfraOps)
Cel: system jest stabilny, szybki, tani, bezpieczny.

| ID | Task | Priority | Status | Depends | Parallelizable |
|----|------|----------|--------|---------|----------------|
| I1 | Dedykowany serwer (wybór, zamówienie) | 🟠 | 📋 | - | ✅ |
| I2 | Migracja z laptopa na serwer | 🟠 | ⏳ | I1 | po I1 |
| I3 | Self-hosted LLM (Whisper done, next: embeddings) | 🟢 | 📋 | I1 | po I1 |
| I4 | Monitoring + alerting (uptime, API health) | 🟢 | 📋 | - | ✅ |
| I5 | Cost tracking (API usage per endpoint) | 🟢 | 📋 | - | ✅ |
| I6 | Szyfrowanie at rest (LUKS) | 🟢 | ⏳ | I1 | po I1 |

## Stream 6: ARCHITECTURE (Agent: Architect)
Cel: strategiczne myślenie o kierunku rozwoju.

| ID | Task | Priority | Status | Depends | Parallelizable |
|----|------|----------|--------|---------|----------------|
| A1 | Architektura real-time audio pipeline | 🟠 | 📋 | I1 | ✅ |
| A2 | Gilbertus ↔ Omnius command protocol | 🟢 | 📋 | O2, O3 | ✅ |
| A3 | Cross-domain correlation engine design | 🟢 | 📋 | Q4, Q5 | ✅ |
| A4 | V2 → V3 migration plan (firmowe dane) | 🟢 | ⏳ | compliance | ✅ |
| A5 | Self-hosted LLM evaluation (cost vs quality) | 🟢 | ⏳ | I1 | ✅ |

---

## Co można robić TERAZ równolegle (max parallelism)

### Slot 1: D1 — WhatsApp live scraper (agent building)
### Slot 2: D2 — Azure Graph API auth (Sebastian authorizes)
### Slot 3: Q1 — Data quality audit (agent running)
### Slot 4: Q7 — Answer quality benchmark
### Slot 5: U3 — Morning brief generator
### Slot 6: U4 — Decision journal implementation
### Slot 7: O2+O3 — Omnius deploy planning

## Zasady pracy

1. **Zawsze 3-5 agentów w tle** — nigdy nie robimy 1 rzeczy na raz
2. **MVP-first** — najprostsze rozwiązanie które działa, potem iteracja
3. **Value scoring** — HIGH value + LOW effort = robimy PIERWSZY
4. **Test immediately** — Sebastian testuje na WhatsApp po każdej zmianie
5. **No dead-ends** — jeśli coś nie działa po 15 min, pivot do prostszego rozwiązania
6. **Log everything** — każda decyzja do memory, każdy dead-end do logs
