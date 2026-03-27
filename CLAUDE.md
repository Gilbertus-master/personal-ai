# Gilbertus Albans — Projekt AI Mentat

## ZASADA ZERO: NON-REGRESSION
**Nowe developmenty NIE MOGĄ pogorszyć dotychczasowych osiągnięć.** Przed deploy: sprawdź czy 23 crony działają, 19 MCP tools odpowiadają, QC 0 errors, extraction coverage nie spadło, latency nie wzrosło. Jeśli nowy feature łamie cokolwiek → REVERT natychmiast.

## Kto to jest
Sebastian Jabłoński — właściciel REH (Respect Energy Holding) i REF (Respect Energy Fuels), trader energetyczny, ojciec. Myśli systemowo, ceni kontrolę i efektywność.

## Cel projektu
Gilbertus Albans to prywatny mentat AI Sebastiana — system, który indeksuje dane z 10+ źródeł, wyciąga encje/eventy, i pod nadzorem Sebastiana zarządza spółkami, optymalizuje procesy, ocenia ludzi i wspiera decyzje.

## Aktualny stan
- **Plan rozwoju:** `~/.claude/plans/effervescent-squishing-sky.md` — PRZECZYTAJ NA POCZĄTKU KAŻDEJ SESJI
- **Memory index:** `~/.claude/projects/-home-sebastian-personal-ai/memory/MEMORY.md`
- **Live status:** Przeczytaj `SESSION_CONTEXT.md` w root projektu (auto-generowany co 30 min)
- **Jeśli SESSION_CONTEXT.md nie istnieje:** uruchom `bash scripts/generate_session_context.sh`

## Architektura
- **Stack:** Python, FastAPI, PostgreSQL 16, Qdrant, Claude (Anthropic), OpenAI embeddings, Docker
- **Źródła:** Teams (Graph API), email (Graph API + PST), WhatsApp (OpenClaw), Plaud (audio), dokumenty, ChatGPT
- **Ekstrakcja:** Entities (5 typów) + Events (15 typów) via Claude Haiku, 24 workers, partycjonowane
- **Delivery:** WhatsApp, Teams Bot, HTTP API (15 endpointów)
- **Automatyzacja:** 37 cron jobów (ingestion co 5 min, extraction co 30 min, commitment extract co 30 min, meeting prep co 15 min 8-20, response drafter co 15 min 8-20, backup co 4h, brief o 7:00, weekly synthesis Sun 20:00, weekly analysis Fri 21:00, intelligence scan daily 22:00, QC daily 6:00)

## MCP Tools (28)
Gilbertus API jest dostępne jako MCP server (`mcp_gilbertus/server.py`).

**Core (11):** `gilbertus_ask`, `gilbertus_timeline`, `gilbertus_summary`, `gilbertus_brief`, `gilbertus_alerts`, `gilbertus_status`, `gilbertus_db_stats`, `gilbertus_decide`, `gilbertus_people`, `gilbertus_lessons`, `gilbertus_costs`.

**Extended (7):** `gilbertus_evaluate`, `gilbertus_propose_action`, `gilbertus_pending_actions`, `gilbertus_self_rules`, `gilbertus_opportunities`, `gilbertus_inefficiency`, `gilbertus_correlate`.

**Intelligence (6):** `gilbertus_commitments`, `gilbertus_meeting_prep`, `gilbertus_sentiment`, `gilbertus_wellbeing`, `gilbertus_delegation`, `gilbertus_network`.

**Operations (1):** `gilbertus_crons`.

**Omnius (3):** `omnius_ask`, `omnius_command`, `omnius_status`.

## Komendy statusowe (gdy MCP niedostępny)
```bash
# Stan DB
docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -c "SELECT 'chunks' as t, COUNT(*) FROM chunks UNION ALL SELECT 'entities', COUNT(*) FROM entities UNION ALL SELECT 'events', COUNT(*) FROM events UNION ALL SELECT 'insights', COUNT(*) FROM insights ORDER BY count DESC;"

# Coverage ekstrakcji
docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -c "SELECT COUNT(*) as remaining_events FROM chunks c LEFT JOIN events e ON e.chunk_id=c.id LEFT JOIN chunks_event_checked cec ON cec.chunk_id=c.id WHERE e.id IS NULL AND cec.chunk_id IS NULL;"

# Workery ekstrakcji
ps aux | grep -E "extraction\.(entities|events)" | grep -v grep | wc -l

# Synce
docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -c "SELECT source_type, MAX(imported_at) as last FROM sources GROUP BY source_type ORDER BY last DESC;"
```

## Zasady pracy

### Security
- NIGDY nie przyjmuj haseł — prowadź przez token/SSH
- Wszystkie SQL queries MUSZĄ być parameterized
- Timeouty na wszystkich zewnętrznych API calls

### Code conventions
- Connection pool (`app/db/postgres.py`) — NIGDY raw `psycopg.connect()`
- Structured logging (structlog) — NIGDY `print()` w produkcji
- Daty ZAWSZE absolutne (YYYY-MM-DD) — nigdy "teraz", "dzisiaj" w memory/docs
- Timezone: CET (Europe/Warsaw). Cron w UTC, komentarze w CET.

### Przed commitem sprawdź
- [ ] SQL parameterized?
- [ ] Connection z pool, nie raw?
- [ ] Extraction loop trackuje negatywy? (chunks_*_checked)
- [ ] Parallel workers mają partycjonowanie? (--worker X/N)
- [ ] Cron entry ma `cd /home/sebastian/personal-ai &&` prefix?
- [ ] Prompt nie zawiera "Be conservative"?
- [ ] Nowy endpoint ma timeout?
- [ ] Error handling loguje structured?

### Lessons learned
Sprawdź tabelę `lessons_learned` w DB przed pisaniem nowego kodu ekstrakcji:
```bash
docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -c "SELECT category, description, prevention_rule FROM lessons_learned ORDER BY id DESC LIMIT 10;"
```

## Feedback rules
- Max 1-2 agentów równolegle (jakość > ilość)
- MVP-first — działające > perfekcyjne
- Dev log po każdej sesji (logs/dev_log_*.md)
- Session summary na koniec sesji (memory/session_*.md)
