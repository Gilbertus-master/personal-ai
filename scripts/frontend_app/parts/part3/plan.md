# Part 3: People & Intelligence — Architecture Plan

**Module:** People Directory, Profiles, Sentiment, Intelligence, Scenarios
**Date:** 2026-03-29

---

## 1. Component Tree (Visual Hierarchy)

```
AppLayout (existing)
├── Sidebar (existing — /people + /intelligence links in nav)
└── <main>
    │
    ├── /people (page.tsx) ─────────────────────────────────────
    │   │
    │   ├── RbacGate [ceo, board, director]
    │   │   └── PEOPLE DIRECTORY
    │   │       │
    │   │       ├── PageHeader ("Ludzie" + person count badge)
    │   │       │   └── CreatePersonButton (ceo only)
    │   │       │
    │   │       ├── PeopleToolbar
    │   │       │   ├── SearchInput (client-side name search)
    │   │       │   ├── FilterChips
    │   │       │   │   ├── relationship_type (employee, partner, client, etc.)
    │   │       │   │   ├── status (active, inactive)
    │   │       │   │   └── organization (derived from data)
    │   │       │   └── SortSelect (name, last_contact, status)
    │   │       │
    │   │       └── PeopleTable
    │   │           └── PersonRow[] (clickable → /people/{slug})
    │   │               ├── Avatar (initials-based)
    │   │               ├── Name (first_name + last_name)
    │   │               ├── Role badge
    │   │               ├── Organization
    │   │               ├── Status dot (active/inactive)
    │   │               ├── Sentiment indicator (positive/neutral/negative)
    │   │               └── Last contact date
    │   │
    │   └── RbacGate [manager, specialist] → AccessDenied
    │
    ├── /people/[slug] (page.tsx) ──────────────────────────────
    │   │
    │   ├── RbacGate [ceo, board, director]
    │   │   └── PERSON PROFILE
    │   │       │
    │   │       ├── ProfileHeader
    │   │       │   ├── Avatar (large, initials)
    │   │       │   ├── Name + role + org
    │   │       │   ├── Status badge + sentiment badge
    │   │       │   ├── Contact channel
    │   │       │   └── ActionButtons
    │   │       │       ├── EditPersonButton (ceo)
    │   │       │       └── EvaluateButton (ceo only)
    │   │       │
    │   │       ├── ScorecardKpis (from GET /scorecard/{slug})
    │   │       │   └── KpiCard[] (4 cards)
    │   │       │       ├── Data volume (chunks + events)
    │   │       │       ├── Recent events (30d count)
    │   │       │       ├── Open loops count
    │   │       │       └── Weekly activity trend
    │   │       │
    │   │       ├── Tabs
    │   │       │   ├── "Oś czasu" — PersonTimeline
    │   │       │   │   └── TimelineEntry[] (icon, date, type badge, description)
    │   │       │   │       └── AddTimelineButton (ceo)
    │   │       │   │
    │   │       │   ├── "Otwarte wątki" — OpenLoops
    │   │       │   │   └── LoopItem[] (description, status, created, close button)
    │   │       │   │       └── AddLoopButton (ceo)
    │   │       │   │
    │   │       │   ├── "Sentiment" — SentimentChart (board+)
    │   │       │   │   └── Line chart (recharts) — weeks × sentiment score
    │   │       │   │
    │   │       │   ├── "Delegacje" — DelegationScore
    │   │       │   │   └── Score display + metrics
    │   │       │   │
    │   │       │   └── "Historia ról" — RolesHistory
    │   │       │       └── RoleEntry[] (role, org, date_from → date_to)
    │   │       │           └── AddRoleButton (ceo)
    │   │       │
    │   │       └── RbacGate [ceo]
    │   │           └── EvaluationSection
    │   │               ├── TriggerEvaluation form (date range picker)
    │   │               └── EvaluationResult (AI-generated markdown)
    │   │
    │   └── RbacGate [manager, specialist] → AccessDenied
    │
    ├── /people/network (page.tsx) ─────────────────────────────
    │   │
    │   └── RbacGate [ceo, board]
    │       └── NETWORK GRAPH
    │           ├── PageHeader ("Sieć relacji")
    │           ├── NetworkGraph (react-force-graph-2d)
    │           │   ├── Nodes (people, sized by event count)
    │           │   └── Edges (communication frequency)
    │           └── NetworkLegend
    │
    ├── /intelligence (page.tsx) ────────────────────────────────
    │   │
    │   └── RbacGate [ceo, board]
    │       └── INTELLIGENCE DASHBOARD
    │           │
    │           ├── PageHeader ("Wywiad biznesowy")
    │           │
    │           ├── OrgHealthBanner (top, full width)
    │           │   ├── Score gauge (circular, 1-100)
    │           │   ├── Trend indicator (improving/declining/stable)
    │           │   └── AssessButton (triggers POST /org-health/assess)
    │           │
    │           ├── IntelligenceTabs
    │           │   │
    │           │   ├── "Szanse" — OpportunitiesTab
    │           │   │   ├── ScanButton (triggers POST /opportunities/scan)
    │           │   │   └── OpportunitiesTable
    │           │   │       └── OpportunityRow[]
    │           │   │           ├── Type badge
    │           │   │           ├── Description (truncated)
    │           │   │           ├── Value PLN (formatted)
    │           │   │           ├── ROI (color-coded)
    │           │   │           ├── Confidence bar
    │           │   │           └── Status badge (new/analyzed/accepted/rejected)
    │           │   │
    │           │   ├── "Nieefektywności" — InefficienciesTab
    │           │   │   └── InefficiencyReport
    │           │   │       ├── RepeatingTasksSection
    │           │   │       ├── BottlenecksSection
    │           │   │       ├── MeetingOverloadSection
    │           │   │       └── SummaryKpis
    │           │   │
    │           │   ├── "Korelacje" — CorrelationsTab
    │           │   │   └── CorrelationExplorer
    │           │   │       ├── TypeSelector (temporal/person/anomaly/report)
    │           │   │       ├── DynamicParams (changes per type)
    │           │   │       ├── RunButton
    │           │   │       └── CorrelationResult (varied display per type)
    │           │   │
    │           │   ├── "Scenariusze" — ScenariosTab (ceo only)
    │           │   │   ├── ScenariosList
    │           │   │   │   └── ScenarioCard[]
    │           │   │   │       ├── Title + type badge
    │           │   │   │       ├── Description
    │           │   │   │       ├── Impact PLN
    │           │   │   │       ├── Status badge
    │           │   │   │       └── AnalyzeButton / CompareButton
    │           │   │   ├── CreateScenarioForm
    │           │   │   └── ScenarioAnalysisView
    │           │   │       └── OutcomeCard[] (dimension, impact, probability, mitigation)
    │           │   │
    │           │   └── "Predykcje" — PredictionsTab
    │           │       └── PredictiveAlerts
    │           │           ├── EscalationRisks section
    │           │           ├── CommunicationGaps section
    │           │           └── DeadlineRisks section
    │           │
    │           └── WellbeingCard (sidebar, board+)
    │               └── Trend sparkline + current score
```

