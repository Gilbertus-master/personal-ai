# Part 4: Compliance & Legal — Architecture Plan

**Module:** Compliance Dashboard, Matters, Obligations, Deadlines, Documents, Trainings, Risks, RACI, Reports
**Date:** 2026-03-29

---

## 1. Component Tree (Visual Hierarchy)

```
AppLayout (existing)
├── Sidebar (existing — /compliance link in nav, roles: ceo, board, director)
└── <main>
    │
    ├── /compliance (page.tsx) ──────────────────────────────────────
    │   │
    │   ├── RbacGate [ceo, board, director]
    │   │   └── COMPLIANCE DASHBOARD
    │   │       │
    │   │       ├── PageHeader ("Compliance" + overall_risk_score badge)
    │   │       │
    │   │       ├── KpiRow (4 cards from GET /compliance/dashboard)
    │   │       │   ├── KpiCard "Obowiązki" (compliant_count / total_obligations)
    │   │       │   ├── KpiCard "Sprawy otwarte" (open_matters)
    │   │       │   ├── KpiCard "Zaległe terminy" (overdue_deadlines, red if > 0)
    │   │       │   └── KpiCard "Ryzyko ogólne" (overall_risk_score, color-coded)
    │   │       │
    │   │       ├── AreaStatusGrid (from GET /compliance/areas)
    │   │       │   └── AreaStatusCard[] (9 areas, clickable → /compliance/areas/{code})
    │   │       │       ├── Area name (name_pl)
    │   │       │       ├── Risk level badge (color-coded)
    │   │       │       ├── Governing body
    │   │       │       └── Key regulations (truncated list)
    │   │       │
    │   │       └── QuickLinks
    │   │           ├── Link → /compliance/matters
    │   │           ├── Link → /compliance/obligations
    │   │           ├── Link → /compliance/deadlines
    │   │           ├── Link → /compliance/documents
    │   │           ├── Link → /compliance/trainings
    │   │           ├── Link → /compliance/risks
    │   │           ├── Link → /compliance/raci
    │   │           └── Link → /compliance/reports
    │   │
    │   └── RbacGate [manager, specialist] → AccessDenied
    │
    ├── /compliance/areas/[code] (page.tsx) ─────────────────────────
    │   │
    │   └── RbacGate [ceo, board, director]
    │       └── AREA DETAIL
    │           │
    │           ├── AreaHeader (name_pl, governing_body, risk_level badge)
    │           │
    │           └── AreaTabs
    │               ├── "Przegląd" — Summary stats from GET /compliance/areas/{code}
    │               ├── "Obowiązki" — Filtered obligations for this area
    │               ├── "Sprawy" — Filtered matters for this area
    │               ├── "Dokumenty" — Filtered documents for this area
    │               ├── "Terminy" — Filtered deadlines for this area
    │               ├── "Szkolenia" — Filtered trainings for this area
    │               ├── "Ryzyka" — Filtered risks for this area
    │               └── "RACI" — Filtered RACI for this area
    │
    ├── /compliance/matters (page.tsx) ──────────────────────────────
    │   │
    │   ├── RbacGate [ceo, board, director]
    │   │   └── MATTERS LIST
    │   │       │
    │   │       ├── PageHeader ("Sprawy compliance")
    │   │       │   └── RbacGate [ceo, board]
    │   │       │       └── CreateMatterButton → opens CreateMatterModal
    │   │       │
    │   │       ├── MattersToolbar
    │   │       │   ├── FilterChip: status (open, researching, analyzed, in_progress, etc.)
    │   │       │   ├── FilterChip: area_code (URE, RODO, AML, etc.)
    │   │       │   └── FilterChip: priority (low, medium, high, critical)
    │   │       │
    │   │       └── MattersTable
    │   │           └── MatterRow[] (clickable → /compliance/matters/{id})
    │   │               ├── Title
    │   │               ├── Type badge (matter_type)
    │   │               ├── Area badge (area_code, color-coded)
    │   │               ├── Priority badge (critical=red, high=orange, medium=yellow, low=green)
    │   │               ├── Status badge
    │   │               ├── Phase indicator (current phase name)
    │   │               └── Updated date
    │   │
    │   └── CreateMatterModal
    │       ├── Title input
    │       ├── MatterType select
    │       ├── AreaCode select
    │       ├── Priority select
    │       ├── Description textarea (optional)
    │       └── SourceRegulation input (optional)
    │
    ├── /compliance/matters/[id] (page.tsx) ─────────────────────────
    │   │
    │   ├── RbacGate [ceo, board, director]
    │   │   └── MATTER DETAIL
    │   │       │
    │   │       ├── MatterHeader
    │   │       │   ├── Title + priority badge + status badge
    │   │       │   ├── Area badge + matter_type badge
    │   │       │   └── Dates (created_at, updated_at, completed_at)
    │   │       │
    │   │       ├── PhaseTimeline (11 phases, horizontal stepper)
    │   │       │   └── PhaseStep[] (initiation → research → ... → closed)
    │   │       │       ├── Step icon (completed/current/future)
    │   │       │       ├── Phase name
    │   │       │       └── Current phase highlighted with accent
    │   │       │
    │   │       ├── MatterActions (board+)
    │   │       │   ├── ResearchButton → POST /matters/{id}/research (~10-15s, loading)
    │   │       │   ├── AdvanceButton → POST /matters/{id}/advance
    │   │       │   ├── ReportButton → POST /matters/{id}/report (~5-10s, loading)
    │   │       │   ├── CommPlanButton → POST /matters/{id}/communication-plan
    │   │       │   └── ExecuteCommButton → POST /matters/{id}/execute-communication
    │   │       │
    │   │       └── MatterTabs
    │   │           ├── "Przegląd" — description, source_regulation
    │   │           ├── "Analiza" — legal_analysis (markdown), risk_analysis (JSON rendered)
    │   │           ├── "Plan działań" — action_plan[] (checklist-style)
    │   │           ├── "Komunikacja" — communication_plan[] (recipients, channels)
    │   │           └── "Raport" — obligations_report, consequences_report
    │   │
    │   └── RbacGate [manager, specialist] → AccessDenied
    │
    ├── /compliance/obligations (page.tsx) ──────────────────────────
    │   │
    │   └── RbacGate [ceo, board, director]
    │       └── OBLIGATIONS LIST
    │           │
    │           ├── PageHeader ("Obowiązki compliance")
    │           │   └── RbacGate [ceo, board]
    │           │       └── CreateObligationButton (inline modal)
    │           │
    │           ├── ObligationsToolbar
    │           │   ├── FilterChip: area_code
    │           │   ├── FilterChip: compliance_status
    │           │   └── ToggleOverdueOnly
    │           │
    │           └── ObligationsTable
    │               └── ObligationRow[]
    │                   ├── Title
    │                   ├── Area badge
    │                   ├── Type badge (obligation_type)
    │                   ├── Frequency
    │                   ├── Next deadline (red if overdue)
    │                   ├── ComplianceStatus badge (compliant=green, non_compliant=red)
    │                   ├── Penalty (penalty_max_pln formatted)
    │                   └── RbacGate [ceo, board]
    │                       └── FulfillButton → opens FulfillModal
    │
    ├── /compliance/deadlines (page.tsx) ────────────────────────────
    │   │
    │   └── RbacGate [ceo, board, director]
    │       └── DEADLINES VIEW
    │           │
    │           ├── PageHeader ("Terminy compliance")
    │           │
    │           ├── DeadlineFilters
    │           │   ├── DaysAhead slider (7/14/30/60/90)
    │           │   └── AreaCode filter
    │           │
    │           └── DeadlineCalendar
    │               ├── OverdueSection (red, always on top)
    │               │   └── DeadlineItem[] (from GET /deadlines/overdue)
    │               └── UpcomingSection (grouped by week)
    │                   └── DeadlineItem[] (from GET /deadlines?days_ahead=N)
    │                       ├── Date (formatted, color by urgency)
    │                       ├── Title
    │                       ├── Type badge
    │                       ├── Status badge
    │                       ├── Area badge
    │                       └── Urgency indicator (days remaining)
    │
    ├── /compliance/documents (page.tsx) ────────────────────────────
    │   │
    │   └── RbacGate [ceo, board, director]
    │       └── DOCUMENTS LIST
    │           │
    │           ├── PageHeader ("Dokumenty compliance")
    │           │   └── RbacGate [ceo]
    │           │       └── GenerateDocButton → opens GenerateDocModal
    │           │
    │           ├── DocumentsToolbar
    │           │   ├── FilterChip: area_code
    │           │   ├── FilterChip: doc_type
    │           │   ├── FilterChip: status (draft, approved, active, etc.)
    │           │   └── ToggleStaleOnly (from GET /documents/stale)
    │           │
    │           └── DocumentsTable
    │               └── DocumentRow[]
    │                   ├── Title + version badge
    │                   ├── DocType badge
    │                   ├── Area badge
    │                   ├── Status badge (draft/review/approved/active/expired)
    │                   ├── SignatureStatus badge
    │                   ├── Valid dates (from → until, red if expired)
    │                   ├── Review due (red if overdue)
    │                   └── RbacGate [ceo]
    │                       └── DocumentActions
    │                           ├── ApproveButton → POST /documents/{id}/approve
    │                           └── SignButton → POST /documents/{id}/sign (modal for signer_name)
    │
    │           └── GenerateDocModal (ceo only)
    │               ├── MatterId select (from matters list)
    │               ├── DocType select
    │               ├── Title input (optional)
    │               ├── TemplateHint textarea (optional)
    │               ├── Signers repeater (name + role pairs)
    │               ├── ValidMonths input (default 12)
    │               └── GenerateButton → POST /documents/generate (~10-20s, loading)
    │
    ├── /compliance/trainings (page.tsx) ────────────────────────────
    │   │
    │   └── RbacGate [ceo, board, director]
    │       └── TRAININGS LIST
    │           │
    │           ├── PageHeader ("Szkolenia compliance")
    │           │   └── RbacGate [ceo, board]
    │           │       └── CreateTrainingButton → opens CreateTrainingModal
    │           │
    │           ├── TrainingsToolbar
    │           │   ├── FilterChip: area_code
    │           │   └── FilterChip: status
    │           │
    │           └── TrainingsTable
    │               └── TrainingRow[] (clickable → /compliance/trainings/{id})
    │                   ├── Title
    │                   ├── Area badge
    │                   ├── TrainingType badge
    │                   ├── Target audience (chips)
    │                   ├── Deadline (red if past)
    │                   └── Status badge
    │
    ├── /compliance/trainings/[id] (page.tsx) ───────────────────────
    │   │
    │   └── RbacGate [ceo, board, director]
    │       └── TRAINING DETAIL
    │           │
    │           ├── TrainingHeader (title, area, type, deadline, status)
    │           ├── ContentSummary (markdown render of content_summary)
    │           │
    │           └── TrainingStatusGrid (from GET /trainings/{id}/status)
    │               └── PersonRow[]
    │                   ├── Person name
    │                   ├── Status badge (assigned/notified/started/completed/overdue)
    │                   ├── Notified date
    │                   ├── Completed date
    │                   ├── Score (if any)
    │                   └── RbacGate [ceo, board, director]
    │                       └── CompleteButton → POST /trainings/{id}/complete
    │
    ├── /compliance/risks (page.tsx) ────────────────────────────────
    │   │
    │   └── RbacGate [ceo, board]
    │       └── RISKS VIEW
    │           │
    │           ├── PageHeader ("Rejestr ryzyk")
    │           │
    │           ├── RiskTabs
    │           │   │
    │           │   ├── "Rejestr" — RisksTable
    │           │   │   ├── RiskToolbar
    │           │   │   │   ├── FilterChip: area_code
    │           │   │   │   └── FilterChip: status (open, mitigated, accepted, closed)
    │           │   │   └── RiskRow[]
    │           │   │       ├── Risk title
    │           │   │       ├── Area badge
    │           │   │       ├── Likelihood badge
    │           │   │       ├── Impact badge
    │           │   │       ├── Risk score (number, color-coded)
    │           │   │       ├── Status badge
    │           │   │       ├── Current controls (truncated)
    │           │   │       └── Mitigation plan (truncated)
    │           │   │
    │           │   └── "Heatmap" — RiskHeatmap
    │           │       └── HeatmapGrid (5×5 matrix)
    │           │           ├── X-axis: Impact (negligible → catastrophic)
    │           │           ├── Y-axis: Likelihood (very_low → very_high)
    │           │           ├── Cells: count of risks, color intensity
    │           │           └── AreaSummary below (per-area risk stats)
    │           │               └── AreaRiskCard[]
    │           │                   ├── Area name
    │           │                   ├── Risk count
    │           │                   ├── Avg score
    │           │                   ├── Max score
    │           │                   └── Critical count (red if > 0)
    │
    ├── /compliance/raci (page.tsx) ─────────────────────────────────
    │   │
    │   └── RbacGate [ceo, board]
    │       └── RACI MATRIX
    │           │
    │           ├── PageHeader ("Matryca RACI")
    │           │
    │           ├── RaciFilters
    │           │   └── FilterChip: area_code (or show all)
    │           │
    │           └── RaciMatrix
    │               ├── Header row: person names (columns)
    │               ├── Left column: areas/matters (rows)
    │               └── Cells: RaciRole badge (R/A/C/I)
    │                   └── Clickable cell → RaciEditPopover
    │                       ├── Role selector (R/A/C/I/remove)
    │                       ├── Notes input
    │                       └── SaveButton → POST /compliance/raci
    │
    ├── /compliance/reports (page.tsx) ──────────────────────────────
    │   │
    │   └── RbacGate [ceo, board, director]
    │       └── REPORTS VIEW
    │           │
    │           ├── PageHeader ("Raporty compliance")
    │           │
    │           └── ReportTabs
    │               ├── "Dzienny" — DailyReport (GET /report/daily)
    │               │   └── Formatted text (emoji-rich, markdown)
    │               ├── "Tygodniowy" — WeeklyReport (GET /report/weekly)
    │               │   └── AreaReport[] (per-area compliance stats)
    │               └── "Obszar" — AreaReport (GET /report/area/{code})
    │                   ├── AreaSelector dropdown
    │                   └── Full area report (all sections)
    │
    └── /compliance/scan (page.tsx) ─────────────────────────────────
        │
        └── RbacGate [ceo, board]
            └── REGULATORY SCAN
                │
                ├── PageHeader ("Skan regulacyjny")
                ├── HoursSelector (6/12/24/48/72)
                ├── ScanButton → POST /compliance/scan
                ├── LoadingState (variable time)
                └── ScanResults
                    ├── Summary (scanned_chunks, regulatory_found, matters_created)
                    └── DetailsList
                        └── ScanResultItem[]
                            ├── Title
                            ├── Area badge
                            ├── MatterType badge
                            ├── Priority badge
                            └── Action taken
```

