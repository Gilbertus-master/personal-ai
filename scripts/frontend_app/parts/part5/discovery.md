# Part 5: Market, Finance & Process Intelligence — Discovery Report

**Generated:** 2026-03-29

---

## 1. API Endpoint Inventory

### Market Intelligence (5 endpoints)

| Method | Path | Params | Response | Complexity |
|--------|------|--------|----------|------------|
| GET | `/market/dashboard` | `?days=7` | `{insights[], alerts[], stats{by_type, total_insights, active_alerts}, sources[]}` | Medium |
| POST | `/market/scan` | — | `{success, fetch{sources_checked, new_items}, analysis{insights_created, alerts_created}}` | Simple |
| GET | `/market/insights` | `?insight_type=&min_relevance=0&limit=20` | `[{id, type, title, description, impact, relevance, companies[], created_at}]` | Simple |
| POST | `/market/sources` | `?name=&url=&source_type=rss` | `{id, name, url, source_type}` | Simple |
| GET | `/market/alerts` | `?acknowledged=false` | `[{id, level, message, acknowledged, created_at, insight_title, insight_type, relevance}]` | Simple |

**Missing:** No `PUT/DELETE` for sources. No `POST /market/alerts/{id}/acknowledge` endpoint (must use raw DB or missing endpoint). No alert dismiss endpoint found.

### Competitor Intelligence (5 endpoints)

| Method | Path | Params | Response | Complexity |
|--------|------|--------|----------|------------|
| GET | `/competitors` | — | `{competitors[{id, name, krs, industry, watch_level, recent_signals_30d, high_severity, latest_analysis}], total, active_count}` | Medium |
| POST | `/competitors` | `?name=&krs_number=&industry=energia&watch_level=active` | `{id, name, watch_level}` | Simple |
| POST | `/competitors/scan` | — | `{success, signals_collected{}, competitors_analyzed, analysis_summaries[], landscape{}}` | Simple |
| GET | `/competitors/{competitor_id}/analysis` | — | `{competitor, swot{strengths[], weaknesses[], threats[], opportunities[], summary}, signals_count}` | Medium |
| GET | `/competitors/signals` | `?competitor_id=&signal_type=&days=30` | `[{id, competitor, type, title, description, severity, date, source_url}]` | Simple |

**Missing:** No `DELETE /competitors/{id}`. No `PUT /competitors/{id}` for editing watch_level. Competitor params are query strings not body — unusual but must follow.

### Finance (5 endpoints)

| Method | Path | Params | Response | Complexity |
|--------|------|--------|----------|------------|
| GET | `/finance` | `?company=` | `{companies{[name]:{latest_metrics, budget_utilization[], alerts[]}}, active_alerts, api_costs{monthly[], avg_monthly_usd, trend, current_month_forecast_usd}, total_budget_utilization}` | Complex |
| POST | `/finance/metric` | — | Body: `{company, metric_type, value, period_start, period_end, source?}` → `{id, company, metric_type, value}` | Simple |
| POST | `/finance/budget` | — | Body: `{company, category, planned_amount, period_start, period_end}` → `{id, company, category, planned_amount}` | Simple |
| POST | `/finance/estimate-cost` | — | Body: `{description}` → `{direct_cost_pln, roi_ratio, payback_months, recommendation, ...}` | Medium |

### Cost Tracking (1 endpoint)

| Method | Path | Params | Response | Complexity |
|--------|------|--------|----------|------------|
| GET | `/costs/budget` | — | `{daily_total_usd, budgets[{scope, limit_usd, spent_usd, pct, hard_limit, status}], alerts_today[]}` | Medium |

### Strategic Goals (4 endpoints)

