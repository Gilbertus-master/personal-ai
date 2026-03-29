# Dev Log — 2026-03-26 (~14h sesja)

## Kontekst
Sesja rozwojowa Gilbertus Albans. Start: ~09:00 CET, koniec: ~23:10 CET.
5 commitów, 95 plików zmienionych, +8718 / -474 linii.

## Commity
1. `3740def` — Faza 0: Connection pool, extraction fix, dedup, Teams grouping, taxonomy
2. `6a9c6bc` — Faza B+C: Omnius, communication, intelligence, compliance, self-improving
3. `68daeaf` — Scripts: QC agents, architecture review, Plaud fix, migration, reports
4. `46375c6` — Session cleanup: migration bundle, state files, remaining changes
5. `f105f8b` — Fix Teams sync: /users/{id}/ → /me/ for delegated permissions

## Co zrobiono

### Faza 0: Stabilizacja + Pamięć + MCP (19/19 tasków)
- Connection pooling (psycopg_pool) — koniec raw psycopg.connect()
- Teams grouping: 18k→16.8k docs (wiadomości per chat per 4h okno)
- Entity dedup + pg_trgm fuzzy upsert: 1.5k duplikatów usunięte
- Bridge people↔entities: 17 znanych osób z aliasami
- Event taxonomy: +7 typów (z 8 do 15)
- Chunk dedup: 29.9k duplikatów usunięte (md5 hash)
- Prompt caching (cache_control: ephemeral na system prompts)
- CLAUDE.md + SESSION_CONTEXT.md + auto-cron co 30 min
- Session handoff hook (on Stop)
- Lessons learned tabela: 11→18 reguł
- Feedback memories fix
- Timezone: TZ=Europe/Warsaw
- Pre-commit hooks: ruff + custom (SQL parameterization, raw connect check)
- Prompt versioning tabela
- API cost tracking (10 callerów: ask, brief, timeline, alerts, extraction_events, extraction_entities, evaluation, correlation, opportunity, morning_brief)
- Graceful worker shutdown (SIGTERM handler)
- Extraction rollback (extraction_runs tabela z commit/rollback)
- MCP server: 18 toolów na `mcp` SDK

### Faza 1: Proaktywna Inteligencja (6/6)
- Calendar sync via Graph API (36+ events)
- Morning brief: 5 sekcji (kalendarz + relacje + open loops per spotkanie)
- Person-aware retrieval (alias expansion dla 17 osób)
- Extraction 100% coverage (Haiku, 24 workerów, ~400 events/min)
- Decision journal via WhatsApp (decision:/decyzja:)
- Cross-domain correlation MVP (temporal Pearson + person profile + anomaly detection)

### Fazy 2-5: Kod napisany, deploy pending
- Evaluation pipeline (data_collector + evaluator + POST /evaluate + MCP)
- Answer cache (1h TTL, 48s→0ms na powtórkach)
- Quarterly eval cron
- Omnius codebase (REH+REF provisioned)
- Command protocol (READ+WRITE+ADMIN)
- Action pipeline (propose→approve→execute)
- Communication orchestrator (standing orders, auto-draft, daily digest)
- Self-improving rules engine
- Opportunity detector (co 2h scan)
- Compliance manager AI
- Weekly reports + decision reminders (7/30/90d)

### QC Agents
- Code quality: daily 6:00, 12 checks + non-regression baseline
- Architecture review: weekly Sun 22:00, 10 checks
- Inventory: auto-generated co 30 min (SESSION_CONTEXT.md)

### Fixy
- Worker overflow: 49→24 (guard w turbo_extract.sh)
- Dead code: task_monitor cleanup
- Raw psycopg.connect: 2 pliki naprawione
- Circular dependency: InterpretedQuery → app/models/
- Ruff: 156→0 errors
- Qdrant drift: 144k→91k (stale vectors cleanup)
- Plaud: ori_ready bug — pole nieudokumentowane, ignorowało 40 nagrań. Fix: sprawdzaj actual DB state
- Teams sync: /users/{id}/ → /me/ dla delegated permissions (400 error na wszystkich chatach)

### Generacja dokumentów
- Cele_2025_Ocena_SJ.docx — oceny 4 pracowników (Kulpa 3.8, Kalinowska 3.1, Mruk 4.0, Morska 4.5)
- Gilbertus_Omnius_Plan_Q2Q3_2026.docx — masterplan 5 faz
- Omnius_REH_Plan_dla_Rocha.docx
- Omnius_REF_Plan_dla_Krystiana.docx
- Bug report PDF (PL+EN) dla Plaud team

### Plan rozwoju
- Przejście z 6-fazowego planu na 5-fazowy ROI-driven (A-E)
- Plan zapisany: ~/.claude/plans/effervescent-squishing-sky.md

## Decyzje
- Haiku jako model ekstrakcji (Sonnet 3.3x droższy/wolniejszy)
- Omnius V1: tylko shared docs, nie dane pracownicze (compliance)
- 5 faz A-E zamiast 6 faz (ROI-driven reorganizacja)
- Extraction: 24 workerów (12 events + 12 entities), partycjonowane

## Niedokończone
- Migracja Hetzner: kod+DB uploaded, brakuje .env, nginx, certbot, cron
- Entity extraction: ~10k remaining (89% → cron dobierze)
- Embedding: 359 pending (cron dobierze)

## Rate limiting
- Hit 4M token/min limit na Haiku (429 errors) — workery czekają i retry