---

## 2. File Tree (Every File Path)

```
frontend/
├── packages/
│   ├── api-client/src/
│   │   ├── compliance-types.ts        ← All TypeScript types (34 type aliases + 15 interfaces)
│   │   ├── compliance.ts             ← 34 API client functions
│   │   └── index.ts                   ← (UPDATE: add compliance exports)
│   │
│   └── ui/src/components/
│       └── compliance/
│           ├── index.ts
│           ├── compliance-dashboard.tsx    ← KPI row + area status grid
│           ├── area-status-card.tsx        ← Single area card
│           ├── matters-table.tsx           ← Filterable matters list + toolbar
│           ├── matter-detail.tsx           ← Full matter view with tabs
│           ├── phase-timeline.tsx          ← 11-phase horizontal stepper
│           ├── matter-actions.tsx          ← Research/advance/report buttons
│           ├── create-matter-modal.tsx     ← New matter form modal
│           ├── obligations-table.tsx       ← Obligations list + fulfill action
│           ├── fulfill-modal.tsx           ← Fulfill with evidence modal
│           ├── deadline-calendar.tsx       ← Timeline view with urgency colors
│           ├── documents-table.tsx         ← Documents list + actions
│           ├── generate-doc-modal.tsx      ← AI document generation form
│           ├── document-actions.tsx        ← Approve/sign buttons
│           ├── trainings-table.tsx         ← Trainings list
│           ├── training-status-grid.tsx    ← Per-person completion tracker
│           ├── create-training-modal.tsx   ← New training form modal
│           ├── risks-table.tsx            ← Risk register table
│           ├── risk-heatmap.tsx           ← 5×5 probability×impact matrix
│           ├── raci-matrix.tsx            ← Editable RACI grid
│           ├── report-viewer.tsx          ← Formatted report display
│           ├── compliance-badge.tsx       ← Status/priority/phase/risk badges
│           └── area-filter.tsx            ← Reusable area code dropdown
│
├── apps/web/
│   ├── app/(app)/
│   │   └── compliance/
│   │       ├── page.tsx                ← Dashboard page
│   │       ├── areas/
│   │       │   └── [code]/
│   │       │       └── page.tsx        ← Area detail page
│   │       ├── matters/
│   │       │   ├── page.tsx            ← Matters list page
│   │       │   └── [id]/
│   │       │       └── page.tsx        ← Matter detail page
│   │       ├── obligations/
│   │       │   └── page.tsx            ← Obligations page
│   │       ├── deadlines/
│   │       │   └── page.tsx            ← Deadlines page
│   │       ├── documents/
│   │       │   └── page.tsx            ← Documents page
│   │       ├── trainings/
│   │       │   ├── page.tsx            ← Trainings list page
│   │       │   └── [id]/
│   │       │       └── page.tsx        ← Training detail page
│   │       ├── risks/
│   │       │   └── page.tsx            ← Risks + heatmap page
│   │       ├── raci/
│   │       │   └── page.tsx            ← RACI matrix page
│   │       ├── reports/
│   │       │   └── page.tsx            ← Reports page
│   │       └── scan/
│   │           └── page.tsx            ← Regulatory scan page
│   │
│   └── lib/
│       ├── hooks/
│       │   └── use-compliance.ts       ← 25+ React Query hooks
│       │
│       └── stores/
│           └── compliance-store.ts     ← Zustand UI state
```

