# Gilbertus & Omnius — Technical Architecture

> **Generated:** 2026-03-31 | **Live metrics snapshot included**
> **Target audience:** Senior engineer joining the project

---

## 1. Executive Summary

**Gilbertus Albans** is a private AI Mentat for Sebastian Jablonski — owner of REH (Respect Energy Holding) and REF (Respect Energy Fuels). It indexes data from 11+ sources, extracts entities and events, and supports strategic decisions through proactive intelligence, compliance monitoring, and automated analysis.

**Omnius** is a multi-tenant corporate AI agent system controlled by Gilbertus. It provides per-company (REH, REF) AI assistants with RBAC, plugin sandboxing, and governance rules that prevent capability reduction.

### Live Metrics (2026-03-31)

| Metric | Value |
|--------|-------|
| Documents | 37,673 |
| Chunks | 106,613 |
| Entities | 37,830 |
| Events | 97,071 |
| Insights | 126 |
| Code review findings | 1,518 |
| Database tables | 137 (Gilbertus) + ~15 (Omnius) |
| API endpoints | 253 total routes |
| Cron jobs | 62 active |
| Frontend pages | 60 |
| UI components | 159 |
| Python files | 278 (71,723 LOC) |
| TypeScript files | 385 |
| Data sources | 11 types, 98 source records |
| MCP tools | 44+ |

---

## 2. System Architecture

### 2.1 High-Level Overview

```
                                    GILBERTUS ALBANS
    ┌─────────────────────────────────────────────────────────────────────┐
    │                                                                     │
    │  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌───────────────┐   │
    │  │  Sources  │──▶│ Ingestion│──▶│ Chunks   │──▶│  Extraction   │   │
    │  │ (11 types)│   │ Pipeline │   │ (106k)   │   │ Entities/Events│  │
    │  └──────────┘   └──────────┘   └──────────┘   └───────┬───────┘   │
    │                                                         │           │
    │                                                         ▼           │
    │  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌───────────────┐   │
    │  │ Delivery  │◀──│ Retrieval│◀──│  Qdrant  │◀──│  PostgreSQL   │   │
    │  │ WhatsApp  │   │ Engine   │   │ Vectors  │   │  137 tables   │   │
    │  │ Teams Bot │   │ (Hybrid) │   └──────────┘   └───────────────┘   │
    │  │ HTTP API  │   └──────────┘                                       │
    │  └──────────┘                                                       │
    │                                                                     │
    │  ┌─────────────────────────────────────────────────────────────┐   │
    │  │                    Analysis Layer (48+ modules)              │   │
    │  │  Intelligence | Compliance | Market | Process | Self-Healing │   │
    │  └─────────────────────────────────────────────────────────────┘   │
    │                                                                     │
    │  ┌─────────────────────────────────────────────────────────────┐   │
    │  │                  Automation (62 cron jobs)                    │   │
    │  │  Ingestion | Extraction | Analysis | Backup | Self-Repair    │   │
    │  └─────────────────────────────────────────────────────────────┘   │
    │                                                                     │
    └─────────────────────────────────────────────────────────────────────┘
                    │                              │
                    ▼                              ▼
    ┌──────────────────────┐       ┌──────────────────────────┐
    │   MCP Server (44+)   │       │   Frontend (Next.js 16)  │
    │   Claude Desktop /   │       │   60 pages, 159 comps    │
    │   Claude Code        │       │   RBAC, i18n, dark mode  │
    └──────────────────────┘       └──────────────────────────┘
                                                │
                    ┌───────────────────────────┘
                    ▼
    ┌──────────────────────────────────────────────────────────┐
    │                    OMNIUS (Multi-Tenant)                  │
    │  ┌─────────┐  ┌─────────┐  ┌──────────┐  ┌──────────┐  │
    │  │  REH    │  │  REF    │  │ Plugins  │  │ Sandbox  │  │
    │  │ (Roch)  │  │(Krystian)│  │ SDK+Gov  │  │ (Docker) │  │
    │  └─────────┘  └─────────┘  └──────────┘  └──────────┘  │
    └──────────────────────────────────────────────────────────┘
```

### 2.2 Data Flow

```
Sources → Ingestion → Documents → Chunks → Extraction → Entities + Events
                                     │                         │
                                     ▼                         ▼
                                  Qdrant                  PostgreSQL
                                (embeddings)             (structured)
                                     │                         │
                                     └────────┬────────────────┘
                                              ▼
                                     Retrieval Engine
                                    (BM25 + Vector RRF)
                                              │
                                              ▼
                                    LLM Answer Generation
                                              │
                              ┌───────────────┼───────────────┐
                              ▼               ▼               ▼
                          WhatsApp        HTTP API        Teams Bot
```

---

## 3. Technology Stack

### 3.1 Backend

| Component | Technology | Details |
|-----------|-----------|---------|
| Language | Python 3.11+ | 278 files, 71,723 LOC |
| Web framework | FastAPI | 253 routes, slowapi rate limiting |
| Database | PostgreSQL 16 | 137 tables, psycopg + connection pool |
| Vector store | Qdrant | OpenAI embeddings (text-embedding-3-small) |
| AI (extraction) | Claude Haiku 4.5 | Entity/event extraction, 24 workers |
| AI (analysis) | Claude Sonnet 4.6 | Answering, briefs, analysis |
| AI (complex) | Claude Opus | Deep analysis, scenario planning |
| AI (embeddings) | OpenAI | text-embedding-3-small |
| Logging | structlog | Structured JSON logging throughout |
| Resilience | Custom decorators | Retry with exponential backoff, circuit breaker |

### 3.2 Frontend

| Component | Technology | Details |
|-----------|-----------|---------|
| Framework | Next.js 16 | App Router, 60 pages |
| UI | React 19 | 159 components |
| Language | TypeScript 5.7 | Strict mode |
| Styling | Tailwind CSS | Dark mode forced |
| Server state | TanStack React Query 5 | 60s staleTime |
| Client state | Zustand 5 | 12 stores with persistence |
| Auth | NextAuth 5 (beta) | API key + Azure AD planned |
| Icons | Lucide React | 460+ icons |
| i18n | next-intl 4 | Polish/English |
| Terminal | xterm.js 5 | Admin terminal emulation |
| Monorepo | pnpm workspaces | 5 packages |

### 3.3 Infrastructure

| Component | Technology |
|-----------|-----------|
| Runtime | WSL2 (Linux 6.6) |
| Containers | Docker (PostgreSQL, Qdrant) |
| Automation | cron (62 jobs) |
| Deployment | Local dev → Hetzner VPS (planned) |
| MCP | Claude Desktop / Claude Code integration |

### 3.4 AI Model Usage

| Use Case | Model | Timeout |
|----------|-------|---------|
| Entity extraction | claude-haiku-4-5 | 60s |
| Event extraction | claude-haiku-4-5 | 60s |
| Commitment extraction | claude-haiku-4-5 | 60s |
| Q&A answering | claude-sonnet-4-6 | 60s |
| Morning brief | claude-sonnet-4-5 | 120s |
| Code autofixer (Tier 2) | claude-sonnet-4-6 | varies |
| Governance validation | claude-haiku-4-5 | 30s |
| Deep analysis | claude-opus | 180s |
| Embeddings | text-embedding-3-small (OpenAI) | 30s |

---

## 4. Data Layer

### 4.1 PostgreSQL Schema

**Core Tables (from `001_init_metadata.sql`):**

```sql
-- Source tracking
CREATE TABLE sources (
    id SERIAL PRIMARY KEY,
    source_type TEXT NOT NULL,    -- whatsapp, email, teams, audio_transcript, etc.
    source_name TEXT NOT NULL,
    imported_at TIMESTAMPTZ DEFAULT NOW()
);

-- Document metadata
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    source_id INT REFERENCES sources(id),
    title TEXT,
    created_at TIMESTAMPTZ,
    author TEXT,
    participants JSONB,
    raw_path TEXT
);

-- Text chunks (unit of retrieval)
CREATE TABLE chunks (
    id SERIAL PRIMARY KEY,
    document_id INT REFERENCES documents(id),
    chunk_index INT,
    text TEXT,
    timestamp_start TIMESTAMPTZ,
    timestamp_end TIMESTAMPTZ,
    embedding_id TEXT,
    UNIQUE(document_id, chunk_index)
);

-- Extracted entities (person, company, project, topic, location)
CREATE TABLE entities (
    id SERIAL PRIMARY KEY,
    name TEXT,
    entity_type TEXT,
    UNIQUE(name, entity_type)
);

-- Extracted events (15 types)
CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    document_id INT REFERENCES documents(id),
    event_type TEXT,
    event_time TIMESTAMPTZ,
    summary TEXT
);

-- Periodic summaries
CREATE TABLE summaries (
    id SERIAL PRIMARY KEY,
    summary_type TEXT,
    period_start DATE,
    period_end DATE,
    text TEXT
);
```

