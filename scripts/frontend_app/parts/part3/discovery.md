# Part 3: People & Intelligence — Discovery Report

**Generated:** 2026-03-29
**Module:** People Directory, Profiles, Sentiment, Intelligence, Scenarios

---

## 1. API Endpoint Inventory

### People Endpoints

| Method | Path | Params | Response Shape | Notes |
|--------|------|--------|----------------|-------|
| GET | `/people` | `?type=&status=&limit=100` | `{ people: Person[], meta: { count, latency_ms } }` | Filterable by relationship_type, status |
| POST | `/people` | Body: `PersonCreate` | `Person` (201) | Creates person + optional relationship |
| GET | `/people/{slug}` | — | `PersonFull` (person + roles_history + timeline + open_loops) | Full profile |
| PUT | `/people/{slug}` | Body: `PersonUpdate` | `Person` | Update person fields |
| DELETE | `/people/{slug}` | — | `{ deleted: true }` | Soft/hard delete |
| POST | `/people/{slug}/timeline` | Body: `TimelineEventCreate` | `TimelineEvent` | Add timeline event |
| POST | `/people/{slug}/roles` | Body: `RoleHistoryCreate` | `RoleHistory` | Add role history entry |
| POST | `/people/{slug}/loops` | Body: `OpenLoopCreate` | `OpenLoop` | Add open loop |
| PUT | `/people/{slug}/loops/{loop_id}` | — | `OpenLoop` | Close open loop |
| GET | `/scorecard/{person_slug}` | — | `{ person, data_volume, recent_events_30d, open_loops, event_profile_3m, weekly_activity }` | Rate limited 5/min |
| GET | `/sentiment/{person_slug}` | `?weeks=8` | Sentiment trend data | From sentiment_tracker |
| GET | `/sentiment-alerts` | — | Sentiment alert list | Global sentiment alerts |
| GET | `/delegation` | — | Delegation ranking report | All people |
| GET | `/delegation/{person_slug}` | `?months=3` | Delegation score for person | Per-person |
| GET | `/delegation-chain` | — | Delegation chain dashboard | Hierarchical view |
| POST | `/delegation-chain/check` | — | Check delegation status | Trigger check |
| POST | `/delegation-chain/delegate` | Body: delegation params | Delegate task | Create delegation |
| GET | `/network` | — | Communication network graph | From network_graph module |
| POST | `/evaluate` | Body: `{ person_slug, date_from?, date_to? }` | Evaluation result | Rate limited 5/min, CEO only |
| GET | `/wellbeing` | `?weeks=8` | Wellbeing trend | Board+ only |
| POST | `/wellbeing/check` | — | Current week assessment | Trigger check |

### Intelligence Endpoints

| Method | Path | Params | Response Shape | Notes |
|--------|------|--------|----------------|-------|
| GET | `/opportunities` | `?status=new&limit=20` | `Opportunity[]` (id, type, description, value_pln, effort_hours, roi, confidence, status, created) | Filterable by status |
| POST | `/opportunities/scan` | `?hours=2` | `{ status, events_scanned, chunks_scanned, opportunities_found, opportunities_saved, notification }` | Triggers AI scan |
| GET | `/inefficiency` | — | `{ generated_at, repeating_tasks[], escalation_bottlenecks[], meeting_overload[], summary }` | Full report |
| POST | `/correlate` | Body: `CorrelationRequest` | Varies by type (temporal/person/anomaly/report) | Rate limited 5/min |
| GET | `/scenarios` | `?status=&limit=20` | `Scenario[]` (id, title, description, type, status, trigger, total_impact_pln, outcome_count) | Filter by status |
| POST | `/scenarios` | `?title=&description=&scenario_type=risk` | `{ id, title, status: "draft" }` | Query params, not body! |
| POST | `/scenarios/{scenario_id}/analyze` | — | `{ scenario_id, title, outcomes[], total_impact_pln, latency_ms }` | AI-powered analysis |
| GET | `/scenarios/compare` | `?ids=1,2` | Comparison result | Compare 2+ scenarios |
| POST | `/scenarios/auto-scan` | — | Auto-generated scenarios | From risk signals |
| GET | `/predictions` | — | `{ escalation_risks[], communication_gaps[], deadline_risks[], total_alerts, new_stored, status }` | Predictive alerts |
| GET | `/org-health` | `?weeks=8` | `{ current_score, trend, history[], best_week, worst_week }` | Score 1-100 |
| POST | `/org-health/assess` | — | `{ id, week_start, overall_score, trend_vs_last_week, dimensions{}, top_risks[], top_improvements[] }` | Current week |

