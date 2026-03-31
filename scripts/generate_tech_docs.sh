#!/usr/bin/env bash
# Technical Documentation Generator — comprehensive docs for Gilbertus & Omnius
set -uo pipefail

PROJ=/home/sebastian/personal-ai
LOG="$PROJ/logs/tech_docs_generator.log"
CLAUDE_BIN="${CLAUDE_BIN:-/home/sebastian/.npm-global/bin/claude}"
DOCS_DIR="$PROJ/docs/technical"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }
mkdir -p "$PROJ/logs" "$DOCS_DIR"

log "=== Technical Documentation Generator — start ==="

# ── Phase 1: Collect live metrics ────────────────────────────────────────
log "Phase 1: Collecting live metrics..."

METRICS=$(cat <<METRICS_EOF
## Live System Metrics ($(date '+%Y-%m-%d %H:%M CET'))

### Database
$(docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -c "
SELECT 'tables' as metric, COUNT(*)::text as value FROM information_schema.tables WHERE table_schema='public'
UNION ALL SELECT 'documents', COUNT(*)::text FROM documents
UNION ALL SELECT 'chunks', COUNT(*)::text FROM chunks
UNION ALL SELECT 'entities', COUNT(*)::text FROM entities
UNION ALL SELECT 'events', COUNT(*)::text FROM events
UNION ALL SELECT 'insights', COUNT(*)::text FROM insights
UNION ALL SELECT 'sources', COUNT(*)::text FROM sources
UNION ALL SELECT 'code_review_findings', COUNT(*)::text FROM code_review_findings
ORDER BY metric;" 2>/dev/null)

### Sources Breakdown
$(docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -c "
SELECT source_type, COUNT(*) as documents FROM sources GROUP BY source_type ORDER BY documents DESC;" 2>/dev/null)

### API Endpoints
$(grep -c "@app\.\(get\|post\|delete\|put\|patch\)" "$PROJ/app/api/main.py" 2>/dev/null) endpoints in main.py
$(find "$PROJ/app/api" -name "*.py" | xargs grep -c "@app\.\|@router\." 2>/dev/null | awk -F: '{s+=$2}END{print s}') total API routes

### Cron Jobs
$(crontab -l 2>/dev/null | grep -v "^#" | grep -v "^$" | wc -l) active cron entries

### Frontend
$(find "$PROJ/frontend/apps/web/app" -name "page.tsx" 2>/dev/null | wc -l) pages
$(find "$PROJ/frontend/packages/ui/src/components" -name "*.tsx" 2>/dev/null | wc -l) UI components

### MCP Tools
$(grep -c "\"name\":" "$PROJ/mcp_gilbertus/server.py" 2>/dev/null) MCP tool registrations

### Code Stats
$(find "$PROJ/app" "$PROJ/mcp_gilbertus" "$PROJ/omnius" -name "*.py" 2>/dev/null | wc -l) Python files
$(find "$PROJ/app" "$PROJ/mcp_gilbertus" "$PROJ/omnius" -name "*.py" 2>/dev/null | xargs wc -l 2>/dev/null | tail -1) total Python LOC
$(find "$PROJ/frontend" -name "*.tsx" -o -name "*.ts" 2>/dev/null | grep -v node_modules | grep -v .next | wc -l) TypeScript files
METRICS_EOF
)

log "Metrics collected"

# ── Phase 2: Collect file tree ───────────────────────────────────────────
log "Phase 2: Collecting file tree..."

FILE_TREE=$(cat <<TREE_EOF
### Backend Structure
$(find "$PROJ/app" -type f -name "*.py" | sort | sed "s|$PROJ/||" | head -120)

### Frontend Structure
$(find "$PROJ/frontend/apps/web/app" -type f -name "*.tsx" | sort | sed "s|$PROJ/||")
$(find "$PROJ/frontend/packages" -type f -name "*.tsx" -o -name "*.ts" | grep -v node_modules | sort | sed "s|$PROJ/||" | head -80)

### MCP & Omnius
$(find "$PROJ/mcp_gilbertus" "$PROJ/omnius" -type f -name "*.py" | sort | sed "s|$PROJ/||")

### Scripts
$(find "$PROJ/scripts" -type f \( -name "*.sh" -o -name "*.py" \) | sort | sed "s|$PROJ/||" | head -40)

### Migrations
$(find "$PROJ/app/db/migrations" "$PROJ/omnius/db/migrations" -type f -name "*.sql" 2>/dev/null | sort | sed "s|$PROJ/||")
TREE_EOF
)

log "File tree collected"

# ── Phase 3: Generate documentation via Claude ──────────────────────────
log "Phase 3: Launching Claude documentation generator..."

cd "$PROJ"
$CLAUDE_BIN --permission-mode bypassPermissions --print --max-turns 80 \
"You are a senior technical writer generating comprehensive documentation for the Gilbertus & Omnius project.

## YOUR TASK
Generate a complete, state-of-the-art technical documentation file at docs/technical/ARCHITECTURE.md.
This is ONE comprehensive document covering everything. Write in English with Polish terms where they are domain-specific.

## LIVE METRICS
$METRICS

## FILE TREE
$FILE_TREE

## INSTRUCTIONS

### What to document
Read the actual source code to understand each component. Do NOT guess — read files before documenting them.

Key files to read (in order):
1. CLAUDE.md — project overview, conventions, architecture summary
2. app/config/timezone.py — central timezone config
3. app/db/postgres.py — connection pool
4. app/api/main.py — first 100 lines (app setup, CORS, middleware) + scan all @app.get/@app.post decorators
5. app/retrieval/answering.py — core Q&A engine (first 50 lines)
6. app/retrieval/morning_brief.py — brief generation (first 30 lines)
7. app/extraction/entities.py and events.py — first 30 lines each
8. mcp_gilbertus/server.py — MCP tools (first 100 lines + scan tool names)
9. omnius/api/auth.py — authentication (first 50 lines)
10. omnius/core/permissions.py — RBAC (first 30 lines)
11. omnius/core/governance.py — governance rules (first 30 lines)
12. frontend/packages/rbac/src/roles.ts — role hierarchy
13. frontend/packages/rbac/src/navigation.ts — module definitions
14. frontend/packages/api-client/src/base.ts — API client
15. frontend/apps/web/app/layout.tsx — root layout
16. frontend/apps/web/components/providers.tsx — provider stack
17. app/analysis/autofixer/tier2_executor.py — first 30 lines (autofixer architecture)
18. app/orchestrator/cron_registry.py — first 50 lines (cron system)
19. app/config/timezone.py — timezone centralization
20. scripts/webapp_autofix.sh — first 30 lines

### Document structure (write to docs/technical/ARCHITECTURE.md)

# Gilbertus & Omnius — Technical Architecture

## 1. Executive Summary
- What is Gilbertus (AI Mentat for Sebastian Jabłoński)
- What is Omnius (multi-tenant agent system for company employees)
- Key numbers (from live metrics above)

## 2. System Architecture
- High-level diagram (ASCII art)
- Data flow: Sources → Ingestion → Chunks → Extraction → Entities/Events → Retrieval → Delivery
- Component diagram showing all layers

## 3. Technology Stack
- Backend: Python, FastAPI, PostgreSQL 16, Qdrant, Claude API, OpenAI embeddings
- Frontend: Next.js 16, React 19, TypeScript, Tailwind CSS, TanStack Query, Zustand
- Infrastructure: Docker, WSL2, cron-based automation
- AI: Claude (Haiku for extraction, Sonnet for analysis, Opus for complex tasks)

## 4. Data Layer
### 4.1 PostgreSQL Schema
- Core tables (sources, documents, chunks, entities, events, insights)
- Supporting tables (commitments, decisions, alerts, lessons_learned)
- Omnius tables (roles, users, permissions, api_keys, audit_log)
- Code quality tables (code_review_findings, code_review_files)
- Total table count and key relationships

### 4.2 Qdrant Vector Store
- Collection structure, embedding model, search strategy

### 4.3 Data Sources
- List all source types with document counts (from metrics)
- Ingestion method for each (Graph API, OpenClaw, Plaud, file import)

## 5. Backend Architecture
### 5.1 API Layer (FastAPI)
- Endpoint categories with counts
- Authentication (API key, Azure AD)
- CORS configuration
- Key endpoint groups: /ask, /brief, /alerts, /timeline, /status, /admin/*

### 5.2 Retrieval Engine
- Hybrid search (BM25 + vector RRF fusion)
- Query interpretation pipeline
- Context assembly and answer generation

### 5.3 Extraction Pipeline
- Entity extraction (5 types, 24 workers, partitioned)
- Event extraction (15 types)
- Commitment extraction
- Chunking strategy

### 5.4 Analysis Modules
- List all modules in app/analysis/ with one-line descriptions
- Intelligence layer (commitments, meeting prep, sentiment, wellbeing, etc.)
- Market intelligence, compliance, legal

### 5.5 Orchestration
- Cron registry and job management
- Task monitor and WhatsApp delivery
- Calendar manager
- Delegation chain

## 6. Frontend Architecture
### 6.1 Monorepo Structure
- apps/web (Next.js app)
- packages/ui (shared components)
- packages/api-client (typed API client)
- packages/rbac (role-based access control)
- packages/i18n (internationalization)

### 6.2 Pages & Modules
- List all pages with paths and descriptions
- Role access matrix

### 6.3 State Management
- TanStack React Query (server state)
- Zustand stores (client state)
- SessionProvider (auth)

### 6.4 Key Patterns
- API client with dynamic URL resolution
- Custom hooks (use-dashboard, use-admin, use-chat)
- Error boundary and error reporter

## 7. RBAC & Security
### 7.1 Role Hierarchy
- Owner (100), gilbertus_admin (99), operator (70), ceo (60), board (50), etc.
- Permission strings and hierarchy
- Data classification levels

### 7.2 Authentication
- API Key flow
- Azure AD / Microsoft Entra ID flow (planned)
- Session management

### 7.3 Governance
- Forbidden actions, protected config keys
- LLM value validation for feature proposals

## 8. MCP Tools
- List all 44+ tools with brief descriptions
- Grouped by category (Core, Extended, Intelligence, Process, Workforce, Legal, Ops)

## 9. Omnius Multi-Tenant System
- Architecture and tenant isolation
- User management (Roch/REH, Krystian/REF)
- Plugin system
- Operator tasks

## 10. Automation & Self-Healing
### 10.1 Cron Jobs
- Categories and counts
- Key schedules (ingestion, extraction, briefs, analysis)

### 10.2 Webapp AutoFix
- HTTP monitoring, TypeScript error detection
- Claude-powered auto-repair

### 10.3 Code Autofixer (3-tier)
- Tier 1: deterministic (ruff, regex)
- Tier 2: LLM-based (Claude sessions)
- Tier 3: deep research+plan+fix
- Verification pipeline with baseline comparison

### 10.4 Data Guardian
- Pipeline health monitoring
- Self-healing capabilities

## 11. Configuration
### 11.1 Timezone
- Central config: app/config/timezone.py
- APP_TIMEZONE = Europe/Warsaw (CET/CEST)

### 11.2 Environment Variables
- Key env vars and their purpose

### 11.3 Docker Services
- PostgreSQL, Qdrant containers

## 12. Development Workflow
- Code conventions (from CLAUDE.md)
- Pre-commit checks
- Lessons learned system
- Session context and dev logs

## 13. Deployment
- Current: WSL2 local development
- Planned: Hetzner VPS (scripts/deploy_hetzner_cloud.sh)

## 14. Appendix
### A. Database Table List (all tables)
### B. API Endpoint Catalog (all endpoints with methods)
### C. Cron Job Schedule (full list)

## IMPORTANT RULES
- Read actual source files — do NOT invent features that don't exist
- Include exact counts from live metrics
- Use code blocks for schemas, configs, examples
- Be precise about file paths
- Write in English, use Polish only for domain-specific terms (e.g., 'Poranny Brief')
- Target audience: senior engineer joining the project
- This should be THE definitive reference document
" 2>&1 | tee -a "$LOG"

log "Exit code: $?"

# Verify
if [ -f "$DOCS_DIR/ARCHITECTURE.md" ]; then
  lines=$(wc -l < "$DOCS_DIR/ARCHITECTURE.md")
  log "✅ ARCHITECTURE.md generated: $lines lines"
else
  log "❌ ARCHITECTURE.md not generated"
fi

log "=== Technical Documentation Generator — done ==="
