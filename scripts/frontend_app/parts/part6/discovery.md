# Part 6: Documents, Decisions & Calendar — Discovery Report

**Date:** 2026-03-29
**Module scope:** Document management, Decision journal, Calendar integration

---

## 1. API Endpoint Inventory

### Documents

| Method | Path | Params | Response | Notes |
|--------|------|--------|----------|-------|
| POST | `/ask` | `query`, `source_types=["document"]`, `top_k`, `date_from`, `date_to`, `mode` | `{answer, sources[], matches[], meta}` | Full-text + semantic search; filter by `source_types` for docs |
| POST | `/timeline` | `event_type?`, `date_from`, `date_to`, `limit` | `{events[], meta}` | Document-based event timeline |
| GET | `/ingestion/dashboard` | — | `{sources, extraction_backlogs, dlq_stats, guardian_alerts}` | Ingestion health per source type |

**Upload endpoint: DOES NOT EXIST.** No file upload API for general documents. Only `voice.py` has `UploadFile` support. This is a **backend gap**.

### Decisions

| Method | Path | Params | Response | Notes |
|--------|------|--------|----------|-------|
| POST | `/decisions/decision` | Body: `{decision_text, context?, expected_outcome?, area, confidence, decided_at?}` | `DecisionResponse{id, decision_text, context, expected_outcome, area, confidence, decided_at, created_at}` | Create new decision |
| POST | `/decisions/decision/{id}/outcome` | Body: `{actual_outcome, rating(1-5), outcome_date?}` | `OutcomeResponse{id, decision_id, actual_outcome, rating, outcome_date, created_at}` | Record outcome |
| GET | `/decisions/decisions` | `area?`, `limit(1-500, default=50)` | `{decisions: DecisionWithOutcomes[], meta: {count, area?, latency_ms}}` | List with nested outcomes |
| GET | `/decisions/decisions/patterns` | — | `{insights: string, meta: {decision_count, areas[], latency_ms}}` | AI analysis (Claude) — Polish text |
| GET | `/decision-intelligence` | `months(default=6)` | Analysis object | Patterns, confidence calibration, bias detection |
| POST | `/decision-intelligence/run` | — | Pipeline result | Run decision intelligence pipeline |

### Calendar

| Method | Path | Params | Response | Notes |
|--------|------|--------|----------|-------|
| GET | `/calendar/events` | `days(default=7)` | `{events[]}` | Upcoming events from M365 |
| GET | `/calendar/conflicts` | `days(default=3)` | `{conflicts[]}` | Scheduling overlaps |
| GET | `/calendar/analytics` | `days(default=30)` | Analytics object | Time distribution, frequency |
| GET | `/calendar/suggestions` | — | `{suggestions[]}` | Relationship-based meeting suggestions |
| POST | `/calendar/block-deep-work` | `date?`, `start_hour(default=9)`, `end_hour(default=11)` | Confirmation | Block focus time |
| GET | `/meeting-prep` | — | Prep briefs | Auto-generated meeting briefs |
| GET | `/meeting-minutes` | `limit(default=10)` | `[{id, document_id, title, date, participants, summary, created}]` | Recent minutes list |
| POST | `/meeting-minutes/generate` | — | Generation result | Generate from recordings |
| GET | `/meeting-roi` | — | ROI analysis | Meeting effectiveness metrics |

---

## 2. RBAC Rules

### Role Hierarchy (7 levels)
| Role | Level | Documents | Decisions | Calendar |
|------|-------|-----------|-----------|----------|
| `gilbertus_admin` | 99 | All classifications | Full access | Full access |
| `operator` | 70 | No access | No access | No access |
| `ceo` | 60 | All (public, internal, confidential, ceo_only, personal) | Full access | Full access |
| `board` | 50 | public, internal, confidential, personal | No access | Full access |
| `director` | 40 | public, internal, personal | No access | Full access |
| `manager` | 30 | public, internal, personal | No access | Full access |
| `specialist` | 20 | public, personal (own only) | No access | No access |

### Frontend Navigation Config (from `packages/rbac/src/navigation.ts`)
- **Documents:** `roles: ['ceo', 'board', 'director']`
- **Decisions:** `roles: ['ceo']`
- **Calendar:** `roles: ['ceo', 'board', 'director', 'manager']`

### Classification-based Document Filtering
Documents browsed via `/ask` with `source_types` filter. Personal documents further filtered by `owner_user_id`. The frontend must pass classification context to respect backend RBAC.

---

## 3. Existing Frontend Patterns