---

## 2. Data Types / Interfaces Needed

### People Types

```typescript
// Person (from /people list)
interface Person {
  id: number
  slug: string
  first_name: string
  last_name: string | null
  aliases: string[]
  created_at: string
  updated_at: string
  relationship: Relationship | null
}

interface Relationship {
  id: number
  relationship_type: string
  current_role: string | null
  organization: string | null
  status: string  // "active", "inactive", etc.
  contact_channel: string | null
  can_contact_directly: boolean
  sentiment: string  // "positive", "neutral", "negative"
  last_contact_date: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

// Full profile (from /people/{slug})
interface PersonFull extends Person {
  roles_history: RoleHistory[]
  timeline: TimelineEvent[]
  open_loops: OpenLoop[]
}

interface RoleHistory {
  id: number
  role: string
  organization: string | null
  date_from: string | null
  date_to: string | null
  notes: string | null
}

interface TimelineEvent {
  id: number
  event_date: string
  event_type: string | null
  description: string
  source: string
  created_at: string
}

interface OpenLoop {
  id: number
  description: string
  status: string
  created_at: string
  closed_at: string | null
}

// Create/Update
interface PersonCreate {
  slug: string
  first_name: string
  last_name?: string | null
  aliases?: string[] | null
  relationship?: RelationshipCreate | null
}

interface RelationshipCreate {
  relationship_type: string
  current_role?: string | null
  organization?: string | null
  status?: string  // default "active"
  contact_channel?: string | null
  can_contact_directly?: boolean  // default true
  sentiment?: string  // default "neutral"
  last_contact_date?: string | null
  notes?: string | null
}

// Scorecard
interface Scorecard {
  person: {
    name: string
    role: string | null
    org: string | null
    status: string | null
    sentiment: string | null
  }
  data_volume: { chunks: number; events: number }
  recent_events_30d: Array<{ type: string; time: string | null; summary: string }>
  open_loops: string[]
  event_profile_3m: Record<string, number>
  weekly_activity: Array<{ week: string; count: number }>
}

// Evaluation
interface EvaluateRequest {
  person_slug: string
  date_from?: string | null
  date_to?: string | null
}

interface EvaluationResult {
  // Fields from evaluate_person() — varies, includes AI-generated content
  latency_ms: number
}

// Correlation
interface CorrelationRequest {
  correlation_type: 'temporal' | 'person' | 'anomaly' | 'report'
  event_type_a?: string | null
  event_type_b?: string | null
  person?: string | null
  window?: 'week' | 'month'  // default "week"
}
```

### Intelligence Types