**Table Categories (137 total):**

| Category | Tables | Examples |
|----------|--------|---------|
| Core data | 8 | sources, documents, chunks, entities, events, chunk_entities, event_entities, summaries |
| Extraction tracking | 6 | extraction_runs, chunks_entity_checked, chunks_event_checked, chunks_commitment_checked, event_candidate_chunks, event_entity_backfill_candidates |
| Intelligence | 12 | commitments, decisions, decision_outcomes, decision_context, alerts, predictions, opportunities, scenarios, scenario_outcomes, insights, strategic_goals, goal_progress |
| People & relationships | 14 | people, contacts, relationships, relationship_roles_history, rel_events, rel_journal, rel_metrics, rel_partners, rel_patterns, relationship_open_loops, relationship_timeline, sentiment_scores, wellbeing_scores, communication_edges |
| Compliance & legal | 14 | compliance_areas, compliance_matters, compliance_obligations, compliance_deadlines, compliance_documents, compliance_trainings, compliance_training_records, compliance_risks, compliance_raci, compliance_audit_evidence, compliance_communications, compliance_risk_assessments, contracts |
| Market & competitors | 6 | market_items, market_sources, market_alerts, market_insights, competitors, competitor_signals, competitor_analysis |
| Process intelligence | 8 | discovered_processes, data_flows, app_inventory, app_cost_history, business_lines, business_line_signals, tech_dependencies, tech_roadmap_snapshots, tech_solutions |
| Finance | 5 | financial_metrics, financial_alerts, budget_items, cost_budgets, cost_alert_log |
| Code quality | 2 | code_review_findings, code_review_files |
| System | 15 | api_costs, answer_cache, answer_evaluations, cron_registry, cron_user_assignments, health_checks, ingestion_dlq, perf_improvement_journal, prompt_versions, sessions, user_activity_log, voice_conversations, calibration_settings, self_rules, lessons_learned |
| ROI & delegation | 8 | roi_activities, roi_hierarchy, roi_summaries, delegation_tasks, authority_levels, authority_log, standing_orders, standing_order_metrics |
| Other | ~20 | action_items, action_outcomes, engagement_metrics, guardian_alerts, ingestion_health, lineage, optimization_plans, org_health_scores, response_drafts, response_feedback, rule_applications, sent_communications, wa_tasks, etc. |

### 4.2 Qdrant Vector Store

- **Collection:** `gilbertus` (main), `omnius_*` per-tenant
- **Embedding model:** OpenAI `text-embedding-3-small` (1536 dimensions)
- **Search strategy:** Hybrid — BM25 full-text + cosine vector similarity with Reciprocal Rank Fusion (RRF)
- **Payload:** chunk_id, document_id, source_type, created_at, author
- **Embedding ID stored in:** `chunks.embedding_id`

### 4.3 Data Sources

| Source Type | Documents | Ingestion Method |
|------------|-----------|-----------------|
| whatsapp | 64 | OpenClaw CLI + live WhatsApp pipeline |
| chatgpt | 13 | ChatGPT export parser |
| email | 5 | Microsoft Graph API + PST import |
| audio_transcript | 3 | Plaud device → Whisper transcription |
| document | 3 | File import (PDF, DOCX) |
| claude_code_full | 2 | Claude Code session archive |
| spreadsheet | 2 | Excel/CSV parser |
| teams | 2 | Microsoft Graph API sync |
| whatsapp_live | 2 | Real-time WhatsApp monitoring |
| email_attachment | 1 | Graph API attachment download |
| calendar | 1 | Microsoft Graph API calendar sync |

---

## 5. Backend Architecture

### 5.1 API Layer (FastAPI)

**File:** `app/api/main.py`

**Setup:**
- FastAPI with environment-driven config (`APP_NAME`, `APP_VERSION`, `APP_ENV`)
- CORS: origins from `CORS_ALLOWED_ORIGINS` env (default: `*`), methods: GET/POST/DELETE, max_age: 3600s
- Rate limiting via slowapi with trusted IP bypass (127.0.0.1, localhost, ::1)
- API Key middleware from `app.api.auth`
- Feature flag caching on startup

**Endpoint Categories (253 total routes):**

| Category | Count | Key Paths |
|----------|-------|-----------|
| Compliance & Legal | 42 | `/compliance/*` (dashboard, matters, obligations, deadlines, risks, documents, trainings, RACI, reports, scan) |
| Process Intelligence | 38 | `/process-intel/*` (dashboard, business-lines, apps, flows, tech-radar, workforce, automation) |
| Core Q&A & Intelligence | 27 | `/ask`, `/brief/today`, `/alerts`, `/timeline`, `/summary/*`, `/commitments`, `/meeting-prep`, `/sentiment/*`, `/wellbeing` |
| People & Relationships | 14 | `/people`, `/people/{slug}`, `/network`, `/delegation/*`, `/evaluate`, `/scorecard/*` |
| Market & Competitors | 10 | `/market/*`, `/competitors/*` |
| Calendar & Goals | 10 | `/calendar/*`, `/goals/*` |
| Decisions & Scenarios | 10 | `/decision*`, `/scenarios/*` |
| Finance & ROI | 10 | `/finance/*`, `/costs/*`, `/roi/*` |
| Admin & System | 15 | `/status`, `/health`, `/crons/*`, `/admin/*`, `/authority/*` |
| Communication | 8 | `/response-*`, `/channel-effectiveness`, `/standing-order-effectiveness` |
| Voice | 6 | `/voice/*` (transcribe, ask, command, tts, health, websocket) |
| Observability | 4 | `/observability/*` (dashboard, alert-check, trace, graph) |
| Other | 12 | `/plaud`, `/presentation/*`, `/insights/*`, `/feedback/*`, `/errors/*`, `/updates/*` |

**Included Routers:**
plaud, decisions, insights, presentation, relationships, teams, voice, voice_ws, observability, updates, roi, feedback, strategic_radar, activity, alerts (resolution + guardian), errors

### 5.2 Retrieval Engine

**File:** `app/retrieval/answering.py`

**Pipeline:**
1. **Query interpretation** — Classify intent, extract time range, identify entities
2. **Hybrid search** — BM25 full-text (PostgreSQL) + vector similarity (Qdrant) with RRF fusion
3. **Context assembly** — Top-k chunks, max 1200 chars each (`CHUNK_TEXT_LIMIT`)
4. **Answer generation** — Claude Sonnet with structured system prompt

**LLM Configuration:**
- Primary model: `claude-sonnet-4-6` (env: `ANTHROPIC_MODEL`)
- Fast model: `claude-haiku-4-5` (env: `ANTHROPIC_FAST_MODEL`)
- Fallback model: `claude-haiku-4-5` (env: `ANTHROPIC_FALLBACK_MODEL`)
- Timeout: 60s, retries: 2, retry delay: 3s

**Operational Modes:**
- `direct_answer` — Concise answer
- `chronology` — Timeline of events
- `synthesis` — Multi-source synthesis
- `analysis` — Deep analytical response
- `deep_analysis` — Comprehensive cross-domain analysis

**Response Lengths:** short, medium, long

**System prompt:** Polish language, cacheable (static), instructs to rely solely on provided context.

### 5.3 Extraction Pipeline

**Entities** (`app/extraction/entities.py`):
- 5 types: `person`, `company`, `project`, `topic`, `location`
- Max 4 entities per chunk
- LLM: Claude Haiku with strict anti-hallucination rules
- Batch size: 50 chunks, 24 workers (partitioned by `--worker X/N`)
- Negative tracking via `chunks_entity_checked` table
- Graceful shutdown on SIGTERM/SIGINT

**Events** (`app/extraction/events.py`):
- 15 types: `conflict`, `support`, `decision`, `meeting`, `trade`, `health`, `family`, `milestone`, `deadline`, `commitment`, `escalation`, `blocker`, `task_assignment`, `approval`, `rejection`
- 1 event per chunk maximum
- Confidence score: 0.0–1.0
- Negative tracking via `chunks_event_checked` table
- Batch size: 50, partitioned workers