### Architecture
- **Monorepo:** pnpm workspaces — `apps/web` (Next.js 16), `packages/{api-client, rbac, ui, i18n}`
- **Router:** Next.js App Router with route groups `(auth)` and `(app)`
- **UI:** Radix UI + Tailwind + Lucide icons (shadcn-style)
- **State:** Zustand + persist middleware (localStorage)
- **Data fetching:** TanStack React Query 5 + custom hooks
- **Auth:** NextAuth v5 beta (API key + Azure AD)
- **Charts:** Recharts 3.8

### File Pattern per Module
```
packages/api-client/src/{module}.ts          — API functions (customFetch wrapper)
packages/api-client/src/{module}-types.ts    — TypeScript types
packages/ui/src/components/{module}/         — UI components
packages/ui/src/components/{module}/index.ts — Barrel exports
apps/web/app/(app)/{module}/page.tsx         — Page route
apps/web/lib/hooks/use-{module}.ts           — React Query hooks
apps/web/lib/stores/{module}-store.ts        — Zustand store
```

### API Client Pattern
```typescript
export async function fetchX(params: XParams): Promise<XResponse> {
  return customFetch<XResponse>({ url: '/endpoint', method: 'GET', params });
}
```

### Hook Pattern
```typescript
export function useX(options?: XOptions) {
  const { autoRefresh, refreshInterval } = useXStore();
  return useQuery<XResponse>({
    queryKey: ['x', options],
    queryFn: () => fetchX(options),
    refetchInterval: autoRefresh ? refreshInterval : false,
  });
}
```

### Component Pattern
- PascalCase names, feature-based directories
- Props interface exported alongside component
- `RbacGate` for permission-gated content
- Loading skeletons built into components
- `KpiCard` for metric display

---

## 4. Data Types/Interfaces Needed

### Documents
```typescript
interface DocumentSource {
  document_id: number;
  title: string;
  source_type: 'email' | 'teams' | 'whatsapp' | 'document' | 'pdf' | 'plaud' | 'chatgpt' | 'calendar';
  created_at: string;
  classification?: string;
}

interface DocumentSearchResult {
  answer: string;
  sources: DocumentSource[];
  matches: { chunk_id: number; document_id: number; score: number; text: string }[];
  meta: { question_type: string; latency_ms: number; cache_hit: boolean };
}

// Upload types — TBD when backend endpoint is created
interface DocumentUploadRequest {
  file: File;
  classification?: string;
  tags?: string[];
}
```

### Decisions
```typescript
interface Decision {
  id: number;
  decision_text: string;
  context: string | null;
  expected_outcome: string | null;
  area: 'business' | 'trading' | 'relationships' | 'wellbeing' | 'general';
  confidence: number; // 0.0 - 1.0
  decided_at: string;
  created_at: string;
  outcomes: DecisionOutcome[];
}

interface DecisionOutcome {
  id: number;
  decision_id: number;
  actual_outcome: string;
  rating: number; // 1-5
  outcome_date: string;
  created_at: string;
}

interface DecisionCreate {
  decision_text: string;
  context?: string;
  expected_outcome?: string;
  area: Decision['area'];
  confidence: number;
  decided_at?: string;
}

interface OutcomeCreate {
  actual_outcome: string;
  rating: number;
  outcome_date?: string;
}

interface DecisionsListResponse {
  decisions: Decision[];
  meta: { count: number; area?: string; latency_ms: number };
}

interface PatternsResponse {
  insights: string; // Markdown text in Polish
  meta: { decision_count: number; areas: string[]; latency_ms: number };
}
```

### Calendar
```typescript
interface CalendarEvent {
  id: string;
  subject: string;
  start: string;
  end: string;
  organizer?: string;
  attendees?: string[];
  location?: string;
  is_online?: boolean;
}

interface CalendarConflict {
  event_a: CalendarEvent;
  event_b: CalendarEvent;
  overlap_minutes: number;
}

interface CalendarAnalytics {
  total_meetings: number;
  total_hours: number;
  meetings_by_day: Record<string, number>;
  focus_time_hours: number;
  meeting_categories?: Record<string, number>;
}

interface MeetingPrep {
  meeting: CalendarEvent;
  brief: string;
  participants_info: any[];
  recent_context: string[];
}

interface MeetingMinutes {
  id: number;
  document_id: number;
  title: string;
  date: string | null;
  participants: string | null;
  summary: string;
  created: string;
}

interface MeetingROI {
  meetings: { subject: string; roi_score: number; reason: string }[];
  summary: string;
}
```

---

## 5. Backend Gaps