| Method | Path | Params | Response | Complexity |
|--------|------|--------|----------|------------|
| GET | `/goals` | — | `{total_goals, by_status{}, by_area{}, top_risks[], recently_achieved[], upcoming_deadlines[]}` | Medium |
| GET | `/goals/{goal_id}` | — | `{id, title, description, company, area, target/current_value, deadline, status, sub_goals[], dependencies[], progress[]}` | Complex |
| POST | `/goals` | — | Body: `{title, target_value, unit?, deadline?, company?, area?}` → `{id, title, ...}` | Simple |
| POST | `/goals/{goal_id}/progress` | — | Body: `{value, note?}` → `{goal_id, progress_id, date, value, status, status_changed}` | Simple |

### Process Intelligence (16 endpoints)

| Method | Path | Params | Response | Complexity |
|--------|------|--------|----------|------------|
| GET | `/process-intel/dashboard` | — | `{business_lines, apps[], optimizations{}, workforce_automation?, tech_radar?}` | Complex |
| GET | `/process-intel/business-lines` | — | `{business_lines[{id, name, description, importance, signals, status}]}` | Simple |
| POST | `/process-intel/discover` | — | `{message, business_lines, new, timestamp}` | Simple |
| GET | `/process-intel/processes` | `?process_type=` | `[{id, name, process_type, frequency, automation_potential, ...}]` | Medium |
| POST | `/process-intel/mine` | — | `{message, processes, new, timestamp}` | Simple |
| GET | `/process-intel/apps` | — | `[{name, category, mentions, replacement, status}]` | Simple |
| POST | `/process-intel/scan-apps` | — | `{message, scanned, apps_found}` | Simple |
| POST | `/process-intel/scan-apps-deep` | — | `{message, apps_discovered, sources{}, new_apps[], updated_apps[]}` | Simple |
| GET | `/process-intel/app-analysis` | — | `[{id, name, vendor, category, user_details[], cost_monthly_pln, replacement_feasibility, ...}]` | Complex |
| GET | `/process-intel/app-analysis/{app_id}` | — | Single app deep analysis | Medium |
| POST | `/process-intel/app-costs` | — | `{total_monthly_pln, total_yearly_pln, cost_breakdown[]}` | Medium |
| GET | `/process-intel/app-replacement-ranking` | — | `{ranking[{rank, app_name, replacement_priority, annual_savings, feasibility, ...}]}` | Medium |
| GET | `/process-intel/flows` | — | `[{flow, source, channel, frequency, volume, automation, bottleneck}]` | Medium |
| POST | `/process-intel/map-flows` | — | `{message, flows_mapped, new_flows, bottlenecks_detected}` | Simple |
| GET | `/process-intel/optimizations` | — | `{total_plans, total_time_savings_hours, total_cost_savings_pln, plans[]}` | Medium |
| POST | `/process-intel/plan` | — | `{message, plans_generated, total_potential_savings}` | Simple |

### Workforce Analysis — CEO Only (5 endpoints)

| Method | Path | Params | Response | Complexity |
|--------|------|--------|----------|------------|
| POST | `/process-intel/analyze-employee/{person_slug}` | — | `{person_name, work_activities[], automatable_pct, replaceability_score, automation_roadmap[], ...}` | Complex |
| POST | `/process-intel/analyze-all-employees` | `?organization=` | `{message, analyzed, total_automatable_pct, total_monthly_savings_pln, by_role{}}` | Simple |
| GET | `/process-intel/work-profile/{person_slug}` | — | Same as analyze-employee (cached) | Medium |
| GET | `/process-intel/automation-overview` | — | `{total_employees, analyzed, avg_automatable_pct, top_automation_candidates[]}` | Medium |
| GET | `/process-intel/automation-roadmap` | — | `{total_initiatives, roadmap[{quarter, initiatives[]}]}` | Medium |

### Tech Radar (6 endpoints)