**Commitments** (separate pipeline):
- Extracted every 2 hours (200 chunks, 2 workers)
- Status tracking: open, overdue, fulfilled, broken
- Checked via `chunks_commitment_checked` table

**Turbo Extraction:**
- Batch script: `scripts/turbo_extract.sh`
- 3000 chunks per run, 12 workers, Claude Haiku
- Runs every 30 minutes

### 5.4 Analysis Modules

**48+ modules in `app/analysis/`:**

| Module | Description |
|--------|-------------|
| `action_outcome_tracker` | Tracks action outcomes at 24h/72h/7d intervals for feedback loop closure |
| `app_inventory` | Discovers applications, platforms, file formats with cost/TCO/replacement analysis |
| `blind_spot_detector` | Detects knowledge gaps: unknown persons, undocumented projects, source/topic gaps |
| `business_lines` | Auto-detects business lines from data patterns without hardcoded definitions |
| `channel_effectiveness` | Analyzes which channel (email/Teams/WhatsApp) works best per person |
| `commitment_tracker` | Monitors commitment status, detects overdue items, per-person statistics |
| `competitor_intelligence` | Monitors competitors via KRS, media, archives; SWOT and competitive landscape |
| `compliance_manager` | Analyzes employee communication style, culture fit, responsiveness |
| `contact_resolver` | Cross-source identity linking (WhatsApp JIDs, emails, Teams UPNs → unified contacts) |
| `contract_tracker` | Extracts contracts from documents, tracks expiry, sends pre-deadline alerts |
| `correlation` | Finds temporal and entity-level patterns (e.g., conflict-to-trade correlations) |
| `cost_estimator` | Estimates financial impact: direct cost, opportunity cost, ROI, payback period |
| `data_flow_mapper` | Maps info flows: who sends what to whom via which channel, bottleneck detection |
| `data_quality_calibrator` | Auto-fixes missing timestamps, orphan docs, stale sources, duplicates |
| `decision_enrichment` | Auto-enriches decisions with market context, competitor signals, goal alignment |
| `decision_intelligence` | Learns from decision patterns, calibrates confidence, detects bias |
| `decision_outcome_detector` | Auto-detects outcomes for pending decisions using evidence gathering + LLM |
| `delegation_tracker` | Task completion rate per person from commitment data with ranking |
| `employee_automation` | Maps work activities, assesses automation potential, calculates savings per role |
| `feedback_calibration` | Self-adjusts relevance thresholds based on which briefs Sebastian reads/ignores |
| `feedback_persistence` | Stores answer evaluations, identifies weak areas with consistently low quality |
| `financial_framework` | KPI input, budget tracking, API cost summaries, daily alerts, monthly reports |
| `health_monitor` | Checks cron execution, extraction coverage, API costs, DB baseline, service health |
| `inefficiency` | Detects repeating tasks, communication bottlenecks, decision delays, meeting overload |
| `ingestion_health_monitor` | Alerts when data sources go stale (configurable thresholds per source type) |
| `legal_compliance` | Legal obligations, compliance docs, deadlines, training across 9 compliance areas |
| `llm_evaluator` | Evaluates self-hosted LLM candidates on Gilbertus tasks (entity extraction, Polish) |
| `market_intelligence` | Two-layer energy market monitoring: semantic search + RSS (TGE, URE, PSE) |
| `meeting_minutes` | Auto-generates structured meeting notes from audio (participants, decisions, actions) |
| `meeting_prep` | 30 min before meetings: participant scorecards, open topics, discussion points |
| `meeting_roi` | Scores meeting productivity by decisions/actions/commitments created |
| `network_graph` | Communication network graphs, silo detection, bottleneck identification |
| `opportunity_detector` | Scans events every 2h, classifies as optimization/opportunity/risk with PLN value |
| `optimization_planner` | Generates Gilbertus replacement plans per process with ROI-prioritized migration |
| `org_health` | Weekly 1-100 health score from 8 dimensions (delivery, sentiment, communication) |
| `predictive_alerts` | Pattern-based predictions for escalation risk, communication gaps, deadline risk |
| `process_mining` | Discovers recurring processes from communication (decision flows, approval chains) |
| `response_tracker` | Tracks response rates within 24h/72h, measures response time, auto-sends reminders |
| `rule_reinforcement` | Measures rule effectiveness, detects conflicts, flags stale rules |
| `scenario_analyzer` | "What if?" simulations across 5 dimensions (revenue, costs, people, ops, reputation) |
| `sentiment_tracker` | Weekly per-person sentiment of communication tone with trend alerts |
| `speaker_resolver` | Maps speaker labels from transcripts to known people, detects meeting boundaries |
| `standing_order_effectiveness` | Tracks standing order response rates and recommends channel/scope changes |
| `strategic_goals` | Links operations to strategy: progress, KPIs, trends, risks, dependencies |
| `strategic_radar` | Cross-domain situational awareness: market + competitors + goals + commitments |
| `tech_radar` | Technology discovery and quarterly roadmap with dependency mapping |
| `threshold_optimizer` | Auto-tunes alert thresholds and brief ordering from interaction data |
| `wellbeing_monitor` | Tracks Sebastian's wellbeing from communication, work hours, conflicts, family events |

**Legal Submodules** (`app/analysis/legal/`):
- `obligation_tracker` — Monitors deadlines with auto-recurrence and WhatsApp alerts (30/14/7/3/1 day)
- `regulatory_scanner` — Scans ingested data for regulatory changes, auto-creates compliance matters
- `risk_assessor` — 5x5 risk matrix (likelihood x impact), 0-1 score, color-coded severity
- `compliance_reporter` — Weekly/monthly compliance reports
- `document_generator` — Auto-generates compliance documents
- `document_validator` — Validates document completeness
- `training_manager` — Training deadline tracking and reminders
- `communication_planner` — Plans compliance communications

**Relationship Submodules** (`app/analysis/relationship/`):
- `health_scorer` — Gottman-inspired scoring (5:1 positivity ratio, Four Horsemen detection)
- `partner_profile`, `event_tracker`, `pattern_detector`, `wa_analyzer`, `coach`

**ROI Submodules** (`app/analysis/roi/`):
- `roi_reporter` — Persists ROI summaries with synergy calculation
- `activity_tracker`, `hierarchy`, `value_mapper`, `synergy_calculator`

**Performance Improvement** (`app/analysis/perf_improver/`):
- `improvement_agent` — Daily loop: analyze → detect bottleneck → plan fix → apply → verify → commit/revert

### 5.5 Orchestration

**Cron Registry** (`app/orchestrator/cron_registry.py`):
- Database-driven cron management with per-user control
- Tables: `cron_registry` (job definitions) + `cron_user_assignments` (per-user enable/disable)
- Categories: ingestion, extraction, analysis, backup, intelligence, communication
- CLI: `--list`, `--generate [user]`, `--enable/--disable JOB_NAME`, `--seed`

**Action Pipeline** (`app/orchestrator/action_pipeline.py`):
- Human-in-the-loop approval via WhatsApp
- Flow: Alert/Analysis → Propose Action → WhatsApp notification → Sebastian approves/rejects → Execute → Log
- Keywords: `approve #123` / `tak #123`, `reject #123` / `nie #123`, `edit #123: [text]`
- Actions: send_email, create_ticket, schedule_meeting, send_whatsapp, omnius_command

**Resilience** (`app/core/resilience.py`):
- `with_retry()` decorator: exponential backoff + jitter, max 3 attempts, 2-30s wait
- Retryable: 429, 500, 502, 503, 504
- Non-retryable: 401, 403

**Timezone** (`app/config/timezone.py`):
- Single source of truth: `APP_TIMEZONE = ZoneInfo('Europe/Warsaw')`
- Helper functions: `now()`, `today()`, `to_app_tz(dt)`
- All crons in UTC, all comments in CET

---

## 6. Frontend Architecture

### 6.1 Monorepo Structure

```
frontend/
├── apps/
│   └── web/                    # Next.js 16 application
│       ├── app/
│       │   ├── (app)/          # Authenticated routes (60 pages)
│       │   ├── (auth)/         # Login page
│       │   └── layout.tsx      # Root layout (dark mode, Polish, providers)
│       ├── components/
│       │   └── providers.tsx   # Provider stack
│       └── lib/
│           └── stores/         # 12 Zustand stores
├── packages/
│   ├── api-client/             # Typed API client (48+ exports)
│   ├── rbac/                   # Role-based access control
│   ├── ui/                     # Shared UI components (159)
│   └── i18n/                   # Internationalization (PL/EN)
└── package.json                # pnpm workspaces
```

