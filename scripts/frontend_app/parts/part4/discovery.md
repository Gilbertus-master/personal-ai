# Part 4: Compliance & Legal — Discovery Report

**Date:** 2026-03-29
**Module:** Compliance & Legal (Matters, Documents, Trainings, Risks, RACI)
**Backend endpoints verified:** 34 (OpenAPI confirmed)

---

## 1. API Endpoint Inventory

### Dashboard & Areas (3 endpoints)

| Method | Path | Params | Response Shape |
|--------|------|--------|----------------|
| GET | `/compliance/dashboard` | — | `{ total_obligations, compliant_count, non_compliant_count, open_matters, overdue_deadlines, at_risk_areas, overall_risk_score }` |
| GET | `/compliance/areas` | — | `{ areas: [{ code, name_pl, name_en, governing_body, key_regulations[], risk_level, responsible_person_id, status }] }` |
| GET | `/compliance/areas/{code}` | path: `code` | Single area + linked obligations, documents, deadlines, risks, raci |

### Matters (8 endpoints)

| Method | Path | Params | Response Shape |
|--------|------|--------|----------------|
| GET | `/compliance/matters` | `?status=&area_code=&priority=&limit=20` | `{ matters: [{ id, title, matter_type, area_code, priority, status, phase, created_at, updated_at }] }` |
| POST | `/compliance/matters` | body: `{ title, matter_type, area_code, description?, priority?, contract_id?, source_regulation? }` | Created matter object |
| GET | `/compliance/matters/{matter_id}` | path: `matter_id` | Full matter: `{ id, title, matter_type, area_code, priority, status, phase, description, legal_analysis, risk_analysis, obligations_report, consequences_report, action_plan[], communication_plan[], source_regulation, created_at, updated_at, completed_at }` |
| POST | `/compliance/matters/{matter_id}/research` | body: `{ query? }` | Research results with legal analysis |
| POST | `/compliance/matters/{matter_id}/advance` | body: `{ force_phase? }` | Updated matter with new phase |
| POST | `/compliance/matters/{matter_id}/report` | — | Formatted compliance report |
| POST | `/compliance/matters/{matter_id}/communication-plan` | — | Communication plan with recipients, channels, timelines |
| POST | `/compliance/matters/{matter_id}/execute-communication` | — | Execution summary with delivery status |

### Obligations (4 endpoints)

| Method | Path | Params | Response Shape |
|--------|------|--------|----------------|
| GET | `/compliance/obligations` | `?area_code=&status=&limit=50` | `{ obligations: [{ id, area_code, title, obligation_type, frequency, next_deadline, responsible_person_id, compliance_status, penalty_description, penalty_max_pln }] }` |
| GET | `/compliance/obligations/overdue` | — | Array of overdue obligations |
| POST | `/compliance/obligations` | body: `{ area_code, title, obligation_type, frequency?, next_deadline?, responsible_person_id?, description?, penalty_description?, penalty_max_pln? }` | Created obligation |
| POST | `/compliance/obligations/{obligation_id}/fulfill` | body: `{ evidence_description? }` | Updated obligation with fulfillment |

### Deadlines (2 endpoints)

| Method | Path | Params | Response Shape |
|--------|------|--------|----------------|
| GET | `/compliance/deadlines` | `?days_ahead=30&area_code=` | `{ deadlines: [{ id, title, date, type, status, recurrence, area_code, area_name }] }` |
| GET | `/compliance/deadlines/overdue` | — | Array of overdue deadlines with days_overdue |

### Documents (5 endpoints)

| Method | Path | Params | Response Shape |
|--------|------|--------|----------------|
| GET | `/compliance/documents` | `?area_code=&doc_type=&status=&limit=50` | `{ documents: [{ id, title, doc_type, area_code, matter_id, version, generated_by, approved_by, approved_at, valid_from, valid_until, review_due, signature_status, status }] }` |
| GET | `/compliance/documents/stale` | `?days=0` | Documents overdue for review |
| POST | `/compliance/documents/generate` | body: `{ matter_id, doc_type, title?, template_hint?, signers?:[{name,role}], valid_months?=12 }` | Generated document with content_text/content_html |
| POST | `/compliance/documents/{doc_id}/approve` | body: `{ approved_by?="sebastian" }` | Updated document status=approved |
| POST | `/compliance/documents/{doc_id}/sign` | body: `{ signer_name }` | Updated signature_status |