---

## 3. API Integration Map (Component → Endpoint)

### Dashboard

| Component | Endpoint | Method | Trigger |
|-----------|----------|--------|---------|
| ComplianceDashboard KPIs | `GET /compliance/dashboard` | useQuery | Page load |
| AreaStatusGrid | `GET /compliance/areas` | useQuery | Page load |
| AreaStatusCard → link | — | Navigation | Click → /compliance/areas/{code} |

### Areas

| Component | Endpoint | Method | Trigger |
|-----------|----------|--------|---------|
| AreaDetail | `GET /compliance/areas/{code}` | useQuery | Page load |

### Matters

| Component | Endpoint | Method | Trigger |
|-----------|----------|--------|---------|
| MattersTable | `GET /compliance/matters` | useQuery | Page load, filter change |
| CreateMatterModal | `POST /compliance/matters` | useMutation | Form submit |
| MatterDetail | `GET /compliance/matters/{id}` | useQuery | Page load |
| ResearchButton | `POST /compliance/matters/{id}/research` | useMutation | Click (~10-15s) |
| AdvanceButton | `POST /compliance/matters/{id}/advance` | useMutation | Click |
| ReportButton | `POST /compliance/matters/{id}/report` | useMutation | Click (~5-10s) |
| CommPlanButton | `POST /compliance/matters/{id}/communication-plan` | useMutation | Click |
| ExecuteCommButton | `POST /compliance/matters/{id}/execute-communication` | useMutation | Click |