### 6.2 Pages & Modules

| Module | Path | Accessible Roles | Description |
|--------|------|-------------------|-------------|
| Dashboard | `/dashboard` | All | Overview dashboard |
| Poranny Brief | `/brief` | owner, ceo, board | Morning intelligence brief |
| Chat | `/chat`, `/chat/[id]` | All | Conversational AI interface |
| People | `/people`, `/people/[slug]`, `/people/network` | owner, ceo, board, director | Person profiles, network graph |
| Intelligence | `/intelligence` | owner, ceo, board | Cross-domain intelligence |
| Compliance | `/compliance/*` (12 sub-pages) | owner, ceo, board, director | Legal & regulatory compliance |
| Market | `/market/*` (5 sub-pages) | owner, ceo, board, director | Market & competitor intelligence |
| Finance | `/finance/*` (3 sub-pages) | owner, ceo, board | Financial metrics & goals |
| Processes | `/process/*` (5 sub-pages) | owner, ceo, board, director | Process mining, tech radar, workforce |
| Decisions | `/decisions` | owner, ceo | Decision journal & intelligence |
| Calendar | `/calendar` | owner, ceo, board, director, manager | Calendar with meeting prep |
| Documents | `/documents` | owner, ceo, board, director | Document browser |
| Voice | `/voice` | owner, ceo, board | Voice interface (transcribe + TTS) |
| Admin | `/admin/*` (12 sub-pages) | owner, gilbertus_admin, operator | System administration |
| Settings | `/settings` | All | Personal settings |

**Admin Sub-Pages:** status, crons, code-review, autofixers, costs, activity, audit, users, roles, plugins, omnius, terminal

### 6.3 State Management

**Provider Stack** (`components/providers.tsx`):
```
SessionProvider (NextAuth)
  └── QueryClientProvider (TanStack React Query, staleTime: 60s)
       └── DesktopProvider
            └── SetupWizard (conditional)
                 └── {children}
```

**Zustand Stores** (12 stores in `lib/stores/`):
- `voice-store` — Recording/playback state, session history (persisted, max 30 sessions)
- `command-palette-store` — Global command palette toggle
- `sidebar-store` — Sidebar collapsed state
- `dashboard-store` — Alert dismissals
- `documents-store`, `decisions-store`, `people-store`, `process-store`, `market-store`, `admin-store`, `calendar-store`, `intelligence-store`

### 6.4 Key Patterns

**API Client** (`packages/api-client/src/base.ts`):
- Dynamic URL: `http://${window.location.hostname}:8000` (browser) or `NEXT_PUBLIC_GILBERTUS_API_URL` (SSR)
- Auth: `X-API-Key` header, auto-redirect to `/login` on 401
- Generic `customFetch<T>(config)` wrapper with abort signal support

**Root Layout** (`apps/web/app/layout.tsx`):
- HTML lang: `pl`, className: `dark` (forced dark mode)
- Font: Inter (latin + latin-ext)
- `<AppErrorBoundary>` + `<ErrorReporter userId="sebastian">`

**App Layout** (`apps/web/app/(app)/layout.tsx`):
- Sidebar + Topbar + Command Palette + Alert Drawer
- Voice FAB (floating action button) for roleLevel >= 50
- Offline Banner + Toast Container + Update Banner
- Hooks: `useRole()`, `useVoiceStore()`, `useSidebarStore()`, `useAlertsBell()`

---

## 7. RBAC & Security

### 7.1 Role Hierarchy

**Defined in:** `frontend/packages/rbac/src/roles.ts` and `omnius/core/permissions.py`

| Role | Power Level | Description |
|------|-------------|-------------|
| `owner` | 100 | Sebastian — full system access |
| `gilbertus_admin` | 99 | System administrator — bypasses all permission and governance checks |
| `operator` | 70 | Infrastructure/dev role — no business data access |
| `ceo` | 60 | Company CEO (e.g., Roch/Krystian) |
| `board` | 50 | Board member |
| `director` | 40 | Department director |
| `manager` | 30 | Team manager |
| `specialist` | 20 | Individual contributor |

### 7.2 Permission Model

**Permission strings** (colon-delimited hierarchy with wildcard support):

| Role | Key Permissions |
|------|----------------|
| owner / gilbertus_admin | All (implicit at level >= 99) |
| operator | `config:write:system`, `sync:manage`, `sync:credentials`, `infra:manage`, `dev:execute`, `commands:task` |
| ceo | `data:read:all`, `financials:read`, `evaluations:read:all`, `communications:read:all`, `users:manage:all`, `rbac:manage`, `prompts:manage`, all commands |
| board | `data:read:all`, `financials:read`, `evaluations:read:reports`, `users:manage:below`, most commands |
| director | `data:read:department`, `communications:read:department`, `config:write:department`, commands |
| manager | `data:read:team`, `config:write:own`, `commands:ticket/meeting/task` |
| specialist | `data:read:own`, `config:write:own`, `commands:task` |

### 7.3 Data Classification

5 levels controlling document visibility:

| Classification | Accessible To |
|---------------|--------------|
| `public` | All roles (except operator) |
| `internal` | director, manager, board, ceo, owner, gilbertus_admin |
| `confidential` | board, ceo, owner, gilbertus_admin |
| `ceo_only` | ceo, owner, gilbertus_admin |
| `personal` | All roles except operator (personal notes/health) |

**Note:** `operator` role has zero data classification access — restricted to system operations only.

### 7.4 Authentication

**Gilbertus API:**
- API Key via `X-API-Key` header (middleware in `app/api/auth.py`)
- Rate limiting with slowapi (trusted IPs bypass)

**Omnius API** (`omnius/api/auth.py`, 3 methods in priority order):
1. **X-API-Key** → SHA-256 hash lookup in `omnius_api_keys` table, returns role info
2. **Bearer JWT** → Azure AD token validation (JWKS cache, 3600s TTL, tenant/client from env)
3. **X-User-Email** → Dev-only (localhost, `OMNIUS_DEV_AUTH=1`), logs warning