### Trainings (4 endpoints)

| Method | Path | Params | Response Shape |
|--------|------|--------|----------------|
| GET | `/compliance/trainings` | `?status=&area_code=&limit=20` | `{ trainings: [{ id, title, area_code, matter_id, training_type, content_summary, target_audience[], deadline, status }] }` |
| GET | `/compliance/trainings/{training_id}/status` | path: `training_id` | Training + records: `[{ person_id, person_name, status, notified_at, completed_at, score }]` |
| POST | `/compliance/trainings` | body: `{ title, area_code, matter_id?, training_type?, content_summary?, target_audience?:[], deadline?, generate_material? }` | Created training |
| POST | `/compliance/trainings/{training_id}/complete` | body: `{ person_id, score? }` | Updated training record |

### Risks (2 endpoints)

| Method | Path | Params | Response Shape |
|--------|------|--------|----------------|
| GET | `/compliance/risks` | `?area_code=&status=open&limit=50` | `{ risks: [{ id, risk_title, risk_description, likelihood, impact, risk_score, color, current_controls, mitigation_plan, status, matter_id, area_code, matter_title }] }` |
| GET | `/compliance/risks/heatmap` | — | `{ areas: [{ code, name, risk_count, avg_score, max_score, critical_count, color }], total_risks, overall_avg }` |

### RACI (2 endpoints)

| Method | Path | Params | Response Shape |
|--------|------|--------|----------------|
| GET | `/compliance/raci` | `?matter_id=&area_code=` | `{ raci: [{ id, area_code, matter_id, person_id, person_name, role, notes }] }` |
| POST | `/compliance/raci` | body: `{ area_code?, matter_id?, person_id, role?="informed", notes? }` | `{ raci_id, person_id, role }` (upsert) |

### Reports (3 endpoints)

| Method | Path | Params | Response Shape |
|--------|------|--------|----------------|
| GET | `/compliance/report/daily` | — | `{ report: "emoji-formatted text" }` (may be null) |
| GET | `/compliance/report/weekly` | — | `{ generated_at, areas: [{ code, name, obligations:{compliant,partially_compliant,non_compliant}, matters:{opened,closed}, deadlines:{met,missed}, documents:{generated,approved}, open_risks }], whatsapp_sent }` |
| GET | `/compliance/report/area/{code}` | path: `code` | Full area report: area info + obligations + matters + documents + deadlines + trainings + risks + raci |

### Scanning (1 endpoint)

| Method | Path | Params | Response Shape |
|--------|------|--------|----------------|
| POST | `/compliance/scan` | `?hours=24` | `{ scanned_chunks, regulatory_found, matters_created, details:[{ title, area_code, matter_type, priority, matter_id, action }] }` |

**Total: 34 endpoints** (23 GET, 11 POST)

---

## 2. RBAC Rules

### Backend Status
**No RBAC decorators on `/compliance/*` endpoints.** These are on the Gilbertus API (port 8000), which has no auth middleware. The Omnius API (separate service) has full RBAC.

### Frontend RBAC (enforced client-side via `@gilbertus/rbac`)

The navigation module for compliance is defined with `roles: ['ceo', 'board', 'director']`.

**Planned access matrix per the module spec:**

| Feature | View | Create/Edit | Notes |
|---------|------|-------------|-------|
| Dashboard | director+ (level ≥ 40) | — | Read-only overview |
| Areas | director+ | — | Reference data |
| Matters list | director+ | board+ (level ≥ 50) | Create/advance/research |
| Matter detail | director+ | board+ | AI research, advance phase |
| Obligations | director+ | board+ | Create, fulfill |
| Deadlines | director+ | — | Calendar view |
| Documents list | director+ | — | View all |
| Documents generate/approve | ceo+ (level ≥ 60) | ceo+ | AI generation, approval, signing |
| Trainings view | director+ | — | |
| Trainings create | board+ | board+ | |
| Training complete | director+ | director+ | Mark person complete |
| Risks | board+ | board+ | Full risk register |
| Risk heatmap | board+ | — | Visual only |
| RACI | board+ | board+ | Set/edit roles |
| Reports | director+ | — | View daily/weekly/area |
| Scan | board+ | board+ | Trigger regulatory scan |

**Implementation:** Use `<RbacGate>` component + `useRole()` hook from `@gilbertus/rbac`.