### Obligations

| Component | Endpoint | Method | Trigger |
|-----------|----------|--------|---------|
| ObligationsTable | `GET /compliance/obligations` | useQuery | Page load, filter change |
| OverdueToggle | `GET /compliance/obligations/overdue` | useQuery | Toggle on |
| CreateObligation | `POST /compliance/obligations` | useMutation | Form submit |
| FulfillModal | `POST /compliance/obligations/{id}/fulfill` | useMutation | Click |

### Deadlines

| Component | Endpoint | Method | Trigger |
|-----------|----------|--------|---------|
| DeadlineCalendar (overdue) | `GET /compliance/deadlines/overdue` | useQuery | Page load |
| DeadlineCalendar (upcoming) | `GET /compliance/deadlines` | useQuery | Page load, days_ahead change |

### Documents

| Component | Endpoint | Method | Trigger |
|-----------|----------|--------|---------|
| DocumentsTable | `GET /compliance/documents` | useQuery | Page load, filter change |
| StaleToggle | `GET /compliance/documents/stale` | useQuery | Toggle on |
| GenerateDocModal | `POST /compliance/documents/generate` | useMutation | Form submit (~10-20s) |
| ApproveButton | `POST /compliance/documents/{id}/approve` | useMutation | Click |
| SignButton | `POST /compliance/documents/{id}/sign` | useMutation | Click |