**Security Headers** (Omnius):
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Strict-Transport-Security` (when HTTPS enabled)
- `X-Request-ID` propagation

### 7.5 Governance

**File:** `omnius/core/governance.py`

**Core Rules:**
1. CEO/board CAN create and improve features (with value validation)
2. CEO/board CANNOT delete features or reduce functionality
3. CEO/board CANNOT reduce data access scope
4. Every change must pass non-regression baseline check
5. Rules are role-bound, not person-bound
6. `gilbertus_admin` (level 99) bypasses all governance

**Forbidden Actions:**
```python
FORBIDDEN_ACTIONS = {
    "delete_feature", "remove_data_source", "reduce_data_scope",
    "delete_role", "delete_permission", "downgrade_role",
    "disable_sync", "disable_cron", "remove_endpoint", "delete_plugin",
}
```

**Protected Config Keys (Gilbertus-only):**
```python
PROTECTED_CONFIG_KEYS = {
    "rbac:permissions:",    # Cannot change RBAC from inside
    "governance:",          # Cannot modify governance rules
    "data_sources:",        # Cannot reduce data sources
    "sync:schedule:",       # Cannot disable syncs
    "prompt:system",        # Cannot change system prompts
}
```

**Value Validation:**
- Actions like `create_feature`, `deploy_plugin`, `add_endpoint` require LLM-based value assessment
- Claude evaluates: real business problem, savings/revenue/decisions, no duplication, proportional effort
- Returns: `value_score` (0.0-1.0), `approved` boolean, `reasoning`
- All assessments logged to `omnius_audit_log`

**Non-Regression:**
- Baselines stored in `omnius_baselines` table (INSERT-only, immutable)
- Checks: active_plugins count, custom metrics
- Changes that regress any baseline metric are blocked

---

## 8. MCP Tools

**File:** `mcp_gilbertus/server.py`

44+ tools organized into 6 tool groups, with a routing system that auto-selects the group based on Polish/English keywords.

### 8.1 Core Tools (10)

| Tool | Description |
|------|-------------|
| `gilbertus_router` | Routes requests to appropriate tool group based on keywords |
| `gilbertus_ask` | Search 31k+ document archive, get AI-powered answers (PL/EN) |
| `gilbertus_brief` | Generate Poranny Brief (morning intelligence brief) |
| `gilbertus_decide` | Log decisions to journal with context, expected outcome, confidence |
| `gilbertus_propose_action` | Propose actions for Sebastian's WhatsApp approval |
| `gilbertus_pending_actions` | List pending action proposals |
| `gilbertus_timeline` | Query events by type and time range |
| `gilbertus_alerts` | Proactive alerts (stale decisions, conflict spikes, silent contacts) |
| `gilbertus_summary` | Generate summaries (daily/weekly, by area) |
| `gilbertus_calendar` | Calendar management (events, conflicts, suggest, analytics, deep work blocks) |

### 8.2 People Tools (9)

| Tool | Description |
|------|-------------|
| `gilbertus_people` | List people with roles, orgs, chunk/event counts |
| `gilbertus_sentiment` | Sentiment trend for person over weeks |
| `gilbertus_commitments` | Track commitments (open, overdue, fulfilled, broken) |
| `gilbertus_delegation` | Delegation effectiveness per person |
| `gilbertus_delegation_chain` | Delegation task dashboard and status |
| `gilbertus_response_stats` | Communication response tracking by person/channel |
| `gilbertus_network` | Communication network analysis (silos, bottlenecks) |
| `gilbertus_meeting_prep` | Pre-meeting brief (attendees, talking points, red flags) |
| `gilbertus_evaluate` | Structured employee evaluation (WHAT/HOW/WEAK POINTS/SCORES) |

### 8.3 Business Tools (10)

| Tool | Description |
|------|-------------|
| `gilbertus_opportunities` | Opportunities ranked by ROI |
| `gilbertus_inefficiency` | Process inefficiency detection |
| `gilbertus_correlate` | Cross-domain pattern correlation |
| `gilbertus_process_intel` | Process Intelligence suite (business lines, apps, flows, tech radar) |
| `gilbertus_workforce_analysis` | [CEO-ONLY] Employee automation potential |
| `gilbertus_org_health` | Organizational health score (1-100) |
| `gilbertus_scenarios` | "What if?" scenario analyzer |
| `gilbertus_goals` | Strategic goal tracking |
| `gilbertus_decision_patterns` | Decision intelligence and confidence calibration |
| `gilbertus_legal` | Legal & Compliance orchestrator (URE, RODO, AML, KSH, ESG) |

### 8.4 Finance Tools (3)

| Tool | Description |
|------|-------------|
| `gilbertus_finance` | Financial dashboard (revenue, costs, cash, budgets, API costs) |
| `gilbertus_market` | Energy market intelligence (TGE, URE, PSE, BiznesAlert RSS) |
| `gilbertus_competitors` | Competitor intelligence (Tauron, PGE, Enea, Energa, Orlen) |

### 8.5 Omnius Tools (4)

| Tool | Description |
|------|-------------|
| `omnius_ask` | Query tenant-specific corporate data (REH/REF) |
| `omnius_command` | Execute commands (create_ticket, send_email, schedule_meeting, assign_task, deploy, etc.) |
| `omnius_status` | Check status of all Omnius tenants |
| `omnius_bridge` | Cross-tenant operations (search both REH+REF, aggregated dashboard) |

### 8.6 System Tools (8+)

| Tool | Description |
|------|-------------|
| `gilbertus_status` | System dashboard (DB stats, services, crons) |
| `gilbertus_db_stats` | Quick DB stats and extraction coverage |
| `gilbertus_lessons` | Query lessons_learned DB by category/module |
| `gilbertus_costs` | API cost report by provider/model/module/day |
| `gilbertus_crons` | Cron registry management |
| `gilbertus_authority` | Authority framework (levels 0-4, approval stats) |
| `gilbertus_self_rules` | List active self-rules from voice recordings |
| `gilbertus_wellbeing` | Wellbeing monitor (stress, family, health, work-life balance) |

### 8.7 Tool Routing

The `gilbertus_router` tool inspects query keywords (Polish and English) to select the tool group:

| Group | Trigger Keywords (sample) |
|-------|--------------------------|
| people | osoba, person, relacja, sentiment, zobowiazanie, delegacja, spotkanie, ocen |
| business | proces, cel, scenariusz, organizacja, optymalizacja, workforce, compliance, legal, URE, RODO |
| finance | finanse, pieniadz, cashflow, rynek, trading, konkurent, tge, cena, koszt |
| omnius | reh, ref, email, teams, ticket, zadanie, omnius, spolka |
| system | status, cron, koszt api, zasady, calendar, brief, wellbeing, lesson |

---

## 9. Omnius Multi-Tenant System

### 9.1 Architecture

**Omnius** is a per-company AI agent controlled by Gilbertus. Each tenant is an independent FastAPI instance with its own database, config, and API keys.

**File:** `omnius/api/main.py`

```python
COMPANY = os.getenv("OMNIUS_COMPANY_NAME")  # e.g., "Respect Energy Fuels"
TENANT = os.getenv("OMNIUS_TENANT")         # e.g., "ref"
# Title: "Omnius — Respect Energy Fuels"
# Description: "Corporate AI Agent for {COMPANY}. Controlled by Gilbertus."
```

### 9.2 Tenant Configuration

| Tenant | Company | Primary User | Database |
|--------|---------|-------------|----------|
| `reh` | Respect Energy Holding | Roch | `omnius_reh` |
| `ref` | Respect Energy Fuels | Krystian | `omnius_ref` |

**Per-tenant resources:**
- Separate PostgreSQL database (`OMNIUS_POSTGRES_DB`)
- Connection pool: min 3, max 30 connections
- Own API keys, users, permissions
- Own document/chunk collections
- Plaud device config per user

### 9.3 Omnius Database Schema (~15 tables)

| Migration | Tables |
|-----------|--------|
| 001_rbac | omnius_roles, omnius_users, omnius_permissions, omnius_api_keys, omnius_audit_log, omnius_operator_tasks |
| 002_content | omnius_documents, omnius_chunks, omnius_config |
| 004_plaud | omnius_plaud_config, omnius_audio_rules |
| 007_plugins | omnius_plugins, omnius_plugin_versions |
| 008_sandbox | omnius_sandbox_sessions |
| 009_reviews | omnius_plugin_reviews, omnius_plugin_proposals |
| 011_config | omnius_plugin_config |
| 012_owner | (owner role addition) |

### 9.4 Plugin System

**SDK** (`omnius/plugins/sdk/base.py`):
- `PluginContext(tenant, user_id, plugin_name)` — sandboxed execution context
- `query_data(query, classification_max="internal")` — semantic search capped at classification level
- Max 10 results per query
- Per-plugin logging context

**Sandbox** (`omnius/core/sandbox.py`):
- Docker-based isolation (`omnius-sandbox:latest` image)
- Dedicated `sandbox-net` network (no external access)
- 30-minute session limit
- No secrets exposure
- Plugins extracted as tar archives

**Governance Integration:**
- Plugin deployment requires value validation (LLM assessment)
- Plugin reviews: security + quality scores
- Cannot delete or downgrade plugins (forbidden action)

### 9.5 Cross-Tenant Operations

The `omnius_bridge` MCP tool enables:
- Search across both REH + REF simultaneously
- Aggregated dashboard
- Cross-company audit trail
- Sync-all command

---

## 10. Automation & Self-Healing

### 10.1 Cron Jobs (62 active)

**Categories and Key Schedules:**

| Category | Jobs | Key Schedules |
|----------|------|---------------|
| **Data Ingestion** | ~10 | Every 5 min: live_ingest, wa_importer, index_chunks. Every 3 min: wa_repair. Hourly: corporate sync |
| **Extraction** | ~5 | Every 30 min: turbo_extract (3000 chunks, 12 workers). Every 2h: commitment extraction |
| **Code Quality** | ~6 | Every 30 min: code_review. Every 10 min: code_fix_parallel. Every 2h: deep_fix. Every 2 min: webapp_autofix |
| **Analysis** | ~10 | Every 2h: opportunity_detector, commitment_check. Daily: alerts (6:30), decision_reminders (8:00), perf_improvement (2:00) |
| **Intelligence** | ~5 | Daily 7:00: morning_brief. Daily 20:00: daily_digest. Sunday: weekly_synthesis (19:00), weekly_report (20:00). Friday: weekly_analysis (21:00) |
| **Compliance** | ~6 | Daily 6:15: compliance_daily. Every 6h: regulatory_scanner. Sunday: weekly_compliance. Monthly 1st: verification. Weekdays 9:00: training_check |
| **Monitoring** | ~8 | Every 10 min: cron_health_check, non_regression. Every 15 min: data_guardian, plaud_monitor. Every 30 min: extraction_watchdog, observability |
| **Backup** | ~3 | Daily 3:00 + 5x/day: backup_db. Daily 3:20: prune_backups. @reboot: auto_restore |
| **Maintenance** | ~4 | Daily 5:00: answer_cache_cleanup. Every 6h: conversation_window_cleanup. Daily 3:00: log_rotation |
| **Other** | ~5 | Every 30 min: session_archive, session_context. Hourly: retrieval_quality_check. Daily: api_credits_check. Quarterly: evaluations |

### 10.2 Webapp AutoFix

**File:** `scripts/webapp_autofix.sh`

Runs every 2 minutes:
1. Monitors Turbopack logs for new TypeScript/build errors
2. Checks application routes for HTTP 500/502 errors
3. On detection, runs `claude -p` with error context for automatic repair
4. Maintains state JSON to track last-seen error positions

### 10.3 Code Autofixer (3-Tier)

**Architecture:**

```
Code Review (every 30 min)
  └─▶ code_review_findings table
       └─▶ Cluster Manager (groups by file/pattern)
            ├─▶ Tier 1: Deterministic (ruff --fix, regex)
            │    No LLM, handles: unused imports (F401), unused vars,
            │    print→structlog, date format, dead code
            │
            ├─▶ Tier 2: LLM-Based (claude -p sessions)
            │    Sonnet model, enriched context, budget tracking,
            │    project conventions enforcement
            │
            └─▶ Tier 3: Deep Fixer (stuck bugs, 3+ failed attempts)
                 Max $2.00/bug, 1-2 bugs per run, every 2h,
                 auto-promotes to manual_review after threshold