| Method | Path | Params | Response | Complexity |
|--------|------|--------|----------|------------|
| POST | `/process-intel/discover-tech` | — | `{message, solutions_discovered, total_dev_hours, total_annual_savings, avg_roi}` | Simple |
| GET | `/process-intel/tech-radar` | — | `{by_type{build,buy,extend}, by_status{}, top_10_by_roi[], total_solutions, total_estimated_savings_pln}` | Complex |
| GET | `/process-intel/tech-radar/{solution_id}` | — | Single solution detail | Simple |
| GET | `/process-intel/tech-roadmap` | — | `{roadmap[{quarter, solutions[]}], total_quarters, total_dev_hours}` | Medium |
| POST | `/process-intel/tech-solution/{solution_id}/status` | `?status=approved` | `{message, solution_id, new_status}` | Simple |
| GET | `/process-intel/tech-strategic-alignment` | — | `{strategic_goals[{goal_id, goal_name, supporting_solutions[]}], total_alignment_coverage}` | Medium |

---

## 2. RBAC Rules

| Feature | Min Role | Permission | Notes |
|---------|----------|------------|-------|
| Market dashboard & insights | director+ | `data:read:department` | Directors see department scope |
| Market sources management | director+ | `data:read:department` | Add RSS sources |
| Competitors landscape | board+ | `data:read:all` | SWOT, signals, scan |
| Finance dashboard | board+ | `financials:read` | Budget, metrics, API costs |
| Finance metric/budget write | board+ | `financials:read` | No separate write permission defined |
| Goals | board+ | `financials:read` | Create, update progress |
| Process intel dashboard | director+ | `data:read:department` | Business lines, processes, apps |
| Process intel scan/mine | director+ | `data:read:department` | Trigger discovery actions |
| Workforce analysis | ceo only | `evaluations:read:all` | Employee automation, replaceability |
| Tech radar | board+ | `config:write:system` | View and manage solutions |

### Frontend RBAC Implementation Pattern
```typescript
// Use RbacGate component:
<RbacGate roles={['ceo', 'board']} permission="financials:read" fallback={<AccessDenied />}>
  <FinanceContent />
</RbacGate>

// Use hooks:
const { role } = useRole();
const { hasPermission } = usePermissions();
```

---

## 3. Existing Patterns to Follow

### API Client (`/frontend/packages/api-client/`)
- `customFetch<T>(config)` in `base.ts` — typed fetch wrapper
- API base URL: `NEXT_PUBLIC_GILBERTUS_API_URL` (default `http://127.0.0.1:8000`)
- Auth via `X-API-Key` header
- Auto-redirect to `/login` on 401
- Each domain gets its own file (e.g., `chat.ts`, `dashboard.ts`, `intelligence.ts`)

```typescript
// Pattern: export async function per endpoint
export async function getMarketDashboard(params?: { days?: number }): Promise<MarketDashboard> {
  return customFetch<MarketDashboard>({
    url: '/market/dashboard',
    method: 'GET',
    params,
  });
}
```

### React Query Hooks (`/frontend/apps/web/lib/hooks/`)
- One `use-{domain}.ts` file per feature area
- Wrap `useQuery` / `useMutation` with typed keys and functions
- Query keys: `['entity', ...filters]`
- `staleTime: 60_000` default
- Support `refetchInterval` via store settings

```typescript
export function useMarketDashboard(days?: number) {
  return useQuery<MarketDashboard>({
    queryKey: ['market-dashboard', days],
    queryFn: () => getMarketDashboard({ days }),
  });
}
```

### Zustand Stores (`/frontend/apps/web/lib/stores/`)
- Per-feature store with `persist` middleware
- Store UI preferences (collapsed sections, active tabs, filters)
- LocalStorage namespace: `gilbertus-{feature}`

### Page Components (`/frontend/apps/web/app/(app)/`)
- App Router: `(app)/{feature}/page.tsx`
- Get role via `useRole()`, gate via `<RbacGate>`
- Role-specific views (CEO vs director vs specialist)
- Use hooks for data, stores for UI state

### UI Components (`/frontend/packages/ui/`)
- shadcn/ui based, exported from `@gilbertus/ui`
- Tailwind CSS v4 with CSS variables (`--bg`, `--text`, `--accent`, etc.)
- Existing patterns: `KpiGrid`, `AlertsFeed`, `ActivityTimeline`