### Trainings

| Component | Endpoint | Method | Trigger |
|-----------|----------|--------|---------|
| TrainingsTable | `GET /compliance/trainings` | useQuery | Page load, filter change |
| CreateTrainingModal | `POST /compliance/trainings` | useMutation | Form submit |
| TrainingStatusGrid | `GET /compliance/trainings/{id}/status` | useQuery | Page load |
| CompleteButton | `POST /compliance/trainings/{id}/complete` | useMutation | Click |

### Risks

| Component | Endpoint | Method | Trigger |
|-----------|----------|--------|---------|
| RisksTable | `GET /compliance/risks` | useQuery | Page load, filter change |
| RiskHeatmap | `GET /compliance/risks/heatmap` | useQuery | Tab select |

### RACI

| Component | Endpoint | Method | Trigger |
|-----------|----------|--------|---------|
| RaciMatrix | `GET /compliance/raci` | useQuery | Page load, filter change |
| RaciEditPopover | `POST /compliance/raci` | useMutation | Save click |

### Reports

| Component | Endpoint | Method | Trigger |
|-----------|----------|--------|---------|
| DailyReport | `GET /compliance/report/daily` | useQuery | Tab select |
| WeeklyReport | `GET /compliance/report/weekly` | useQuery | Tab select |
| AreaReport | `GET /compliance/report/area/{code}` | useQuery | Area select |