| Gap | Severity | Workaround |
|-----|----------|------------|
| **No document upload endpoint** | HIGH | Must create `POST /documents/upload` with `UploadFile` support (PDF, DOCX, XLSX, TXT, images). Needs multipart form handling + ingestion pipeline trigger. |
| **No document browse/list endpoint** | MEDIUM | Can use `POST /ask` with `source_types` filter + empty-ish query, or query DB directly. Ideally create `GET /documents` with pagination, source_type filter, classification filter. |
| **No document detail endpoint** | MEDIUM | Can reconstruct from `/ask` matches (chunk_id → document_id), but a `GET /documents/{id}` with chunks + metadata would be cleaner. |
| **Calendar event response shapes undefined** | LOW | `calendar_manager` functions exist but exact return types need verification at runtime. Mock-friendly with typed interfaces. |
| **Decision intelligence response shape undefined** | LOW | `analyze_decision_patterns()` return type not in schemas — need runtime check. |
| **No SSE/WebSocket for upload progress** | LOW | Can poll ingestion dashboard, or use simple progress bar with multipart upload response. |

---

## 6. Complexity Estimates

### Documents
| Feature | Complexity | Notes |
|---------|-----------|-------|
| Document search (full-text) | **Simple** | Reuse `/ask` with source_type filter |
| Browse by source type | **Medium** | Need new `GET /documents` endpoint or creative `/ask` usage |
| Upload zone (drag-and-drop) | **Complex** | New backend endpoint needed, multipart upload, progress tracking |
| Document viewer with chunks | **Complex** | Need document detail endpoint, chunk highlighting, metadata display |
| Upload progress + ingestion status | **Medium** | Poll `/ingestion/dashboard` or add SSE |

### Decisions
| Feature | Complexity | Notes |
|---------|-----------|-------|
| Decision journal list | **Simple** | `GET /decisions/decisions` — straightforward table |
| Create decision form | **Simple** | `POST /decisions/decision` — form with area enum, confidence slider |
| Outcome tracker | **Simple** | `POST /decisions/decision/{id}/outcome` — modal with rating |
| AI pattern analysis | **Medium** | `GET /decisions/decisions/patterns` — markdown rendering, loading state |
| Decision intelligence | **Medium** | `GET /decision-intelligence` — dashboard with charts |
| Weekly synthesis | **Simple** | Display from existing endpoint |

### Calendar
| Feature | Complexity | Notes |
|---------|-----------|-------|
| Week view with events | **Medium** | `GET /calendar/events` — need calendar grid component |
| Conflict detection | **Simple** | `GET /calendar/conflicts` — highlighted list |
| Meeting prep briefs | **Simple** | `GET /meeting-prep` — card list with markdown |
| Deep work blocks | **Simple** | `POST /calendar/block-deep-work` — form with date/time |
| Meeting ROI analysis | **Medium** | `GET /meeting-roi` — charts + table |
| Time analytics | **Medium** | `GET /calendar/analytics` — pie/bar charts with Recharts |
| Meeting minutes | **Simple** | `GET /meeting-minutes` — list with expandable summaries |
| Meeting suggestions | **Simple** | `GET /calendar/suggestions` — card list |

---

## 7. What Exists vs What Needs Creation

### Already exists
- Navigation config in `packages/rbac/src/navigation.ts` (all 3 modules registered)
- RBAC role/classification system in `packages/rbac/`
- `RbacGate` component for permission gating
- `DeadlineCalendar` in compliance (potential reuse for calendar grid patterns)
- `DocumentsTable` + `GenerateDocModal` in compliance (pattern reference)
- Compliance documents page (reference for document management UX)

### Must create
| Layer | Documents | Decisions | Calendar |
|-------|-----------|-----------|----------|
| API client | `documents.ts` + types | `decisions.ts` + types | `calendar.ts` + types |
| Zustand store | `documents-store.ts` | `decisions-store.ts` | `calendar-store.ts` |
| React Query hooks | `use-documents.ts` | `use-decisions.ts` | `use-calendar.ts` |
| UI components | `packages/ui/src/components/documents/` | `packages/ui/src/components/decisions/` | `packages/ui/src/components/calendar/` |
| Page routes | `app/(app)/documents/page.tsx` | `app/(app)/decisions/page.tsx` | `app/(app)/calendar/page.tsx` |
| Optional sub-routes | `documents/[id]/page.tsx` | `decisions/[id]/page.tsx` | — |

### Backend endpoints to create
1. `POST /documents/upload` — multipart file upload with classification
2. `GET /documents` — list/browse with filters (source_type, classification, date range, pagination)
3. `GET /documents/{id}` — document detail with chunks and metadata

---

## 8. Recommended Implementation Order

1. **Decisions** (all endpoints exist, simplest module, CEO-only)
2. **Calendar** (all endpoints exist, medium complexity, wider audience)
3. **Documents** (requires new backend endpoints, most complex)