```typescript
interface Opportunity {
  id: number
  type: string  // opportunity_type
  description: string
  value_pln: number
  effort_hours: number
  roi: number
  confidence: number
  status: string  // "new", "analyzed", "accepted", "rejected"
  created: string
}

interface OpportunityScanResult {
  status: 'ok' | 'no_data'
  events_scanned: number
  chunks_scanned: number
  opportunities_found: number
  opportunities_saved: number
  notification: string | null
}

interface InefficiencyReport {
  generated_at: string
  repeating_tasks: Array<{
    type: string
    pattern: string
    weeks_seen: number
    total: number
    avg_confidence: number
    est_hours_per_month: number
    automation_potential: 'high' | 'medium'
  }>
  escalation_bottlenecks: Array<{
    person: string
    escalations: number
    interpretation: string
  }>
  meeting_overload: Array<{
    person: string
    date: string
    meetings: number
    interpretation: string
  }>
  summary: {
    repeating_patterns: number
    bottleneck_people: number
    overloaded_days: number
    est_automation_hours_per_month: number
    est_automation_savings_pln: number
  }
}

interface Scenario {
  id: number
  title: string
  description: string
  type: 'risk' | 'opportunity' | 'strategic'
  status: 'draft' | 'analyzed' | 'archived'
  trigger: string | null
  created_by: string
  created_at: string
  analyzed_at: string | null
  total_impact_pln: number
  outcome_count: number
}

interface ScenarioOutcome {
  dimension: 'revenue' | 'costs' | 'people' | 'operations' | 'reputation'
  impact_description: string
  impact_value_pln: number
  probability: number
  time_horizon: '1m' | '3m' | '6m' | '1y' | '3y'
  mitigation: string
}

interface ScenarioAnalysis {
  scenario_id: number
  title: string
  outcomes: ScenarioOutcome[]
  total_impact_pln: number
  latency_ms: number
}

interface PredictiveAlerts {
  escalation_risks: Array<{
    person_name: string
    alert_type: 'escalation_risk'
    risk: 'low' | 'medium' | 'high'
    probability: number
    recent_conflicts: number
    prediction: string | null
  }>
  communication_gaps: Array<{
    person_name: string
    alert_type: 'communication_gap'
    silence_days: number
    baseline_events_per_week: number
    prediction: string
  }>
  deadline_risks: Array<{
    commitment_id: number
    description: string
    days_until_deadline: number
    alert_type: 'deadline_risk'
    prediction: string
  }>
  total_alerts: number
  new_stored: number
  status: 'ok'
}

interface OrgHealth {
  current_score: number  // 1-100
  trend: 'improving' | 'declining' | 'stable'
  history: Array<{ week: string; score: number }>
  best_week: { week: string; score: number }
  worst_week: { week: string; score: number }
}

interface OrgHealthAssessment {
  id: number | null
  week_start: string
  overall_score: number
  trend_vs_last_week: number | null
  dimensions: Record<string, {
    score: number
    value: number
    weight: number
    label: string
  }>
  top_risks: string[]
  top_improvements: string[]
}
```

---

## 3. RBAC Rules

### Role Hierarchy
| Role | Level | Key Permissions |
|------|-------|----------------|
| gilbertus_admin | 99 | Full bypass |
| operator | 70 | Infra/dev only, no business data |
| ceo | 60 | Full business: `data:read:all`, `evaluations:read:all`, `communications:read:all` |
| board | 50 | `data:read:all`, `evaluations:read:reports` (no eval trigger) |
| director | 40 | `data:read:department`, `evaluations:read:reports`, `communications:read:department` |
| manager | 30 | `data:read:team` |
| specialist | 20 | `data:read:own` |

### Module Access (from frontend RBAC navigation.ts)
| Feature | Allowed Roles | Reason |
|---------|--------------|--------|
| **People directory** | ceo, board, director | `people` module in nav |
| **People evaluations** | ceo only | `evaluations:read:all` permission required |
| **Sentiment/wellbeing** | ceo, board | Board+ for trend data |
| **Network graph** | ceo, board | Board+ |
| **Intelligence module** | ceo, board | `intelligence` module in nav |
| **Scenarios** | ceo only (CRUD + analyze) | Strategic decisions |
| **Delegation** | ceo, board, director | Varies by scope |

### Data Scope Rules
- **director**: sees only own department's people
- **board**: sees all people but can only read evaluation reports (not trigger)
- **ceo**: full access — trigger evaluations, all people, all intelligence

---

## 4. Existing Patterns to Follow

### Project Structure (monorepo)
```
packages/api-client/src/  → API functions + types per module
packages/ui/src/components/ → Reusable UI components per module
packages/rbac/src/         → Role checks, navigation config
apps/web/app/(app)/        → Next.js App Router pages
apps/web/lib/stores/       → Zustand stores
apps/web/lib/hooks/        → Custom hooks (store + API orchestration)
```