---

## 4. Data Types / Interfaces Needed

### Market Module
```typescript
interface MarketInsight {
  id: number; type: 'price_change'|'regulation'|'tender'|'trend'|'risk';
  title: string; description: string; impact: string;
  relevance: number; companies: string[]; created_at: string;
}
interface MarketAlert {
  id: number; level: 'info'|'warning'|'critical';
  message: string; acknowledged: boolean; created_at: string;
  insight_title: string; insight_type: string; relevance: number;
}
interface MarketSource {
  name: string; last_fetched: string|null; active: boolean;
  id?: number; url?: string; source_type?: 'rss'|'api'|'web';
}
interface MarketDashboard {
  insights: MarketInsight[]; alerts: MarketAlert[];
  stats: { by_type: Record<string,number>; total_insights: number; active_alerts: number };
  sources: MarketSource[];
}
```

### Competitor Module
```typescript
interface Competitor {
  id: number; name: string; krs: string; industry: string;
  watch_level: 'active'|'passive'|'archived';
  recent_signals_30d: number; high_severity: number;
  latest_analysis?: string; analysis_date?: string;
}
interface CompetitorSignal {
  id: number; competitor: string;
  type: 'krs_change'|'hiring'|'media'|'tender'|'financial';
  title: string; description: string;
  severity: 'low'|'medium'|'high';
  date: string|null; source_url: string;
}
interface SwotAnalysis {
  competitor: string;
  swot: { strengths: string[]; weaknesses: string[]; threats: string[]; opportunities: string[]; summary: string };
  signals_count: number;
}
```

### Finance Module
```typescript
interface FinanceDashboard {
  companies: Record<string, {
    latest_metrics: Record<string, { value: number; currency: string; period_start: string; source: string }>;
    budget_utilization: { category: string; planned: number; actual: number; pct: number; currency: string }[];
    alerts: { alert_type: string; description: string; severity: string; created_at: string }[];
  }>;
  active_alerts: number;
  api_costs: { monthly: { month: string; total_usd: number; api_calls: number }[]; avg_monthly_usd: number; trend: string; current_month_forecast_usd: number };
  total_budget_utilization: number;
}
interface CostBudget {
  daily_total_usd: number;
  budgets: { scope: string; limit_usd: number; spent_usd: number; pct: number; hard_limit: boolean; status: 'ok'|'warning'|'exceeded' }[];
  alerts_today: { scope: string; type: string; message: string; at: string }[];
}
interface StrategicGoal {
  id: number; title: string; description: string; company: string;
  area: 'business'|'trading'|'operations'|'people'|'technology'|'wellbeing';
  target_value: number; current_value: number; unit: string;
  deadline: string; status: 'on_track'|'at_risk'|'behind'|'achieved'|'cancelled';
  pct_complete: number; sub_goals?: any[]; dependencies?: any[]; progress?: any[];
}
```

