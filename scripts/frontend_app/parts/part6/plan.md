# Part 6: Documents, Decisions & Calendar — Architecture Plan

**Date:** 2026-03-29
**Modules:** Documents, Decisions, Calendar
**Implementation order:** Decisions → Calendar → Documents

---

## 1. Component Tree

### Decisions (CEO only)
```
DecisionsPage
├── DecisionsHeader (title + "Nowa decyzja" button)
├── DecisionsTabs
│   ├── Tab: "Dziennik" (default)
│   │   ├── DecisionFilters (area dropdown, search)
│   │   └── DecisionsList
│   │       └── DecisionCard[] (expandable)
│   │           ├── DecisionMeta (area badge, confidence bar, date)
│   │           ├── DecisionContext (collapsed by default)
│   │           └── OutcomesList
│   │               ├── OutcomeItem[] (rating stars, actual text)
│   │               └── AddOutcomeButton → OutcomeModal
│   ├── Tab: "Wzorce AI"
│   │   └── PatternsPanel (markdown rendered AI insights)
│   └── Tab: "Intelligence"
│       └── DecisionIntelligence
│           ├── ConfidenceCalibration (chart)
│           ├── BiasDetection (cards)
│           └── AreaBreakdown (pie chart)
├── CreateDecisionModal
│   ├── AreaSelect (5 areas)
│   ├── ConfidenceSlider (0-100%)
│   ├── TextFields (decision, context, expected outcome)
│   └── DatePicker (decided_at)
└── OutcomeModal
    ├── TextArea (actual_outcome)
    ├── StarRating (1-5)
    └── DatePicker (outcome_date)
```

### Calendar (manager+)
```
CalendarPage
├── CalendarHeader (title + week nav + "Deep Work" button)
├── CalendarTabs
│   ├── Tab: "Tydzień" (default)
│   │   └── WeekView
│   │       ├── DayColumn[] (7 days)
│   │       │   └── EventBlock[] (positioned by time)
│   │       │       ├── EventTitle + time
│   │       │       └── ConflictBadge (if overlapping)
│   │       └── TimeGutter (hour labels)
│   ├── Tab: "Przygotowanie"
│   │   └── MeetingPrepList
│   │       └── MeetingPrepCard[]
│   │           ├── MeetingInfo (subject, time, attendees)
│   │           ├── Brief (markdown)
│   │           └── ParticipantContext
│   ├── Tab: "Protokoły"
│   │   └── MeetingMinutesList
│   │       └── MinutesCard[] (expandable summary)
│   │       └── GenerateMinutesButton
│   └── Tab: "Analityka"
│       └── CalendarAnalytics
│           ├── TimeDistribution (pie: meetings vs focus vs free)
│           ├── MeetingsPerDay (bar chart)
│           └── MeetingROITable (subject, score, reason)
├── DeepWorkModal
│   ├── DatePicker
│   ├── StartHour / EndHour selects
│   └── ConfirmButton
└── EventDetailPopover (on event click)
```

### Documents (director+ upload, classification-filtered browse)
```
DocumentsPage
├── DocumentsHeader (title + "Wgraj dokument" button)
├── DocumentsTabs
│   ├── Tab: "Szukaj" (default)
│   │   ├── SearchBar (full-text query input)
│   │   ├── SourceTypeFilter (multi-select chips)
│   │   ├── DateRangeFilter
│   │   └── SearchResults
│   │       └── DocumentResultCard[]
│   │           ├── Title + source badge
│   │           ├── RelevanceScore
│   │           ├── MatchSnippet (highlighted chunk text)
│   │           └── Metadata (date, source_type)
│   ├── Tab: "Przeglądaj"
│   │   ├── SourceTypeFilter
│   │   ├── ClassificationFilter (based on RBAC)
│   │   └── DocumentsGrid / DocumentsTable
│   │       └── DocumentCard[] → click to detail
│   └── Tab: "Ingestion"
│       └── IngestionStatus
│           ├── SourceHealthCards (per source_type)
│           └── DLQStats
├── UploadModal (RbacGate: director+)
│   ├── DropZone (drag-and-drop area)
│   ├── FilePreview (name, size, type)
│   ├── ClassificationSelect
│   └── UploadProgress
└── DocumentDetailPanel (slide-over or sub-route)
    ├── DocumentMeta (title, source, date, classification)
    ├── ChunksList (with text content)
    └── RelatedEntities / Events
```