### Scan

| Component | Endpoint | Method | Trigger |
|-----------|----------|--------|---------|
| ScanButton | `POST /compliance/scan` | useMutation | Click |

---

## 4. RBAC per View/Component

| View | Roles | Gate Type |
|------|-------|-----------|
| `/compliance` dashboard | ceo, board, director | Page-level RbacGate |
| `/compliance/areas/[code]` | ceo, board, director | Page-level RbacGate |
| `/compliance/matters` list | ceo, board, director | Page-level RbacGate |
| Create matter button | ceo, board | Component-level RbacGate |
| `/compliance/matters/[id]` detail | ceo, board, director | Page-level RbacGate |
| Matter actions (research/advance/report) | ceo, board | Component-level RbacGate |
| `/compliance/obligations` | ceo, board, director | Page-level RbacGate |
| Create obligation | ceo, board | Component-level RbacGate |
| Fulfill obligation | ceo, board | Button visibility |
| `/compliance/deadlines` | ceo, board, director | Page-level RbacGate |
| `/compliance/documents` | ceo, board, director | Page-level RbacGate |
| Generate document | ceo | Component-level RbacGate |
| Approve/sign document | ceo | Button visibility |
| `/compliance/trainings` | ceo, board, director | Page-level RbacGate |
| Create training | ceo, board | Component-level RbacGate |
| Complete training | ceo, board, director | Button visibility |
| `/compliance/trainings/[id]` | ceo, board, director | Page-level RbacGate |
| `/compliance/risks` | ceo, board | Page-level RbacGate |
| `/compliance/raci` | ceo, board | Page-level RbacGate |
| RACI edit | ceo, board | Cell-level RbacGate |
| `/compliance/reports` | ceo, board, director | Page-level RbacGate |
| `/compliance/scan` | ceo, board | Page-level RbacGate |

---

## 5. State Management (Zustand Store Shape)

### compliance-store.ts