```

**Supporting components:**
- **Cluster Manager** (`autofixer/cluster_manager.py`): Groups findings, assigns tiers via regex patterns, max 10 per cluster, max 3 attempts per round
- **Context Gatherer** (`autofixer/context_gatherer.py`): Enriches with file contents, resolved examples, and project conventions:
  - SQL: parameterized (`%s` with params, never f-strings)
  - DB: `get_pg_connection()` from `app/db/postgres.py`
  - Logging: structlog only (never `print()`)
  - Timeouts: explicit on all external API calls
  - Cost tracking: every Anthropic call logs via `log_anthropic_cost()`
  - Caching: `cache_control` ephemeral on system prompts

### 10.4 Data Guardian

**File:** `scripts/data_guardian/runner.py`

- Fixes issues identified during Gilbertus audit
- Runs Claude Code sessions sequentially per problem
- CLI modes: `--dry-run`, `--task C1`, `--status`, `--reset C1`
- Max timeout: 900 seconds per task

### 10.5 Performance Improvement Agent

**File:** `app/analysis/perf_improver/improvement_agent.py`

Daily automated cycle:
1. Analyze query performance → detect bottleneck
2. Plan fix → apply change
3. Verify improvement → commit or revert
4. Log to `perf_improvement_journal`

---

## 11. Configuration

### 11.1 Timezone

**File:** `app/config/timezone.py`

```python
from zoneinfo import ZoneInfo

APP_TIMEZONE_NAME = 'Europe/Warsaw'
APP_TIMEZONE = ZoneInfo(APP_TIMEZONE_NAME)

def now():     return datetime.now(APP_TIMEZONE)
def today():   return now().date()
def to_app_tz(dt): ...  # Converts any datetime to CET/CEST
```

**Convention:** All cron schedules in UTC, all comments and displays in CET.

### 11.2 Key Environment Variables

**Gilbertus:**

| Variable | Default | Purpose |
|----------|---------|---------|
| `POSTGRES_HOST` | 127.0.0.1 | PostgreSQL host |
| `PGBOUNCER_PORT` / `POSTGRES_PORT` | 5433 | PostgreSQL port |
| `POSTGRES_DB` | gilbertus | Database name |
| `PG_POOL_MIN_SIZE` | 5 | Min pool connections |
| `ANTHROPIC_MODEL` | claude-sonnet-4-6 | Primary LLM model |
| `ANTHROPIC_FAST_MODEL` | claude-haiku-4-5 | Light tasks model |
| `ANTHROPIC_FALLBACK_MODEL` | claude-haiku-4-5 | Fallback on errors |
| `CORS_ALLOWED_ORIGINS` | * | Comma-separated origins |
| `APP_NAME` / `APP_VERSION` / `APP_ENV` | — | App metadata |

**Omnius:**

| Variable | Default | Purpose |
|----------|---------|---------|
| `OMNIUS_COMPANY_NAME` | (required) | Company display name |
| `OMNIUS_TENANT` | (required) | Tenant identifier (reh/ref) |
| `OMNIUS_POSTGRES_DB` | omnius_ref | Omnius database |
| `OMNIUS_POSTGRES_PORT` | 5432 | Omnius DB port |
| `OMNIUS_AZURE_TENANT_ID` | — | Azure AD tenant |
| `OMNIUS_AZURE_CLIENT_ID` | — | Azure AD client |
| `OMNIUS_CORS_ORIGINS` | teams.microsoft.com | CORS origins |
| `OMNIUS_DEV_AUTH` | 0 | Enable dev auth (localhost only) |
| `OMNIUS_LLM_MODEL` | claude-haiku-4-5 | Governance validation model |
| `OMNIUS_HTTPS` | 0 | Enable HSTS header |

**Frontend:**

| Variable | Purpose |
|----------|---------|
| `NEXT_PUBLIC_GILBERTUS_API_URL` | API base URL for SSR |

### 11.3 Docker Services

| Service | Container | Port | Purpose |
|---------|-----------|------|---------|
| PostgreSQL 16 | gilbertus-postgres | 5433 | Main database (named volume) |
| Qdrant | gilbertus-qdrant | 6333/6334 | Vector search |

### 11.4 Connection Pools

| Pool | Min | Max | Timeout |
|------|-----|-----|---------|
| Gilbertus PostgreSQL | 5 | 10 | — |
| Omnius PostgreSQL | 3 | 30 | 30s |

---

## 12. Development Workflow

### 12.1 Code Conventions (from CLAUDE.md)

- **Database:** Always use connection pool (`app/db/postgres.py`), never raw `psycopg.connect()`
- **SQL:** All queries must be parameterized (`%s` with tuple, never f-strings)
- **Logging:** structlog only, never `print()` in production
- **Dates:** Always absolute (YYYY-MM-DD), never "today"/"now" in docs/memory
- **Timezone:** CET (Europe/Warsaw), import from `app/config/timezone.py`
- **Cron entries:** Must have `cd /home/sebastian/personal-ai &&` prefix
- **Endpoints:** Must have timeout
- **Error handling:** Structured logging
- **Extraction loops:** Must track negatives (`chunks_*_checked` tables)
- **Parallel workers:** Must have partitioning (`--worker X/N`)

### 12.2 Pre-Commit Checklist

- [ ] SQL parameterized?
- [ ] Connection from pool, not raw?
- [ ] Extraction loop tracks negatives?
- [ ] Parallel workers have partitioning?
- [ ] Cron entry has `cd` prefix?
- [ ] Prompt doesn't contain "Be conservative"?
- [ ] New endpoint has timeout?
- [ ] Error handling logs structured?

### 12.3 Lessons Learned System

Database table `lessons_learned` stores operational lessons by category/module:
```bash
docker exec gilbertus-postgres psql -U gilbertus -d gilbertus \
  -c "SELECT category, description, prevention_rule FROM lessons_learned ORDER BY id DESC LIMIT 10;"