---

## 2. File Tree

```
# API Client Layer (packages/api-client/src/)
frontend/packages/api-client/src/decisions-types.ts
frontend/packages/api-client/src/decisions.ts
frontend/packages/api-client/src/calendar-types.ts
frontend/packages/api-client/src/calendar.ts
frontend/packages/api-client/src/documents-types.ts
frontend/packages/api-client/src/documents.ts

# Zustand Stores (apps/web/lib/stores/)
frontend/apps/web/lib/stores/decisions-store.ts
frontend/apps/web/lib/stores/calendar-store.ts
frontend/apps/web/lib/stores/documents-store.ts

# React Query Hooks (apps/web/lib/hooks/)
frontend/apps/web/lib/hooks/use-decisions.ts
frontend/apps/web/lib/hooks/use-calendar.ts
frontend/apps/web/lib/hooks/use-documents.ts

# UI Components — Decisions (packages/ui/src/components/decisions/)
frontend/packages/ui/src/components/decisions/index.ts
frontend/packages/ui/src/components/decisions/decision-card.tsx
frontend/packages/ui/src/components/decisions/decision-filters.tsx
frontend/packages/ui/src/components/decisions/create-decision-modal.tsx
frontend/packages/ui/src/components/decisions/outcome-modal.tsx
frontend/packages/ui/src/components/decisions/patterns-panel.tsx
frontend/packages/ui/src/components/decisions/decision-intelligence.tsx
frontend/packages/ui/src/components/decisions/confidence-slider.tsx
frontend/packages/ui/src/components/decisions/star-rating.tsx

# UI Components — Calendar (packages/ui/src/components/calendar/)
frontend/packages/ui/src/components/calendar/index.ts
frontend/packages/ui/src/components/calendar/week-view.tsx
frontend/packages/ui/src/components/calendar/day-column.tsx
frontend/packages/ui/src/components/calendar/event-block.tsx
frontend/packages/ui/src/components/calendar/meeting-prep-card.tsx
frontend/packages/ui/src/components/calendar/minutes-card.tsx
frontend/packages/ui/src/components/calendar/calendar-analytics.tsx
frontend/packages/ui/src/components/calendar/deep-work-modal.tsx
frontend/packages/ui/src/components/calendar/event-detail-popover.tsx

# UI Components — Documents (packages/ui/src/components/documents/)
frontend/packages/ui/src/components/documents/index.ts
frontend/packages/ui/src/components/documents/search-bar.tsx
frontend/packages/ui/src/components/documents/document-result-card.tsx
frontend/packages/ui/src/components/documents/source-type-filter.tsx
frontend/packages/ui/src/components/documents/upload-modal.tsx
frontend/packages/ui/src/components/documents/drop-zone.tsx
frontend/packages/ui/src/components/documents/documents-table.tsx
frontend/packages/ui/src/components/documents/ingestion-status.tsx
frontend/packages/ui/src/components/documents/document-detail-panel.tsx

# Page Routes
frontend/apps/web/app/(app)/decisions/page.tsx
frontend/apps/web/app/(app)/calendar/page.tsx
frontend/apps/web/app/(app)/documents/page.tsx
```

---

## 3. API Integration Map

### Decisions
| Component | Endpoint | Method | Hook |
|-----------|----------|--------|------|
| DecisionsList | `/decisions/decisions` | GET | `useDecisions(area?, limit?)` |
| CreateDecisionModal | `/decisions/decision` | POST | `useCreateDecision()` |
| OutcomeModal | `/decisions/decision/{id}/outcome` | POST | `useAddOutcome()` |
| PatternsPanel | `/decisions/decisions/patterns` | GET | `useDecisionPatterns()` |
| DecisionIntelligence | `/decision-intelligence` | GET | `useDecisionIntelligence(months?)` |
| DecisionIntelligence | `/decision-intelligence/run` | POST | `useRunIntelligence()` |