```typescript
interface ComplianceStore {
  // Matters filters
  matterStatus: string | null;
  matterArea: string | null;
  matterPriority: string | null;
  matterDetailTab: 'overview' | 'analysis' | 'action_plan' | 'communication' | 'report';

  // Obligations filters
  obligationArea: string | null;
  obligationStatus: string | null;
  showOverdueOnly: boolean;

  // Deadlines
  daysAhead: number;  // default 30
  deadlineArea: string | null;

  // Documents filters
  docArea: string | null;
  docType: string | null;
  docStatus: string | null;
  showStaleOnly: boolean;

  // Trainings filters
  trainingArea: string | null;
  trainingStatus: string | null;

  // Risks
  riskArea: string | null;
  riskStatus: string | null;
  riskActiveTab: 'register' | 'heatmap';

  // RACI
  raciArea: string | null;

  // Reports
  reportActiveTab: 'daily' | 'weekly' | 'area';
  reportAreaCode: string | null;

  // Area detail
  areaDetailTab: 'overview' | 'obligations' | 'matters' | 'documents' | 'deadlines' | 'trainings' | 'risks' | 'raci';

  // Actions
  setMatterStatus: (s: string | null) => void;
  setMatterArea: (a: string | null) => void;
  setMatterPriority: (p: string | null) => void;
  setMatterDetailTab: (t: string) => void;
  setObligationArea: (a: string | null) => void;
  setObligationStatus: (s: string | null) => void;
  toggleOverdueOnly: () => void;
  setDaysAhead: (d: number) => void;
  setDeadlineArea: (a: string | null) => void;
  setDocArea: (a: string | null) => void;
  setDocType: (t: string | null) => void;
  setDocStatus: (s: string | null) => void;
  toggleStaleOnly: () => void;
  setTrainingArea: (a: string | null) => void;
  setTrainingStatus: (s: string | null) => void;
  setRiskArea: (a: string | null) => void;
  setRiskStatus: (s: string | null) => void;
  setRiskActiveTab: (t: 'register' | 'heatmap') => void;
  setRaciArea: (a: string | null) => void;
  setReportActiveTab: (t: 'daily' | 'weekly' | 'area') => void;
  setReportAreaCode: (c: string | null) => void;
  setAreaDetailTab: (t: string) => void;
  resetAllFilters: () => void;
}
```

Persist key: `gilbertus-compliance`

---

## 6. UX Flows

### Flow 1: Compliance Dashboard Overview
1. User navigates to `/compliance`
2. Dashboard loads → parallel: GET /compliance/dashboard + GET /compliance/areas
3. KPI cards show overall compliance health (red highlights if non-compliant or overdue)
4. Area grid shows 9 compliance areas with risk-level colors
5. User clicks area card → navigate to `/compliance/areas/{code}`
6. User clicks quick-link → navigate to specific sub-page

### Flow 2: Matter Lifecycle
1. Board+ user navigates to `/compliance/matters`
2. Matters list loads with filters (GET /compliance/matters?limit=20)
3. User clicks "Nowa sprawa" → CreateMatterModal opens
4. Fills title, type, area, priority → POST /compliance/matters → success toast → refetch
5. Clicks matter row → navigate to `/compliance/matters/{id}`
6. PhaseTimeline shows current phase (e.g., "research")
7. User clicks "Zbadaj" → POST /matters/{id}/research → 10-15s loading spinner → results appear in Analysis tab
8. User clicks "Następna faza" → POST /matters/{id}/advance → phase advances, timeline updates
9. User clicks "Generuj raport" → POST /matters/{id}/report → 5-10s → report appears in Report tab
10. User clicks "Plan komunikacji" → POST /matters/{id}/communication-plan → recipients/channels shown
11. User clicks "Wyślij komunikację" → POST /matters/{id}/execute-communication → delivery status

### Flow 3: Document Generation & Approval (CEO only)
1. CEO navigates to `/compliance/documents`
2. Documents list loads (GET /compliance/documents)
3. Toggles "Przeterminowane" → shows stale docs (GET /documents/stale)
4. Clicks "Generuj dokument" → GenerateDocModal opens
5. Selects matter, doc_type, adds signers → POST /documents/generate
6. 10-20s loading with progress indicator → generated doc appears in list
7. Clicks "Zatwierdź" on a document → POST /documents/{id}/approve → status changes to "approved"
8. Clicks "Podpisz" → signer_name modal → POST /documents/{id}/sign → signature_status updates

### Flow 4: Risk Assessment
1. Board+ user navigates to `/compliance/risks`
2. Default "Rejestr" tab loads (GET /compliance/risks)
3. User filters by area_code → refetch
4. User switches to "Heatmap" tab → GET /compliance/risks/heatmap
5. 5×5 matrix renders: likelihood (Y) × impact (X), cells colored by risk density
6. Below: per-area summary cards with risk counts and scores
7. User clicks cell → filters register to show matching risks