### API Client Pattern
- All API calls go through `customFetch<T>()` from `packages/api-client/src/base.ts`
- Each module gets its own file: `people.ts`, `intelligence.ts`
- Types in separate file: `people-types.ts`, `intelligence-types.ts`
- Export from `packages/api-client/src/index.ts`

### State Management
- **Zustand** with `persist` middleware for UI state (collapsed sections, filters, dismissed items)
- **React Query** for server data (fetching, caching, refetch)
- Hooks combine store + API: `usePeople()`, `useIntelligence()`

### Component Patterns
- **shadcn/ui style** with Radix primitives
- **CSS variables**: `bg-[var(--surface)]`, `text-[var(--text)]`, `border-[var(--border)]`
- **Lucide icons** for all icons
- **KpiCard** pattern for metric display
- **Loading skeletons** with pulse animation
- **react-markdown** for rendering AI-generated content

### Routing
- Route groups: `(auth)` for login, `(app)` for protected
- Module pages: `/people`, `/people/[slug]`, `/intelligence`, etc.
- Layout nesting: root → app layout (sidebar + topbar) → module layout

---

## 5. Backend Gaps / Notes

### Missing or Needs Attention
1. **POST /scenarios** uses query params, not request body — frontend should send as query params
2. **No pagination** on most list endpoints (people has limit, scenarios has limit, but no offset/cursor)
3. **No SSE/WebSocket** for real-time updates — all polling-based
4. **Evaluation response** shape is dynamic (AI-generated) — need to handle flexible content
5. **Correlation response** varies by type — need union type handling
6. **No search endpoint** for people — filtering only by type/status, no text search (name search must be client-side)
7. **Sentiment/wellbeing** response shapes not fully typed in backend — need to read analysis module implementations for exact shapes
8. **Network graph** response format needs investigation — likely returns nodes + edges for d3/force-graph

### Extra Endpoints Found (not in original spec)
- `PUT /people/{slug}` — update person
- `DELETE /people/{slug}` — delete person
- `POST /people/{slug}/timeline` — add timeline event
- `POST /people/{slug}/roles` — add role history
- `POST /people/{slug}/loops` — add open loop
- `PUT /people/{slug}/loops/{loop_id}` — close loop
- `GET /delegation-chain` — delegation hierarchy
- `POST /delegation-chain/check` — check delegations
- `POST /delegation-chain/delegate` — delegate task
- `GET /scenarios/compare` — compare scenarios
- `POST /scenarios/auto-scan` — auto-generate scenarios
- `GET /sentiment-alerts` — global sentiment alerts
- `POST /wellbeing/check` — trigger wellbeing check

---

## 6. Complexity Estimates

### People Module
| Feature | Complexity | Notes |
|---------|-----------|-------|
| Directory (list + search + filters) | **Medium** | Table with client-side search, filter chips, sorting |
| Profile page | **Complex** | Multi-section: scorecard KPIs, timeline, open loops, sentiment chart, delegation score, roles history |
| Evaluation trigger + history | **Medium** | Form (person + date range), loading state for AI, result display |
| Network Graph | **Complex** | d3-force or react-force-graph, node styling, interaction, responsive |
| Wellbeing trends | **Simple** | Line chart (recharts), board+ gate |

### Intelligence Module
| Feature | Complexity | Notes |
|---------|-----------|-------|
| Opportunities table | **Medium** | Sortable table, status badges, scan trigger button, ROI formatting |
| Inefficiencies report | **Simple** | Markdown-ish rendering of structured report sections |
| Correlation explorer | **Complex** | Multi-step: type selector → dynamic params → varied result display (charts for temporal, profile for person) |
| Scenarios CRUD + analyze | **Complex** | List, create form, analyze trigger (AI), outcome display, compare view |
| Predictions | **Medium** | 3-section alert display (escalation, gaps, deadlines), severity badges |
| Org Health | **Medium** | Score gauge, trend chart, dimension breakdown, assess trigger |

### Total Estimate
- **Simple:** 2 features
- **Medium:** 4 features
- **Complex:** 4 features
- **Overall module complexity:** High — significant variety in data shapes and visualizations