### Calendar
| Component | Endpoint | Method | Hook |
|-----------|----------|--------|------|
| WeekView | `/calendar/events` | GET | `useCalendarEvents(days?)` |
| WeekView (conflicts) | `/calendar/conflicts` | GET | `useCalendarConflicts(days?)` |
| CalendarAnalytics | `/calendar/analytics` | GET | `useCalendarAnalytics(days?)` |
| CalendarAnalytics (ROI) | `/meeting-roi` | GET | `useMeetingROI()` |
| MeetingPrepList | `/meeting-prep` | GET | `useMeetingPrep()` |
| MeetingMinutesList | `/meeting-minutes` | GET | `useMeetingMinutes(limit?)` |
| MeetingMinutesList | `/meeting-minutes/generate` | POST | `useGenerateMinutes()` |
| CalendarPage (suggestions) | `/calendar/suggestions` | GET | `useMeetingSuggestions()` |
| DeepWorkModal | `/calendar/block-deep-work` | POST | `useBlockDeepWork()` |

### Documents
| Component | Endpoint | Method | Hook |
|-----------|----------|--------|------|
| SearchResults | `/ask` | POST | `useDocumentSearch(query, filters)` |
| DocumentsTable | `/documents` | GET | `useDocumentsList(filters)` *(new backend endpoint)* |
| DocumentDetailPanel | `/documents/{id}` | GET | `useDocumentDetail(id)` *(new backend endpoint)* |
| UploadModal | `/documents/upload` | POST | `useDocumentUpload()` *(new backend endpoint)* |
| IngestionStatus | `/ingestion/dashboard` | GET | `useIngestionDashboard()` |

---

## 4. RBAC Per View

| View/Component | Minimum Role | Gate |
|----------------|-------------|------|
| `/decisions` page | `ceo` | `<RbacGate permission="decisions">` |
| Create decision | `ceo` | Inherits from page |
| Add outcome | `ceo` | Inherits from page |
| Decision intelligence | `ceo` | Inherits from page |
| `/calendar` page | `manager` | `<RbacGate permission="calendar">` |
| Block deep work | `ceo` | `<RbacGate roles={['ceo']}>` within calendar |
| Meeting prep | `director` | `<RbacGate roles={['ceo','board','director']}>` |
| `/documents` page | `director` | `<RbacGate permission="documents">` |
| Upload documents | `director` | `<RbacGate roles={['ceo','board','director']}>` |
| Browse documents | classification-filtered | Backend enforces per-role classification filter |
| Document search | classification-filtered | Backend enforces via `/ask` |

---

## 5. State Management (Zustand Stores)

### decisions-store.ts
```typescript
interface DecisionsStore {
  // Filters
  areaFilter: string | null;        // 'business'|'trading'|'relationships'|'wellbeing'|'general'|null
  searchQuery: string;
  listLimit: number;                 // default 50

  // UI state
  activeTab: 'journal' | 'patterns' | 'intelligence';
  expandedDecisionId: number | null;
  intelligenceMonths: number;        // default 6

  // Actions
  setAreaFilter: (area: string | null) => void;
  setSearchQuery: (q: string) => void;
  setActiveTab: (tab: DecisionsStore['activeTab']) => void;
  setExpandedDecisionId: (id: number | null) => void;
  setIntelligenceMonths: (m: number) => void;
}
```

### calendar-store.ts
```typescript
interface CalendarStore {
  // Navigation
  weekOffset: number;               // 0 = current week, -1 = last week, etc.
  eventsDays: number;               // default 7

  // UI state
  activeTab: 'week' | 'prep' | 'minutes' | 'analytics';
  selectedEventId: string | null;
  analyticsDays: number;            // default 30

  // Auto-refresh
  autoRefresh: boolean;
  refreshInterval: number;          // default 300_000 (5 min)

  // Actions
  setWeekOffset: (offset: number) => void;
  nextWeek: () => void;
  prevWeek: () => void;
  setActiveTab: (tab: CalendarStore['activeTab']) => void;
  setSelectedEventId: (id: string | null) => void;
  setAnalyticsDays: (days: number) => void;
}
```

