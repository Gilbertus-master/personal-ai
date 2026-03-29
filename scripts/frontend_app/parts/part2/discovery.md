# Part 2: Dashboard & Alerts — Discovery Report

Generated: 2026-03-29

---

## 1. API Endpoint Inventory

### GET /brief/today
- **Params:** `force` (bool, default=false), `days` (int, default=14), `date` (string|null, YYYY-MM-DD)
- **Rate limit:** 30/min
- **Response:**
```typescript
interface MorningBriefResponse {
  status: string;             // "generated" | "cached" | "error"
  date: string | null;        // YYYY-MM-DD
  summary_id: number | null;
  period_start: string | null;
  period_end: string | null;
  events_count: number | null;
  open_loops_count: number | null;
  entities_count: number | null;
  summaries_count: number | null;
  text: string | null;        // Markdown content
  meta: { latency_ms: number };
}
```

### GET /alerts
- **Params:** `active_only` (bool, default=true), `alert_type` (string|null — "decision_no_followup"|"conflict_spike"|"missing_communication"|"health_clustering"), `severity` (string|null — "high"|"medium"|"low"), `limit` (int, default=50, max=50), `refresh` (bool, default=false), `date` (string|null)
- **Response:**
```typescript
interface AlertsResponse {
  alerts: AlertItem[];
  meta: Record<string, any>;
}
interface AlertItem {
  alert_id: number;
  alert_type: string;
  severity: string;           // "high" | "medium" | "low"
  title: string;
  description: string;
  evidence: string | null;
  is_active: boolean;
  created_at: string | null;
}
```

### GET /status
- **Params:** none
- **Rate limit:** 10/min (public endpoint)
- **Response:**
```typescript
interface StatusResponse {
  db: {
    documents: number;
    chunks: number;
    entities: number;
    events: number;
    insights: number | null;
    summaries: number;
    alerts: number | null;
  };
  embeddings: { total: number; done: number; pending: number };
  sources: Array<{ source_type: string; document_count: number; newest_date: string }>;
  last_backup: string;
  services: {
    postgres: { status: string; error?: string };
    qdrant: { status: string; error?: string };
    whisper: { status: string; error?: string };
  };
  cron_jobs: any[];
  latency_ms: number;
}
```

### POST /timeline
- **Body:**
```typescript
interface TimelineRequest {
  event_type?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;              // default=20, 1-500
}
```
- **Response:**
```typescript
interface TimelineResponse {
  events: TimelineEvent[];
  meta: Record<string, any>;
}
interface TimelineEvent {
  event_id: number;
  event_time: string | null;
  event_type: string;
  document_id: number;
  chunk_id: number;
  summary: string;
  entities: string[];
}
```

### GET /commitments
- **Params:** `person` (string|null), `status` (string, default="open"), `limit` (int, default=20)
- **Response (no person):**
```typescript
interface CommitmentsListResponse {
  commitments: Array<{
    id: number;
    person_name: string;
    commitment_text: string;
    deadline: string | null;
    status: string;            // "open"|"overdue"|"fulfilled"|"broken"|"cancelled"
    created_at: string;
  }>;
}
```
- **Response (with person):**
```typescript
interface CommitmentSummaryResponse {
  person_name: string;
  total: number;
  open: number;
  fulfilled: number;
  broken: number;
  overdue: number;
  cancelled: number;
}
```

### GET /costs/budget
- **Params:** none
- **Response:**
```typescript
interface BudgetResponse {
  daily_total_usd: number;
  budgets: Array<{
    scope: string;
    limit_usd: number;
    spent_usd: number;
    pct: number;
    hard_limit: boolean;
    status: string;            // "ok" | "warning" | "exceeded"
  }>;
  alerts_today: Array<{
    scope: string;
    type: string;
    message: string;
    at: string;
  }>;
}
```

### GET /observability/dashboard
- **Params:** `hours` (int, default=24)
- **Response:**
```typescript
interface ObservabilityResponse {
  stats: {
    period_hours: number;
    total_runs: number;
    avg_latency_ms: number;
    p50_ms: number;
    p95_ms: number;
    max_latency_ms: number;
    error_count: number;
    error_rate_pct: number;
    cache_hit_count: number;
    cache_hit_rate_pct: number;
    fallback_count: number;
  };
  stages: {
    avg_interpret_ms: number;
    avg_retrieve_ms: number;
    avg_answer_ms: number;
    bottleneck: string;
    bottleneck_pct: number;
  };
  cost: {
    runs_with_cost: number;
    total_input_tokens: number;
    total_output_tokens: number;
    total_cost_usd: number;
  };
  slowest_runs: Array<{
    run_id: number;
    at: string;
    query: string;
    latency_ms: number;
    model: string;
    error: boolean;
    stages: Record<string, any> | null;
  }>;
  recent_errors: Array<{
    run_id: number;
    at: string;
    query: string;
    latency_ms: number;
    error_message: string;
  }>;
  model_breakdown: Array<{
    model: string;
    runs: number;
    avg_ms: number;
    cost_usd: number;
  }>;
}
```