---

## 2. File Tree (Every File Path)

```
frontend/
├── packages/
│   ├── api-client/src/
│   │   ├── people-types.ts          ← Person, PersonFull, Scorecard, etc.
│   │   ├── people.ts               ← fetchPeople, fetchPerson, fetchScorecard, etc.
│   │   ├── intelligence-types.ts    ← Opportunity, Scenario, OrgHealth, etc.
│   │   ├── intelligence.ts          ← fetchOpportunities, fetchScenarios, etc.
│   │   └── index.ts                 ← (UPDATE: add exports)
│   │
│   └── ui/src/components/
│       ├── people/
│       │   ├── index.ts
│       │   ├── people-toolbar.tsx
│       │   ├── people-table.tsx
│       │   ├── person-row.tsx
│       │   ├── profile-header.tsx
│       │   ├── scorecard-kpis.tsx
│       │   ├── person-timeline.tsx
│       │   ├── open-loops.tsx
│       │   ├── sentiment-chart.tsx
│       │   ├── delegation-score.tsx
│       │   ├── roles-history.tsx
│       │   ├── evaluation-section.tsx
│       │   ├── person-form-modal.tsx
│       │   └── network-graph.tsx
│       │
│       └── intelligence/
│           ├── index.ts
│           ├── org-health-banner.tsx
│           ├── opportunities-table.tsx
│           ├── inefficiency-report.tsx
│           ├── correlation-explorer.tsx
│           ├── scenarios-list.tsx
│           ├── scenario-form.tsx
│           ├── scenario-analysis.tsx
│           └── predictive-alerts.tsx
│
├── apps/web/
│   ├── app/(app)/
│   │   ├── people/
│   │   │   ├── page.tsx             ← People directory page
│   │   │   ├── [slug]/
│   │   │   │   └── page.tsx         ← Person profile page
│   │   │   └── network/
│   │   │       └── page.tsx         ← Network graph page
│   │   │
│   │   └── intelligence/
│   │       └── page.tsx             ← Intelligence dashboard page
│   │
│   └── lib/
│       ├── hooks/
│       │   ├── use-people.ts        ← React Query hooks for people
│       │   └── use-intelligence.ts  ← React Query hooks for intelligence
│       │
│       └── stores/
│           ├── people-store.ts      ← Search, filters, sort preferences
│           └── intelligence-store.ts ← Active tab, dismissed items, filters
```