### Process Intelligence Module
```typescript
interface ProcessIntelDashboard {
  business_lines: { business_lines: BusinessLine[] };
  apps: AppInventoryItem[];
  optimizations: { total_plans: number; total_time_savings_hours: number; total_cost_savings_pln: number; plans: any[] };
  workforce_automation?: any;
  tech_radar?: any;
}
interface BusinessLine {
  id: number; name: string; description: string; key_entities: string[];
  importance: 'low'|'medium'|'high'|'critical'; signals: number;
  status: 'active'|'archived'|'merged'; discovered_at: string;
}
interface DiscoveredProcess {
  id: number; name: string; description: string;
  process_type: 'decision'|'approval'|'reporting'|'trading'|'compliance'|'communication'|'operational';
  frequency: 'daily'|'weekly'|'monthly'|'quarterly'|'ad_hoc';
  participants: any[]; steps: any[]; tools_used: any[];
  automation_potential: number; automation_notes: string;
  status: 'discovered'|'confirmed'|'automated'|'archived';
}
interface AppInventoryItem {
  name: string; category: string; mentions: number;
  replacement: string; status: 'not_planned'|'planned'|'partial'|'replaced'|'not_replaceable';
}
interface AppDeepAnalysis extends AppInventoryItem {
  id: number; vendor: string; discovery_sources: any[];
  supported_processes: any[]; user_details: { user: string; role: string; usage_frequency: string }[];
  data_flow_types: any[]; cost_monthly_pln: number; cost_yearly_pln: number;
  replacement_feasibility: number; replacement_plan: any; tco_analysis: any;
}
interface DataFlow {
  flow: string; source: string; channel: string;
  frequency: 'daily'|'weekly'|'monthly'|'occasional';
  volume: number; automation: 'manual'|'semi_auto'|'automated'|'gilbertus';
  bottleneck: 'low'|'medium'|'high';
}
interface EmployeeWorkProfile {
  person_name: string; person_role: string;
  work_activities: { activity: string; category: string; frequency: string; hours_per_week: number; automation_potential: number }[];
  automatable_pct: number; replaceability_score: number;
  automation_roadmap: { task: string; gilbertus_module: string; dev_hours: number; savings_monthly_pln: number; priority: number }[];
}
interface TechSolution {
  id: number; name: string; solution_type: 'build'|'buy'|'extend';
  estimated_dev_hours: number; estimated_cost_pln: number;
  estimated_annual_savings_pln: number; roi_ratio: number;
  payback_months: number; strategic_alignment_score: number;
  status: 'proposed'|'approved'|'in_development'|'deployed'|'rejected';
  risk_notes: string;
}
```

---

## 5. Backend Gaps

| Gap | Impact | Workaround |
|-----|--------|------------|
| No `POST /market/alerts/{id}/acknowledge` | Cannot acknowledge/dismiss alerts from UI | Need new endpoint or use raw SQL (bad) |
| No `DELETE /market/sources/{id}` | Cannot remove RSS sources | Need new endpoint |
| No `PUT /competitors/{id}` | Cannot edit competitor watch_level | Need new endpoint |
| No `DELETE /competitors/{id}` | Cannot remove competitors | Need new endpoint |
| No `DELETE /goals/{id}` | Cannot delete/cancel goals | Need new endpoint |
| Competitor add uses query params not body | Inconsistent with other POST endpoints | Frontend must use query params |
| Market source add uses query params not body | Same inconsistency | Frontend must use query params |
| No pagination on any listing endpoint | Large datasets will be slow | Client-side pagination for now |
| No SSE/WebSocket for scan progress | Scans run synchronously, may timeout | Show loading spinner, handle timeouts |
| Tech radar has no quadrant field | Frontend needs adopt/trial/assess/hold categories | Map `status` field or add quadrant to backend |

---

## 6. Complexity Estimates

### Market Module — **Medium**
| Feature | Complexity | Notes |
|---------|------------|-------|
| Market dashboard | Medium | Aggregated view with stats, charts by type |
| Insights feed | Simple | Filterable list with type/relevance badges |
| Market alerts | Simple | List with acknowledge action (needs backend) |
| RSS sources management | Simple | Table + add form (no edit/delete yet) |
| Scan trigger | Simple | Button with loading state |

### Competitor Module — **Medium**
| Feature | Complexity | Notes |
|---------|------------|-------|
| Competitor landscape table | Medium | Table with signal counts, severity indicators |
| Add competitor | Simple | Form with 4 fields |
| SWOT analysis detail | Medium | Structured card layout for S/W/O/T |
| Signals timeline | Medium | Filterable list with severity + type badges |
| Scan trigger | Simple | Button with loading |

### Finance Module — **Complex**
| Feature | Complexity | Notes |
|---------|------------|-------|
| Finance dashboard | Complex | Multi-company metrics, budget bars, API cost charts |
| Budget utilization bars | Medium | Progress bars per category with thresholds |
| API cost tracker | Complex | Per-model, per-module breakdown + trend line chart |
| Cost budget status | Medium | Daily spend vs limits with status indicators |
| Goals list | Medium | Grouped by area/status with progress indicators |
| Goal detail | Complex | Tree with sub-goals, dependencies, progress history chart |
| Create goal | Simple | Form with 6 fields |
| Update goal progress | Simple | Value input + optional note |