```

### 12.4 Session Management

- **Session context:** Auto-generated every 30 min → `SESSION_CONTEXT.md`
- **Dev logs:** Written after each session → `logs/dev_log_*.md`
- **Session summaries:** Stored in memory → `memory/session_*.md`
- **Claude sessions:** Archived every 30 min → `scripts/archive_claude_sessions.sh`

---

## 13. Deployment

### 13.1 Current: Local Development (WSL2)

- WSL2 on Windows (Linux 6.6.87.2-microsoft-standard-WSL2)
- Docker for PostgreSQL and Qdrant
- Python virtual environment
- cron for automation
- FastAPI dev server on port 8000
- Next.js dev server (Turbopack)

### 13.2 Planned: Hetzner VPS

**Script:** `scripts/deploy_hetzner_cloud.sh`

Target: self-hosted VPS for production deployment with:
- Docker Compose for all services
- Automated backup to remote storage
- SSL/TLS termination
- Monitoring and alerting

---

## 14. Appendix

### A. Database Table List (137 Gilbertus tables)

```
action_items                action_outcomes             alert_delivery_log
alert_fix_tasks             alert_suppressions          alerts
answer_cache                answer_evaluations          api_costs
app_cost_history            app_errors                  app_inventory
ask_run_matches             ask_runs                    authority_levels
authority_log               budget_items                business_line_signals
business_lines              calibration_settings        checkpoint_blobs
checkpoint_migrations       checkpoint_writes           checkpoints
chunk_entities              chunks                      chunks_commitment_checked
chunks_entity_checked       chunks_event_checked        code_review_files
code_review_findings        commitments                 communication_edges
competitor_analysis         competitor_signals          competitors
compliance_areas            compliance_audit_evidence   compliance_communications
compliance_deadlines        compliance_documents        compliance_matters
compliance_obligations      compliance_raci             compliance_risk_assessments
compliance_training_records compliance_trainings        contact_link_log
contacts                    contracts                   conversation_windows
cost_alert_log              cost_budgets                cron_registry
cron_user_assignments       data_flows                  decision_context
decision_outcome_checks     decision_outcomes           decisions
delegation_tasks            discovered_processes        document_contacts
documents                   email_cleanup_candidates    employee_work_profiles
engagement_metrics          entities                    event_candidate_chunks
event_entities              event_entity_backfill_candidates  events
extraction_runs             financial_alerts            financial_metrics
goal_dependencies           goal_progress               guardian_alerts
health_checks               ingestion_dlq               ingestion_health
insights                    interpretation_cache        item_annotations
lessons_learned             lineage                     llm_evaluations
market_alerts               market_insights             market_items
market_sources              meeting_minutes             opportunities
optimization_plans          org_health_scores           people
perf_improvement_journal    predictive_alerts           prompt_versions
quality_reviews             query_stage_times           rel_events
rel_journal                 rel_metrics                 rel_partners
rel_patterns                relationship_open_loops     relationship_roles_history
relationship_timeline       relationships               response_drafts
response_feedback           roi_activities              roi_hierarchy
roi_summaries               rule_applications           scenario_outcomes
scenarios                   self_rules                  self_rules_processed_chunks
sent_communications         sentiment_scores            sessions
sources                     standing_order_metrics      standing_orders
strategic_goals             strategic_radar             strategic_radar_snapshots
summaries                   tech_dependencies           tech_roadmap_snapshots
tech_solutions              user_activity_log           voice_conversations
wa_tasks                    wellbeing_scores
```

### B. API Endpoint Catalog

#### Direct Routes (app/api/main.py)

| Method | Path |
|--------|------|
| POST | `/ask` |
| POST | `/evaluate` |
| GET | `/scorecard/{person_slug}` |
| POST | `/opportunities/scan` |
| GET | `/opportunities` |
| GET | `/inefficiency` |
| POST | `/correlate` |
| GET | `/health` |
| GET | `/version` |
| GET | `/code-fixes/manual-queue` |
| GET | `/admin/roles` |
| GET | `/autofixers/dashboard` |
| GET | `/conversation/windows` |
| GET | `/status` |
| GET | `/performance/stats` |
| POST | `/timeline` |
| POST | `/summary/generate` |
| POST | `/summary/query` |
| GET | `/brief/today` |
| GET | `/alerts` |
| GET | `/commitments` |
| POST | `/commitments/check` |
| POST | `/commitments/{commitment_id}/resolve` |
| GET | `/commitments/{commitment_id}` |
| GET | `/meeting-prep` |
| GET | `/meeting-minutes` |
| POST | `/meeting-minutes/generate` |
| GET | `/sentiment/{person_slug}` |
| GET | `/sentiment-alerts` |
| GET | `/wellbeing` |
| POST | `/wellbeing/check` |
| GET | `/contracts` |
| GET | `/contracts/expiring` |
| GET | `/compliance/dashboard` |
| GET | `/compliance/areas` |
| GET | `/compliance/areas/{code}` |
| GET | `/compliance/matters` |
| POST | `/compliance/matters` |
| GET | `/compliance/matters/{matter_id}` |
| GET | `/compliance/obligations` |
| GET | `/compliance/obligations/overdue` |
| POST | `/compliance/obligations` |
| POST | `/compliance/obligations/{obligation_id}/fulfill` |
| GET | `/compliance/deadlines` |
| GET | `/compliance/deadlines/overdue` |
| POST | `/compliance/matters/{matter_id}/research` |
| POST | `/compliance/matters/{matter_id}/advance` |
| POST | `/compliance/matters/{matter_id}/report` |
| GET | `/compliance/risks` |
| GET | `/compliance/risks/heatmap` |
| POST | `/compliance/scan` |
| GET | `/compliance/documents` |
| GET | `/compliance/documents/stale` |
| POST | `/compliance/documents/generate` |
| POST | `/compliance/documents/{doc_id}/approve` |
| POST | `/compliance/documents/{doc_id}/sign` |
| GET | `/compliance/trainings` |
| GET | `/compliance/trainings/{training_id}/status` |
| POST | `/compliance/trainings` |
| POST | `/compliance/trainings/{training_id}/complete` |
| GET | `/compliance/report/daily` |
| GET | `/compliance/report/weekly` |
| GET | `/compliance/report/area/{code}` |
| GET | `/compliance/raci` |
| POST | `/compliance/raci` |
| POST | `/compliance/matters/{matter_id}/communication-plan` |
| POST | `/compliance/matters/{matter_id}/execute-communication` |
| GET | `/delegation` |
| GET | `/delegation/{person_slug}` |
| GET | `/blind-spots` |
| GET | `/network` |
| GET | `/predictions` |
| GET | `/weekly-synthesis` |
| POST | `/response-drafter/run` |
| GET | `/crons` |
| GET | `/crons/summary` |
| POST | `/crons/{job_name}/enable` |
| POST | `/crons/{job_name}/disable` |
| GET | `/crons/generate/{user}` |
| GET | `/action-outcomes` |
| POST | `/action-outcomes/check` |
| GET | `/decision-intelligence` |
| POST | `/decision-intelligence/run` |
| GET | `/rules/effectiveness` |
| POST | `/rules/reinforce` |
| GET | `/authority` |
| GET | `/authority/stats` |
| POST | `/authority/{category}/level/{level}` |
| GET | `/delegation-chain` |
| POST | `/delegation-chain/check` |
| POST | `/delegation-chain/delegate` |
| GET | `/response-tracking` |
| POST | `/response-tracking/run` |
| GET | `/channel-effectiveness` |
| GET | `/standing-order-effectiveness` |
| GET | `/authority/suggestions` |
| GET | `/finance` |
| POST | `/finance/metric` |
| POST | `/finance/budget` |
| POST | `/finance/estimate-cost` |
| GET | `/costs/budget` |
| GET | `/calendar/events` |
| GET | `/calendar/conflicts` |
| GET | `/calendar/analytics` |
| GET | `/calendar/suggestions` |
| POST | `/calendar/block-deep-work` |
| GET | `/meeting-roi` |
| GET | `/goals` |
| GET | `/goals/{goal_id}` |
| POST | `/goals` |
| POST | `/goals/{goal_id}/progress` |
| GET | `/org-health` |
| POST | `/org-health/assess` |
| GET | `/scenarios` |
| POST | `/scenarios` |
| POST | `/scenarios/{scenario_id}/analyze` |
| GET | `/scenarios/compare` |
| POST | `/scenarios/auto-scan` |
| GET | `/market/dashboard` |
| POST | `/market/scan` |
| GET | `/market/insights` |
| POST | `/market/sources` |
| GET | `/market/alerts` |
| GET | `/competitors` |
| POST | `/competitors` |
| POST | `/competitors/scan` |
| GET | `/competitors/{competitor_id}/analysis` |
| GET | `/competitors/signals` |
| GET | `/process-intel/dashboard` |
| GET | `/process-intel/business-lines` |
| POST | `/process-intel/discover` |
| GET | `/process-intel/processes` |
| POST | `/process-intel/mine` |
| GET | `/process-intel/apps` |
| POST | `/process-intel/scan-apps` |
| GET | `/process-intel/flows` |
| POST | `/process-intel/map-flows` |
| GET | `/process-intel/optimizations` |
| POST | `/process-intel/plan` |
| POST | `/process-intel/scan-apps-deep` |
| GET | `/process-intel/app-analysis` |
| GET | `/process-intel/app-analysis/{app_id}` |
| POST | `/process-intel/app-costs` |
| GET | `/process-intel/app-replacement-ranking` |
| POST | `/process-intel/analyze-employee/{person_slug}` |
| POST | `/process-intel/analyze-all-employees` |
| GET | `/process-intel/work-profile/{person_slug}` |
| GET | `/process-intel/automation-overview` |
| GET | `/process-intel/automation-roadmap` |
| POST | `/process-intel/discover-tech` |
| GET | `/process-intel/tech-radar` |
| GET | `/process-intel/tech-radar/{solution_id}` |
| GET | `/process-intel/tech-roadmap` |
| POST | `/process-intel/tech-solution/{solution_id}/status` |
| GET | `/process-intel/tech-strategic-alignment` |
| POST | `/process-intel/discover-bg` |
| POST | `/process-intel/mine-bg` |
| POST | `/process-intel/optimize-bg` |
| GET | `/process-intel/job/{job_id}` |
| GET | `/coverage/heatmap` |

#### Router-Based Endpoints

| Router | Method | Path |
|--------|--------|------|
| activity | POST | `/activity/log` |
| activity | GET | `/activity/log` |
| activity | POST | `/items/annotate` |
| activity | GET | `/items/{item_type}/{item_id}/annotations` |
| activity | POST | `/items/research` |
| alerts | POST | `/alerts/{alert_id}/resolve` |
| alerts | GET | `/alerts/suppressions` |
| alerts | DELETE | `/alerts/suppressions/{suppression_id}` |
| alerts | GET | `/alerts/fix-tasks` |
| alerts | POST | `/alerts/fix-tasks/{task_id}/complete` |
| guardian | GET | `/guardian/alerts` |
| guardian | POST | `/guardian/alerts/{alert_id}/acknowledge` |
| guardian | POST | `/guardian/alerts/acknowledge-all` |
| guardian | GET | `/guardian/alerts/stats` |
| decisions | POST | `/decision` |
| decisions | POST | `/decision/{decision_id}/outcome` |
| decisions | GET | `/decisions` |
| decisions | POST | `/decisions/scan` |
| decisions | GET | `/decisions/pending` |
| decisions | GET | `/decisions/patterns` |
| errors | POST | `/errors/report` |
| errors | GET | `/errors/unresolved` |
| errors | POST | `/errors/{error_id}/resolve` |
| feedback | GET | `/feedback/trends` |
| feedback | GET | `/feedback/weak-areas` |
| feedback | GET | `/feedback/optimization-report` |
| insights | GET | `/insights` |
| insights | GET | `/insights/summary` |
| observability | GET | `/observability/dashboard` |
| observability | GET | `/observability/alert-check` |
| observability | GET | `/observability/trace/{run_id}` |
| observability | GET | `/observability/graph/action/{action_id}` |
| plaud | POST | `/plaud` |
| presentation | POST | `/presentation/ask` |
| presentation | POST | `/presentation/tts` |
| presentation | GET | `/presentation/intro` |
| presentation | GET | `/presentation/demo` |
| relationships | GET | `/people` |
| relationships | POST | `/people` |
| relationships | GET | `/people/{slug}` |
| relationships | PUT | `/people/{slug}` |
| relationships | DELETE | `/people/{slug}` |
| relationships | POST | `/people/{slug}/timeline` |
| relationships | POST | `/people/{slug}/loops` |
| relationships | PUT | `/people/{slug}/loops/{loop_id}` |
| relationships | POST | `/people/{slug}/roles` |
| roi | GET | `/roi/summary` |
| roi | GET | `/roi/builder` |
| roi | GET | `/roi/management` |
| roi | GET | `/roi/life` |
| roi | GET | `/roi/company/{company_id}` |
| roi | GET | `/roi/leaderboard` |
| roi | POST | `/roi/activity` |
| roi | POST | `/roi/scan` |
| roi | GET | `/roi/hierarchy` |
| roi | POST | `/roi/hierarchy` |
| strategic_radar | GET | `/strategic-radar` |
| strategic_radar | GET | `/strategic-radar/history` |
| teams | POST | `/teams/webhook` |
| updates | GET | `/updates/{app_name}/{target}/{arch}/{current_version}` |
| updates | GET | `/updates/{app_name}/latest` |
| updates | POST | `/updates/{app_name}/publish` |
| voice | POST | `/voice/transcribe` |
| voice | POST | `/voice/ask` |
| voice | POST | `/voice/command` |
| voice | POST | `/voice/tts` |
| voice | GET | `/voice/health` |
| voice_ws | WS | `/voice/ws` |

### C. Cron Job Schedule (62 active entries)

**Ingestion & Sync:**

| Schedule (UTC) | CET | Job |
|---------------|-----|-----|
| `*/5 * * * *` | every 5m | Live ingest + WhatsApp import + chunk indexing |
| `*/3 * * * *` | every 3m | WhatsApp repair monitor |
| `15 * * * *` | hourly :15 | Corporate data sync |
| `*/30 * * * *` | every 30m | Session archive + session context |

**Extraction:**

| Schedule (UTC) | CET | Job |
|---------------|-----|-----|
| `*/30 * * * *` | every 30m | Turbo extraction (3000 chunks, 12 workers, Haiku) |
| `5 */2 * * *` | every 2h :05 | Commitment extraction (200 chunks, 2 workers) |

**Code Quality & Self-Healing:**

| Schedule (UTC) | CET | Job |
|---------------|-----|-----|
| `*/30 * * * *` | every 30m | Code review (5 files per run) |
| `*/10 * * * *` | every 10m | Parallel code fixer |
| `0 */2 * * *` | every 2h | Deep fixer (Tier 3) |
| `*/2 * * * *` | every 2m | Webapp autofix monitor |
| `*/10 * * * *` | every 10m | Non-regression monitor |

**Analysis & Intelligence:**

| Schedule (UTC) | CET | Job |
|---------------|-----|-----|
| `0 5 * * *` | 07:00 CET | Poranny Brief (morning brief) |
| `30 4 * * *` | 06:30 CET | Alerts check |
| `0 6 * * *` | 08:00 CET | Decision outcome reminders |
| `0 18 * * *` | 20:00 CET | Daily digest |
| `0 */2 * * *` | every 2h | Opportunity detector + commitment check |
| `*/15 8-20 * * 1-5` | weekdays 10-22 CET | Response drafter |
| `0 19 * * 5` | Fri 21:00 CET | Weekly analysis |
| `0 17 * * 0` | Sun 19:00 CET | Weekly synthesis |
| `0 18 * * 0` | Sun 20:00 CET | Weekly report |
| `0 20 * * 0` | Sun 22:00 CET | Architecture review |

**Compliance & Security:**

| Schedule (UTC) | CET | Job |
|---------------|-----|-----|
| `15 4 * * *` | 06:15 CET | Daily compliance check |
| `0 */6 * * *` | every 6h | Regulatory scanner |
| `0 17 * * 0` | Sun 19:00 CET | Weekly compliance report |
| `0 6 1 * *` | 1st 08:00 CET | Monthly verification |
| `0 7 * * 1-5` | weekdays 09:00 CET | Training deadline check |
| `0 6 * * 1` | Mon 08:00 CET | Security scan |

**Monitoring:**

| Schedule (UTC) | CET | Job |
|---------------|-----|-----|
| `*/10 * * * *` | every 10m | Cron health check |
| `*/30 * * * *` | every 30m | Extraction watchdog + observability alert check |
| `*/15 * * * *` | every 15m | Data guardian + Plaud monitor |
| `*/2 * * * *` | every 2m | Task monitor |
| `0 * * * *` | hourly | Retrieval quality check |

**Backup & Maintenance:**

| Schedule (UTC) | CET | Job |
|---------------|-----|-----|
| `0 1 * * *` | 03:00 CET | Primary backup |
| `0 5,9,13,17,21 * * *` | 5x/day | Additional backups |
| `20 1 * * *` | 03:20 CET | Prune old backups |
| `0 3 * * *` | 05:00 CET | Answer cache cleanup |
| `0 */6 * * *` | every 6h | Conversation window cleanup |
| `0 1 * * *` | 03:00 CET | Log rotation |

---

*This document is the definitive technical reference for the Gilbertus & Omnius project. For live status, run `bash scripts/generate_session_context.sh` or check `SESSION_CONTEXT.md`.*