### Role Hierarchy (from `@gilbertus/rbac`)
```
gilbertus_admin: 99
operator: 70 (infra only, no business data)
ceo: 60
board: 50
director: 40
manager: 30
specialist: 20
```

---

## 3. Existing Patterns to Follow

### API Client (`@gilbertus/api-client`)
- `customFetch<T>(config)` — base HTTP with auto API key header, 401 redirect
- Domain modules: `chat.ts`, `dashboard.ts`, `people.ts`, `intelligence.ts`
- **Create:** `packages/api-client/src/compliance.ts` + `compliance-types.ts`
- Pattern: export async functions per endpoint, typed request/response

### State Management
- **Zustand** for UI state (filters, active tabs, collapsed sections) with `persist()` middleware
- **TanStack React Query v5** for server data (`useQuery`, `useMutation`, `queryClient.invalidateQueries`)
- **Create:** `apps/web/lib/stores/compliance-store.ts` + `apps/web/lib/hooks/use-compliance.ts`

### Components (`@gilbertus/ui`)
- Feature component groups exported from `packages/ui/src/components/compliance/`
- Naming: `PascalCase` files and exports
- Styling: CSS variables (`var(--bg)`, `var(--accent)`, etc.) + `cn()` utility
- Loading: `animate-pulse` skeletons
- Cards: `rounded-lg border border-[var(--border)] bg-[var(--surface)]`

### Page Structure
- Route: `apps/web/app/(app)/compliance/page.tsx` (dashboard)
- Sub-routes: `compliance/matters/page.tsx`, `compliance/matters/[id]/page.tsx`, etc.
- All pages `'use client'`
- Wrap gated content in `<RbacGate roles={[...]}>`

---

## 4. TypeScript Interfaces Needed