---

## 3. API Integration Map (Component → Endpoint)

### People Module

| Component | Endpoint | Method | Trigger |
|-----------|----------|--------|---------|
| PeopleTable | `GET /people` | useQuery | Page load, filter change |
| PersonRow → link | — | Navigation | Click → /people/{slug} |
| ProfileHeader | `GET /people/{slug}` | useQuery | Page load |
| ScorecardKpis | `GET /scorecard/{slug}` | useQuery | Page load |
| PersonTimeline | (from PersonFull) | — | From profile query |
| OpenLoops | (from PersonFull) | — | From profile query |
| AddTimelineButton | `POST /people/{slug}/timeline` | useMutation | Click |
| AddLoopButton | `POST /people/{slug}/loops` | useMutation | Click |
| CloseLoopButton | `PUT /people/{slug}/loops/{id}` | useMutation | Click |
| SentimentChart | `GET /sentiment/{slug}` | useQuery | Tab select |
| DelegationScore | `GET /delegation/{slug}` | useQuery | Tab select |
| RolesHistory | (from PersonFull) | — | From profile query |
| EvaluateButton | `POST /evaluate` | useMutation | Click (ceo) |
| CreatePersonButton | `POST /people` | useMutation | Form submit |
| EditPersonButton | `PUT /people/{slug}` | useMutation | Form submit |
| NetworkGraph | `GET /network` | useQuery | Page load |

### Intelligence Module

| Component | Endpoint | Method | Trigger |
|-----------|----------|--------|---------|
| OrgHealthBanner | `GET /org-health` | useQuery | Page load |
| AssessButton | `POST /org-health/assess` | useMutation | Click |
| OpportunitiesTable | `GET /opportunities` | useQuery | Tab select |
| ScanButton | `POST /opportunities/scan` | useMutation | Click |
| InefficiencyReport | `GET /inefficiency` | useQuery | Tab select |
| CorrelationExplorer | `POST /correlate` | useMutation | Form submit |
| ScenariosList | `GET /scenarios` | useQuery | Tab select |
| CreateScenarioForm | `POST /scenarios` | useMutation | Form submit |
| AnalyzeButton | `POST /scenarios/{id}/analyze` | useMutation | Click |
| CompareButton | `GET /scenarios/compare` | useQuery | Click |
| PredictiveAlerts | `GET /predictions` | useQuery | Tab select |
| WellbeingCard | `GET /wellbeing` | useQuery | Page load |

---

## 4. RBAC per View/Component

| View | Roles | Gate Type |
|------|-------|-----------|
| `/people` directory | ceo, board, director | Page-level RbacGate |
| `/people/[slug]` profile | ceo, board, director | Page-level RbacGate |
| Evaluation trigger | ceo only | Component-level RbacGate |
| Create/Edit person | ceo only | Component-level RbacGate |
| Add timeline/loops/roles | ceo only | Button visibility |
| Sentiment chart | ceo, board | Tab visibility |
| Wellbeing | ceo, board | Component-level RbacGate |
| Network graph | ceo, board | Page-level RbacGate |
| `/intelligence` | ceo, board | Page-level RbacGate |
| Scenarios CRUD | ceo only | Tab-level RbacGate |
| Scenarios read | ceo, board | Read-only for board |

**Director scope restriction:** Directors see only people from their department. Filter applied in `usePeople()` hook based on role — backend enforces via API but frontend should also filter for UX consistency.

---

## 5. State Management (Zustand Store Shapes)

### people-store.ts