### Process Intelligence Module — **Complex**
| Feature | Complexity | Notes |
|---------|------------|-------|
| PI dashboard | Complex | Aggregates business lines, apps, optimizations, tech |
| Business lines | Simple | Card grid with importance badges |
| Process discovery | Medium | Filterable list with automation potential bars |
| App inventory | Medium | Table with status, mentions, replacement info |
| App deep analysis | Complex | Cost breakdown, user details, replacement plan |
| App ranking | Medium | Ranked table with savings projections |
| Data flows | Complex | Flow diagram visualization (Sankey or similar) |
| Optimization plans | Medium | Priority-sorted cards with savings |
| Workforce analysis (CEO) | Complex | Per-person breakdown, replaceability scores |
| Automation roadmap | Medium | Quarterly timeline view |
| Tech radar | Complex | Quadrant chart (needs custom viz or D3) |
| Tech roadmap | Medium | Quarterly timeline with solutions |

### Overall Part 5 Complexity: **Complex** (largest part)
- ~42 endpoints to integrate
- 3 major modules with sub-views
- Charts required: trend lines, progress bars, radar/quadrant, flow diagrams
- CEO-only gating for workforce section

---

## 7. Recommended Page Structure

```
(app)/
├── market/
│   ├── page.tsx              # Dashboard + insights feed
│   ├── alerts/page.tsx       # Alert list with acknowledge
│   ├── sources/page.tsx      # RSS source management
│   └── competitors/
│       ├── page.tsx           # Landscape table
│       ├── [id]/page.tsx      # SWOT detail + signals
│       └── signals/page.tsx   # All signals timeline
├── finance/
│   ├── page.tsx              # Dashboard: metrics + budget + API costs
│   ├── costs/page.tsx        # Detailed cost budget view
│   └── goals/
│       ├── page.tsx           # Goals list
│       └── [id]/page.tsx      # Goal detail with tree
├── process/
│   ├── page.tsx              # PI dashboard overview
│   ├── apps/
│   │   ├── page.tsx           # App inventory + ranking
│   │   └── [id]/page.tsx      # Deep analysis
│   ├── flows/page.tsx        # Data flow visualization
│   ├── tech-radar/page.tsx   # Radar chart + roadmap
│   └── workforce/page.tsx    # CEO-only automation analysis
```

---

## 8. New Files Needed

### API Client
- `packages/api-client/src/market.ts` — Market + competitor endpoints
- `packages/api-client/src/finance.ts` — Finance + costs + goals endpoints
- `packages/api-client/src/process-intel.ts` — Process intelligence endpoints

### Types
- `packages/api-client/src/types/market-types.ts`
- `packages/api-client/src/types/finance-types.ts`
- `packages/api-client/src/types/process-types.ts`

### Hooks
- `apps/web/lib/hooks/use-market.ts`
- `apps/web/lib/hooks/use-finance.ts`
- `apps/web/lib/hooks/use-process-intel.ts`

### Stores
- `apps/web/lib/stores/market-store.ts` — Active tab, filters, dismissed alerts
- `apps/web/lib/stores/finance-store.ts` — Selected company, active tab
- `apps/web/lib/stores/process-store.ts` — Active section, filters

### UI Components
- `packages/ui/src/components/market/` — InsightCard, AlertItem, SourceTable, CompetitorTable, SwotCard, SignalTimeline
- `packages/ui/src/components/finance/` — BudgetBar, CostChart, MetricCard, GoalCard, GoalTree, ProgressChart
- `packages/ui/src/components/process/` — BusinessLineCard, ProcessCard, AppTable, FlowDiagram, TechRadarChart, WorkforceTable, RoadmapTimeline