### Core Types
```typescript
// Enums
type ComplianceAreaCode = 'URE' | 'RODO' | 'AML' | 'KSH' | 'ESG' | 'LABOR' | 'TAX' | 'CONTRACT' | 'INTERNAL_AUDIT';
type MatterType = 'new_regulation' | 'regulation_change' | 'audit_finding' | 'incident' | 'license_renewal' | 'contract_review' | 'policy_update' | 'training_need' | 'complaint' | 'inspection' | 'risk_assessment' | 'other';
type MatterStatus = 'open' | 'researching' | 'analyzed' | 'action_plan_ready' | 'in_progress' | 'review' | 'completed' | 'closed' | 'on_hold';
type MatterPhase = 'initiation' | 'research' | 'analysis' | 'planning' | 'document_generation' | 'approval' | 'training' | 'communication' | 'verification' | 'monitoring' | 'closed';
type Priority = 'low' | 'medium' | 'high' | 'critical';
type RiskLevel = 'low' | 'medium' | 'high' | 'critical';
type Likelihood = 'very_low' | 'low' | 'medium' | 'high' | 'very_high';
type Impact = 'negligible' | 'minor' | 'moderate' | 'major' | 'catastrophic';
type RiskColor = 'green' | 'yellow' | 'orange' | 'red' | 'critical';
type ObligationType = 'reporting' | 'licensing' | 'documentation' | 'training' | 'audit' | 'notification' | 'registration' | 'inspection' | 'filing' | 'other';
type Frequency = 'one_time' | 'daily' | 'weekly' | 'monthly' | 'quarterly' | 'semi_annual' | 'annual' | 'biennial' | 'on_change' | 'on_demand';
type ComplianceStatus = 'compliant' | 'partially_compliant' | 'non_compliant' | 'unknown' | 'not_applicable';
type DocType = 'policy' | 'procedure' | 'form' | 'template' | 'register' | 'report' | 'certificate' | 'license' | 'contract_annex' | 'training_material' | 'communication' | 'regulation_text' | 'internal_regulation' | 'risk_assessment' | 'audit_report' | 'other';
type DocStatus = 'draft' | 'review' | 'approved' | 'active' | 'superseded' | 'expired' | 'archived';
type SignatureStatus = 'not_required' | 'pending' | 'partially_signed' | 'signed' | 'expired';
type TrainingType = 'mandatory' | 'awareness' | 'certification' | 'refresher' | 'onboarding';
type TrainingStatus = 'planned' | 'material_ready' | 'scheduled' | 'in_progress' | 'completed' | 'cancelled';
type TrainingRecordStatus = 'assigned' | 'notified' | 'started' | 'completed' | 'overdue' | 'exempted';
type DeadlineType = 'filing' | 'reporting' | 'license_renewal' | 'audit' | 'training' | 'review' | 'inspection' | 'payment' | 'document_expiry' | 'contract' | 'custom';
type DeadlineStatus = 'pending' | 'in_progress' | 'completed' | 'overdue' | 'cancelled';
type RaciRole = 'responsible' | 'accountable' | 'consulted' | 'informed';
type RiskStatus = 'open' | 'mitigated' | 'accepted' | 'closed';

// Main entities
interface ComplianceArea { code: ComplianceAreaCode; name_pl: string; name_en: string; governing_body: string; key_regulations: string[]; risk_level: RiskLevel; responsible_person_id: number; status: string; }
interface ComplianceMatter { id: number; title: string; matter_type: MatterType; area_code: string; priority: Priority; status: MatterStatus; phase: MatterPhase; description?: string; legal_analysis?: string; risk_analysis?: Record<string, unknown>; obligations_report?: string; consequences_report?: string; action_plan?: Record<string, unknown>[]; communication_plan?: Record<string, unknown>[]; source_regulation?: string; created_at: string; updated_at: string; completed_at?: string; }
interface ComplianceObligation { id: number; area_code: string; title: string; obligation_type: ObligationType; frequency: Frequency; next_deadline?: string; responsible_person_id?: number; compliance_status: ComplianceStatus; penalty_description?: string; penalty_max_pln?: number; created_at: string; }
interface ComplianceDeadline { id: number; title: string; date: string; type: DeadlineType; status: DeadlineStatus; recurrence: string; area_code: string; area_name: string; days_overdue?: number; }
interface ComplianceDocument { id: number; title: string; doc_type: DocType; area_code: string; matter_id?: number; version: number; generated_by: string; approved_by?: string; approved_at?: string; valid_from?: string; valid_until?: string; review_due?: string; signature_status: SignatureStatus; status: DocStatus; created_at: string; }
interface ComplianceTraining { id: number; title: string; area_code: string; matter_id?: number; training_type: TrainingType; content_summary?: string; target_audience: string[]; deadline?: string; status: TrainingStatus; created_at: string; }
interface TrainingRecord { person_id: number; person_name: string; status: TrainingRecordStatus; notified_at?: string; completed_at?: string; score?: number; }
interface ComplianceRisk { id: number; risk_title: string; risk_description?: string; likelihood: Likelihood; impact: Impact; risk_score: number; color: RiskColor; current_controls?: string; mitigation_plan?: string; status: RiskStatus; matter_id?: number; area_code: string; matter_title?: string; created_at: string; }
interface RaciEntry { id: number; area_code?: string; matter_id?: number; person_id: number; person_name: string; role: RaciRole; notes?: string; }
interface ComplianceDashboard { total_obligations: number; compliant_count: number; non_compliant_count: number; open_matters: number; overdue_deadlines: number; at_risk_areas: number; overall_risk_score: number; }
interface RiskHeatmapArea { code: string; name: string; risk_count: number; avg_score: number; max_score: number; critical_count: number; color: RiskColor; }
```

---

## 5. Backend Gaps & Notes

### No Gaps for Core Features
All 34 endpoints exist and are confirmed via OpenAPI. The API surface fully covers the module spec.

### Extra Endpoints (beyond spec)
- `POST /compliance/scan` — regulatory scanning (trigger manually)
- `POST /compliance/matters/{id}/communication-plan` — generate comms plan
- `POST /compliance/matters/{id}/execute-communication` — send comms via WhatsApp/email/Teams
- `GET /compliance/trainings/{id}/status` — per-person breakdown

### No SSE/WebSocket Needed
All endpoints are synchronous REST. AI operations (research, document generation) may take 5-15s but return inline.

### Missing on Backend
1. **No pagination metadata** — endpoints return arrays with `limit` param but no `total_count` or `offset`/`cursor`
2. **No PATCH/PUT** — matters, obligations, documents cannot be directly edited (only advanced via workflow)
3. **No DELETE** — nothing can be deleted (by design: audit trail)
4. **No bulk operations** — no batch fulfill, batch approve
5. **No search/fulltext** — filtering by exact fields only, no free-text search across matters

### AI-Powered Operations (slow, show loading)
- `POST /compliance/matters/{id}/research` — Claude Sonnet, ~10-15s
- `POST /compliance/documents/generate` — Claude Sonnet, ~10-20s
- `POST /compliance/matters/{id}/report` — Claude Sonnet, ~5-10s
- `POST /compliance/scan` — Claude Haiku per chunk, variable time