---

## 2. RBAC Rules — Dashboard Visibility

| Widget | gilbertus_admin | ceo | board | director | manager | specialist | operator |
|--------|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Morning Brief (full) | Y | Y | Y | - | - | - | - |
| Morning Brief (general) | Y | Y | Y | Y | Y | - | - |
| Alerts Feed | Y | Y | Y | - | - | - | - |
| KPI Grid (full) | Y | Y | - | - | - | - | - |
| KPI Grid (basic) | Y | Y | Y | - | - | - | - |
| Activity Timeline | Y | Y | Y | - | - | - | - |
| System Status | Y | Y | - | - | - | - | Y |
| Cron Health | Y | Y | - | - | - | - | Y |
| Quick Actions | Y | Y | Y | Y | Y | - | - |
| Notifications Bell | Y | Y | Y | Y | Y | Y | Y |
| Calendar Widget | - | - | - | Y | Y | - | - |
| Own Tasks | - | - | - | - | - | Y | - |

**Implementation strategy:**
- Use `<RbacGate roles={[...]}>`  from `@gilbertus/rbac` + `@gilbertus/ui`
- Use `useRole()` hook to conditionally render sections
- Operator sees ONLY system status section (services + crons)
- Specialist sees simplified view (own tasks + calendar)
- Director/Manager see brief (general) + calendar widget

**Relevant frontend RBAC hooks (already exist):**
- `useRole()` → `{ role: RoleName, roleLevel: number }`
- `usePermissions()` → `{ hasPermission(perm), permissions[] }`
- `<RbacGate roles={[...]} permission="..." fallback={...}>`

---

## 3. Existing Patterns to Follow

### File structure
```
apps/web/
  app/(app)/dashboard/
    page.tsx                  # Main dashboard page (currently placeholder)
    _components/              # Dashboard-specific components (NEW)
      morning-brief.tsx
      alerts-feed.tsx
      kpi-grid.tsx
      activity-timeline.tsx
      system-status.tsx
      quick-actions.tsx
  lib/
    stores/
      dashboard-store.ts      # NEW — Zustand store for dashboard state
    hooks/
      use-dashboard.ts        # NEW — data fetching hook
packages/
  api-client/src/
    dashboard.ts              # NEW — API functions for dashboard endpoints
    dashboard-types.ts        # NEW — TypeScript interfaces
  ui/src/components/
    (reuse existing: SkeletonCard, RbacGate, cn())
```

### Component pattern
```typescript
// 'use client' at top for interactive components
// Interface before function
// Destructured props with defaults
// CSS vars for colors: bg-[var(--surface)], text-[var(--text)]
// cn() for conditional classes
// Lucide icons
```

### API client pattern
```typescript
// In packages/api-client/src/dashboard.ts
export async function fetchBrief(params?: { force?: boolean; days?: number }): Promise<MorningBriefResponse> {
  return customFetch<MorningBriefResponse>({
    url: '/brief/today',
    method: 'GET',
    params: params ? Object.fromEntries(
      Object.entries(params).map(([k, v]) => [k, String(v)])
    ) : undefined,
  });
}
```

### State management pattern
```typescript
// Zustand with persist for user preferences (e.g., collapsed sections)
// TanStack Query for server data (already in Providers: staleTime 60s)
// Prefer useQuery() over manual fetch for auto-refresh, caching, loading states
```

### Styling
- CSS variables: `var(--bg)`, `var(--surface)`, `var(--border)`, `var(--text)`, `var(--accent)`, `var(--success)`, `var(--warning)`, `var(--danger)`
- Dark mode default, class-based
- Responsive: `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3`
- Cards: `rounded-lg bg-[var(--surface)] border border-[var(--border)] p-4`

---

## 4. Data Types / Interfaces Needed

All types listed in section 1 response shapes, plus:

```typescript
// Derived types for KPI cards
interface KpiCard {
  label: string;
  value: number | string;
  trend?: 'up' | 'down' | 'flat';
  trendValue?: string;        // e.g., "+12%"
  color?: 'default' | 'success' | 'warning' | 'danger';
  sparkline?: number[];       // historical values for mini chart
}

// For notifications bell
interface NotificationItem {
  id: number;
  type: 'alert' | 'commitment' | 'system';
  title: string;
  severity?: string;
  timestamp: string;
  read: boolean;
}

// Dashboard config (persisted in Zustand)
interface DashboardPreferences {
  collapsedSections: string[];
  autoRefresh: boolean;
  refreshInterval: number;    // ms, default 300000 (5 min)
}
```

---

## 5. Backend Gaps

| Gap | Impact | Workaround |
|-----|--------|------------|
| No SSE/WebSocket for real-time alerts | Must poll | Poll /alerts every 60s for notification bell |
| No dismiss/acknowledge endpoint for alerts | Cannot mark alerts as read | Need `POST /alerts/{id}/acknowledge` or `PUT /alerts/{id}` |
| No unified "notifications" endpoint | Must aggregate from multiple sources | Combine /alerts (active) + compose client-side |
| /status returns cron_jobs as static list, not live status | No last-run / next-run info | Use /crons/summary for richer cron data |
| No trend data for KPIs (historical counts) | Cannot show sparklines | Use /observability/dashboard for latency trends; for entity counts, would need new endpoint or calculate client-side from timeline |
| /commitments doesn't return total count in list mode | Need extra query for count | Use response array .length or add ?person=all for summary |
| No endpoint to mark notifications as read | Bell counter won't decrement | Store read state in localStorage or add backend endpoint |

**Recommended backend additions (nice-to-have, not blocking):**
1. `POST /alerts/{alert_id}/acknowledge` — mark alert as acknowledged
2. Add `total_count` to `/commitments` list response
3. Historical KPI snapshots endpoint (or use existing data to derive)

---

## 6. Complexity Estimates

| Feature | Complexity | Notes |
|---------|-----------|-------|
| Morning Brief | **Medium** | Markdown rendering (already have MarkdownRenderer), collapsible sections, force-refresh button |
| Alerts Feed | **Medium** | Color-coded severity, polling, dismiss needs backend gap resolution |
| KPI Grid | **Medium** | 4-6 cards, data from 3 endpoints, trend arrows (sparklines = complex, skip for MVP) |
| Activity Timeline | **Medium** | Scrollable list, type filters, POST body, pagination |
| System Status | **Simple** | Traffic-light indicators from /status services object |
| Quick Actions | **Simple** | 4 buttons routing to other pages or triggering actions |
| Notifications Bell | **Medium** | Polling, badge count, dropdown panel, read/unread state |
| RBAC gating | **Simple** | Already have RbacGate + useRole, just wire up |
| Auto-refresh | **Simple** | TanStack Query refetchInterval option |
| Skeleton loaders | **Simple** | Already have SkeletonCard component |
| Responsive layout | **Simple** | Tailwind grid, already established pattern |

**Overall module: MEDIUM complexity**
- ~8-10 new component files
- ~2 new API client files (functions + types)
- ~1 Zustand store (preferences)
- ~1 custom hook (data orchestration)
- Modify: Topbar (notification bell), dashboard/page.tsx

---

## 7. Implementation Priority (MVP)

1. **KPI Grid** — instant value, simple to implement
2. **Morning Brief** — core daily feature
3. **System Status** — operator needs it
4. **Alerts Feed** — critical for awareness
5. **Quick Actions** — simple routing buttons
6. **Activity Timeline** — medium effort, good value
7. **Notifications Bell** — enhance Topbar, requires polling setup

---

## 8. Key Decisions for Design Phase

1. **TanStack Query vs manual fetch?** → Use TanStack Query (already in Providers). Enables auto-refresh, caching, loading/error states out of the box.
2. **Sparklines for KPIs?** → Skip for MVP, just show number + trend arrow. Add sparklines in iteration.
3. **Alert dismiss without backend?** → Store dismissed IDs in localStorage for now. Flag as backend gap.
4. **Notification bell scope?** → MVP: show count of active alerts. Later: aggregate from multiple sources.
5. **Dashboard page: client or server component?** → Client component (`'use client'`). Multiple dynamic data sources, polling, interactive sections.
6. **Cron status source?** → Use `GET /crons/summary` instead of /status cron_jobs for richer data.