### Flow 5: RACI Matrix Editing
1. Board+ user navigates to `/compliance/raci`
2. RACI grid loads (GET /compliance/raci)
3. Rows: areas or matters. Columns: people.
4. Cells show R/A/C/I badges (or empty)
5. User clicks cell → RaciEditPopover
6. Selects role (R/A/C/I) + optional notes → POST /compliance/raci (upsert)
7. Cell updates immediately (optimistic update)

### Flow 6: Training Completion Tracking
1. Director+ navigates to `/compliance/trainings`
2. Training list loads (GET /compliance/trainings)
3. Clicks training row → navigate to `/compliance/trainings/{id}`
4. Training header shows title, area, type, deadline
5. StatusGrid shows all assigned people with their completion status
6. Manager clicks "Ukończone" on a person → POST /trainings/{id}/complete with person_id
7. Person row updates to "completed" with current date

### Flow 7: Regulatory Scan
1. Board+ user navigates to `/compliance/scan`
2. Selects hours range (24h default)
3. Clicks "Skanuj" → POST /compliance/scan?hours=24
4. Variable loading time → results show:
   - scanned_chunks count
   - regulatory_found count
   - matters_created count
   - Details list with each found item: title, area, type, priority, action taken

---

## 7. Shared/Reusable Components

These existing components will be reused:
- **KpiCard** — from `packages/ui/src/components/dashboard/kpi-card.tsx`
- **MarkdownRenderer** — from `packages/ui/src/components/chat/markdown-renderer.tsx`
- **SkeletonCard** — from `packages/ui/src/components/skeleton-card.tsx`
- **RbacGate** — from `packages/ui/src/components/rbac-gate.tsx`

New shared component within compliance:
- **ComplianceBadge** — universal badge for status, priority, phase, risk level, area code (consistent color maps)
- **AreaFilter** — reusable area_code dropdown (used in 8+ pages)

---

## 8. Design Notes

### AI Loading States
Four endpoints involve AI processing (10-20s):
- `research` → pulsing "Analizuję..." overlay with Loader2 spinner
- `generate doc` → modal stays open with progress text
- `report` → inline skeleton in Report tab
- `scan` → full-page loading with chunks-scanned counter

### Color Maps (consistent across all badges)

```typescript
// Priority
critical: 'bg-red-500/10 text-red-400 border-red-500/20'
high:     'bg-orange-500/10 text-orange-400 border-orange-500/20'
medium:   'bg-yellow-500/10 text-yellow-400 border-yellow-500/20'
low:      'bg-green-500/10 text-green-400 border-green-500/20'

// Compliance status
compliant:           'bg-green-500/10 text-green-400'
partially_compliant: 'bg-yellow-500/10 text-yellow-400'
non_compliant:       'bg-red-500/10 text-red-400'

// Risk color
green:    'bg-green-500/10 text-green-400'
yellow:   'bg-yellow-500/10 text-yellow-400'
orange:   'bg-orange-500/10 text-orange-400'
red:      'bg-red-500/10 text-red-400'
critical: 'bg-red-600/10 text-red-500'

// Area code
URE:      'bg-blue-500/10 text-blue-400'
RODO:     'bg-purple-500/10 text-purple-400'
AML:      'bg-red-500/10 text-red-400'
KSH:      'bg-cyan-500/10 text-cyan-400'
ESG:      'bg-green-500/10 text-green-400'
LABOR:    'bg-amber-500/10 text-amber-400'
TAX:      'bg-indigo-500/10 text-indigo-400'
CONTRACT: 'bg-teal-500/10 text-teal-400'
INTERNAL_AUDIT: 'bg-gray-500/10 text-gray-400'
```

### No Pagination
Backend returns arrays with `limit` but no offset/cursor. Frontend uses client-side pagination for large lists (matters, obligations, documents). Default limit=50 should be sufficient for initial use.

### No Delete, No Edit
Backend is workflow-driven: advance phases, fulfill obligations, approve documents. No PATCH/PUT/DELETE. UI should not show edit/delete actions.