---

## 6. Complexity Estimate

| Feature | Complexity | Components | Notes |
|---------|-----------|------------|-------|
| **Dashboard** | Medium | KPI cards, area status grid, overdue counters | 9 areas, color-coded risk levels |
| **Matters list** | Medium | Filterable table, status/priority badges, phase indicator | 3 filter dimensions + create modal |
| **Matter detail** | Complex | Multi-section page: info, analysis, action plan, comms, phase stepper | AI actions (research/advance/report), phase workflow visualization |
| **Obligations** | Medium | Table with compliance status badges, fulfill action, overdue highlights | Deadline-aware styling |
| **Deadlines** | Medium | Calendar/timeline view, color-coded urgency | Need date-grid or timeline component |
| **Documents** | Medium | Table with status workflow, generate modal, approve/sign actions | AI generation (loading states important) |
| **Trainings** | Medium | Table + detail with per-person status breakdown | Person completion grid |
| **Risks** | Complex | List + 5×5 heatmap matrix visualization | Interactive probability×impact grid |
| **RACI** | Medium | Matrix grid: people × areas/obligations × R/A/C/I | Editable cells, bulk assignment |
| **Reports** | Simple | On-demand report generation, formatted display | 3 report types, pre-formatted text |
| **Regulatory Scan** | Simple | Trigger button + results display | Manual action, show scan results |

### Total estimate: ~25-30 components, ~15 pages/sub-pages

---

## 7. Recommended File Structure

```
packages/api-client/src/
  compliance.ts              # API functions
  compliance-types.ts        # TypeScript interfaces

apps/web/lib/
  stores/compliance-store.ts # Zustand UI state
  hooks/use-compliance.ts    # React Query hooks

packages/ui/src/components/compliance/
  index.ts
  # Dashboard
  ComplianceDashboard.tsx    # KPI grid + area status
  AreaStatusCard.tsx         # Single area card
  # Matters
  MattersTable.tsx           # Filterable matters list
  MatterDetail.tsx           # Full matter view
  PhaseTimeline.tsx          # Phase progress stepper
  MatterActions.tsx          # Research/advance/report buttons
  CreateMatterModal.tsx      # New matter form
  # Obligations
  ObligationsTable.tsx       # Obligations list
  FulfillModal.tsx           # Fulfill with evidence
  # Deadlines
  DeadlineCalendar.tsx       # Calendar/timeline view
  # Documents
  DocumentsTable.tsx         # Documents list
  GenerateDocModal.tsx       # AI document generation
  DocumentActions.tsx        # Approve/sign actions
  # Trainings
  TrainingsTable.tsx         # Trainings list
  TrainingStatusGrid.tsx     # Per-person completion
  CreateTrainingModal.tsx    # New training form
  # Risks
  RisksTable.tsx             # Risk register
  RiskHeatmap.tsx            # 5×5 matrix visualization
  # RACI
  RaciMatrix.tsx             # Editable RACI grid
  # Reports
  ReportViewer.tsx           # Formatted report display
  # Shared
  ComplianceBadge.tsx        # Status/priority/phase badges
  AreaFilter.tsx             # Area code dropdown

apps/web/app/(app)/compliance/
  page.tsx                   # Dashboard
  matters/page.tsx           # Matters list
  matters/[id]/page.tsx      # Matter detail
  obligations/page.tsx       # Obligations
  deadlines/page.tsx         # Deadlines calendar
  documents/page.tsx         # Documents
  trainings/page.tsx         # Trainings
  trainings/[id]/page.tsx    # Training detail (per-person)
  risks/page.tsx             # Risks + heatmap
  raci/page.tsx              # RACI matrix
  reports/page.tsx           # Reports
```

---

## 8. Key Design Decisions

1. **Phase stepper** for matters — most complex UI element, 11 phases with visual progress
2. **Risk heatmap** — 5×5 grid (likelihood × impact), color-coded cells, interactive
3. **RACI matrix** — people as rows, areas/obligations as columns, R/A/C/I as cell values
4. **AI actions** need prominent loading states (10-20s operations)
5. **No inline editing** — backend is workflow-driven (advance phases, fulfill, approve)
6. **Deadline calendar** — simple date grid with color urgency, not a full calendar lib
7. **Polish-first** — all legal content is in Polish, UI labels bilingual via i18n