```typescript
interface PeopleStore {
  // Directory state
  searchQuery: string;
  filterType: string | null;        // relationship_type filter
  filterStatus: string | null;      // status filter
  sortBy: 'name' | 'last_contact' | 'status';
  sortOrder: 'asc' | 'desc';

  // Profile state
  activeTab: 'timeline' | 'loops' | 'sentiment' | 'delegation' | 'roles';

  // Actions
  setSearchQuery: (q: string) => void;
  setFilterType: (type: string | null) => void;
  setFilterStatus: (status: string | null) => void;
  setSortBy: (sort: 'name' | 'last_contact' | 'status') => void;
  toggleSortOrder: () => void;
  setActiveTab: (tab: string) => void;
  resetFilters: () => void;
}
```

Persist key: `gilbertus-people`

### intelligence-store.ts

```typescript
interface IntelligenceStore {
  // Tab state
  activeTab: 'opportunities' | 'inefficiencies' | 'correlations' | 'scenarios' | 'predictions';

  // Opportunities filters
  opportunityStatus: string | null;

  // Correlation form state
  correlationType: 'temporal' | 'person' | 'anomaly' | 'report';
  correlationParams: Record<string, string>;

  // Scenarios filters
  scenarioStatus: string | null;

  // Actions
  setActiveTab: (tab: string) => void;
  setOpportunityStatus: (status: string | null) => void;
  setCorrelationType: (type: string) => void;
  setCorrelationParam: (key: string, value: string) => void;
  resetCorrelationParams: () => void;
  setScenarioStatus: (status: string | null) => void;
}
```

Persist key: `gilbertus-intelligence`

---

## 6. UX Flows

### Flow 1: Browse People Directory
1. User navigates to `/people`
2. People list loads (GET /people?status=active&limit=100)
3. User types in search → client-side filter by name
4. User clicks filter chip (e.g., "employee") → refetch with `?type=employee`
5. User clicks person row → navigate to `/people/{slug}`

### Flow 2: View Person Profile
1. Page loads → parallel fetch: GET /people/{slug} + GET /scorecard/{slug}
2. KPI cards render from scorecard data
3. Default tab: "Oś czasu" shows timeline events
4. User clicks "Sentiment" tab → lazy-fetch GET /sentiment/{slug}?weeks=8
5. CEO clicks "Oceń" button → date range form → POST /evaluate → show AI result in markdown

### Flow 3: Explore Intelligence
1. User navigates to `/intelligence`
2. OrgHealthBanner loads (GET /org-health)
3. Default tab: "Szanse" → loads GET /opportunities
4. User clicks "Skanuj" → POST /opportunities/scan → toast notification → refetch list
5. User switches to "Scenariusze" tab → loads GET /scenarios
6. CEO clicks "Nowy scenariusz" → form modal → POST /scenarios (query params!) → redirect to new scenario
7. CEO clicks "Analizuj" on scenario → POST /scenarios/{id}/analyze → shows outcomes

### Flow 4: Correlation Analysis
1. User selects correlation type (temporal/person/anomaly/report)
2. Dynamic form shows relevant parameters for selected type
3. User fills params and clicks "Analizuj" → POST /correlate
4. Result renders based on type:
   - temporal: chart (recharts)
   - person: profile summary
   - anomaly: alert-style list
   - report: markdown rendered text

### Flow 5: Create/Edit Person (CEO only)
1. CEO clicks "Dodaj osobę" on directory → modal form
2. Fills: slug, first_name, last_name, relationship fields
3. Submit → POST /people → success toast → refetch list
4. On profile, CEO clicks "Edytuj" → pre-filled modal → PUT /people/{slug}

---

## 7. Shared/Reusable Components

These existing components will be reused:
- **KpiCard** — from `packages/ui/src/components/dashboard/kpi-card.tsx`
- **MarkdownRenderer** — from `packages/ui/src/components/chat/markdown-renderer.tsx`
- **SkeletonCard** — from `packages/ui/src/components/skeleton-card.tsx`
- **RbacGate** — from `packages/ui/src/components/rbac-gate.tsx`

New shared patterns:
- **DataTable** pattern (PeopleTable, OpportunitiesTable) — consistent table styling with sort headers
- **Badge** variants — status, severity, type badges (consistent color map)
- **TabNav** — consistent tab navigation for profile tabs and intelligence tabs