### documents-store.ts
```typescript
interface DocumentsStore {
  // Search
  searchQuery: string;
  sourceTypeFilter: string[];       // multi-select
  dateFrom: string | null;
  dateTo: string | null;

  // Browse
  classificationFilter: string | null;
  browseSourceType: string | null;

  // UI state
  activeTab: 'search' | 'browse' | 'ingestion';
  selectedDocumentId: number | null;

  // Actions
  setSearchQuery: (q: string) => void;
  setSourceTypeFilter: (types: string[]) => void;
  setDateRange: (from: string | null, to: string | null) => void;
  setActiveTab: (tab: DocumentsStore['activeTab']) => void;
  setSelectedDocumentId: (id: number | null) => void;
  setBrowseSourceType: (type: string | null) => void;
  setClassificationFilter: (cls: string | null) => void;
}
```

---

## 6. UX Flows

### Decisions: Create Decision
1. User clicks "Nowa decyzja" → CreateDecisionModal opens
2. User fills: decision_text (required), area (dropdown, required), confidence (slider 0-100%), context (optional), expected_outcome (optional), decided_at (optional, defaults to now)
3. Submit → POST `/decisions/decision` → modal closes → list refreshes → new decision appears at top
4. Toast: "Decyzja zapisana"

### Decisions: Record Outcome
1. User expands a DecisionCard → sees outcomes list + "Dodaj wynik" button
2. Click → OutcomeModal opens (pre-filled decision context for reference)
3. User fills: actual_outcome (text), rating (1-5 stars), outcome_date (optional)
4. Submit → POST `/decisions/decision/{id}/outcome` → modal closes → card refreshes with new outcome
5. Toast: "Wynik zapisany"

### Decisions: View AI Patterns
1. User switches to "Wzorce AI" tab
2. Loading skeleton → GET `/decisions/decisions/patterns` → markdown rendered
3. Shows insights in Polish (areas, patterns, recommendations)

### Calendar: Navigate Week
1. Default view: current week (Mon-Sun)
2. Arrow buttons shift weekOffset ±1 → refetch `/calendar/events?days=7` with calculated date offset
3. Events render in DayColumn at correct time positions
4. Conflicts highlighted with red border + ConflictBadge (from `/calendar/conflicts`)

### Calendar: Block Deep Work
1. User clicks "Deep Work" button → DeepWorkModal opens
2. Selects date (default tomorrow), start_hour (default 9), end_hour (default 11)
3. Submit → POST `/calendar/block-deep-work` → confirmation toast
4. Calendar refreshes → blocked slot visible

### Calendar: Meeting Prep
1. User switches to "Przygotowanie" tab
2. Loading → GET `/meeting-prep` → list of upcoming meetings with AI-generated briefs
3. Each MeetingPrepCard shows: meeting info, participant context, brief (markdown)

### Documents: Search
1. User types query in SearchBar → debounced 500ms
2. POST `/ask` with `{query, source_types: selectedSourceTypes, date_from, date_to, mode: "search"}`
3. Results: answer text + DocumentResultCard[] with highlighted snippets
4. Click card → DocumentDetailPanel slides in (or navigates to detail)

### Documents: Upload (director+)
1. User clicks "Wgraj dokument" → UploadModal opens (RbacGate enforced)
2. Drag-and-drop or click to select file (PDF, DOCX, XLSX, TXT, images)
3. Select classification (optional, defaults based on role)
4. Submit → POST `/documents/upload` (multipart) → progress bar
5. On complete → toast "Dokument wgrany, przetwarzanie..." → ingestion pipeline handles rest
6. User can check "Ingestion" tab for processing status

---

## 7. Key Technical Decisions

1. **No streaming for search** — `/ask` returns full response, display with loading skeleton
2. **Week view custom component** — no external calendar library, simple CSS grid (7 cols × 24 rows)
3. **Markdown rendering** — reuse `react-markdown` + `remark-gfm` from chat module for patterns/briefs
4. **Document upload** — multipart/form-data via customFetch extension, no SSE for progress (poll ingestion dashboard)
5. **Confidence slider** — custom range input with labeled ticks (0%, 25%, 50%, 75%, 100%)
6. **Star rating** — interactive 1-5 stars component, reusable
7. **Backend gaps** — Documents module marks upload/browse/detail as "coming soon" if backend endpoints don't exist yet; search via `/ask` works immediately

---

## 8. Dependencies

- `react-markdown` + `remark-gfm` (already in project from chat module)
- `recharts` (already in project for charts)
- No new external dependencies needed
