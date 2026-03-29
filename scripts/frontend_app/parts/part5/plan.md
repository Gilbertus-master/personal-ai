# Part 5: Market, Finance & Process Intelligence — Architecture Plan

**Generated:** 2026-03-29

---

## 1. Component Tree

```
<AppLayout>
  ├── <MarketPage>                          # /market
  │   ├── <RbacGate roles={['director','board','ceo']} permission="data:read:department">
  │   │   ├── <MarketDashboardHeader />      # Stats KPIs + scan button
  │   │   ├── <MarketInsightsFeed />         # Filterable insights list
  │   │   │   └── <InsightCard />*           # Per-insight: type badge, relevance, impact
  │   │   ├── <MarketAlertsBanner />         # Active alerts summary
  │   │   └── <MarketSourcesPanel />         # Collapsible sources overview
  │   └── </RbacGate>
  │
  ├── <MarketAlertsPage>                    # /market/alerts
  │   ├── <RbacGate roles={['director','board','ceo']}>
  │   │   ├── <AlertsFilterBar />            # Filter by level, acknowledged
  │   │   └── <AlertsList />
  │   │       └── <AlertItem />*             # Level badge, acknowledge button
  │   └── </RbacGate>
  │
  ├── <MarketSourcesPage>                   # /market/sources
  │   ├── <RbacGate roles={['director','board','ceo']}>
  │   │   ├── <AddSourceForm />              # Name, URL, type
  │   │   └── <SourcesTable />               # Name, URL, type, last_fetched, active
  │   └── </RbacGate>
  │
  ├── <CompetitorsPage>                     # /market/competitors
  │   ├── <RbacGate roles={['board','ceo']} permission="data:read:all">
  │   │   ├── <CompetitorToolbar />          # Add competitor + scan button
  │   │   ├── <CompetitorTable />            # Name, industry, watch_level, signals, severity
  │   │   └── <AddCompetitorDialog />        # Modal form
  │   └── </RbacGate>
  │
  ├── <CompetitorDetailPage>                # /market/competitors/[id]
  │   ├── <RbacGate roles={['board','ceo']}>
  │   │   ├── <CompetitorHeader />           # Name, KRS, industry, watch_level
  │   │   ├── <SwotCard />                   # 4-quadrant SWOT display
  │   │   └── <SignalTimeline />             # Chronological signals list
  │   │       └── <SignalItem />*            # Type badge, severity, date
  │   └── </RbacGate>
  │
  ├── <CompetitorSignalsPage>               # /market/competitors/signals
  │   ├── <RbacGate roles={['board','ceo']}>
  │   │   ├── <SignalsFilterBar />           # By competitor, type, days
  │   │   └── <SignalTimeline />             # Reused
  │   └── </RbacGate>
  │
  ├── <FinancePage>                         # /finance
  │   ├── <RbacGate roles={['board','ceo']} permission="financials:read">
  │   │   ├── <FinanceKpiRow />              # Active alerts, total utilization, API cost trend
  │   │   ├── <CompanyMetricsGrid />         # Per-company: latest metrics cards
  │   │   │   └── <CompanyMetricCard />*
  │   │   ├── <BudgetUtilizationSection />   # Per-company budget bars
  │   │   │   └── <BudgetBar />*             # Category, planned vs actual, pct
  │   │   ├── <ApiCostSection />             # Monthly cost chart + forecast
  │   │   │   ├── <CostTrendChart />         # Recharts line chart
  │   │   │   └── <CostForecastBadge />
  │   │   └── <FinanceAlertsList />          # Finance-specific alerts
  │   └── </RbacGate>
  │
  ├── <CostsPage>                           # /finance/costs
  │   ├── <RbacGate roles={['board','ceo']}>
  │   │   ├── <DailySpendKpi />              # daily_total_usd
  │   │   ├── <BudgetScopeTable />           # Per-scope: limit, spent, pct, status
  │   │   └── <CostAlertsFeed />             # Today's cost alerts
  │   └── </RbacGate>
  │
  ├── <GoalsPage>                           # /finance/goals
  │   ├── <RbacGate roles={['board','ceo']}>
  │   │   ├── <GoalsToolbar />               # Create goal button + area/status filters
  │   │   ├── <GoalsSummaryKpis />           # Total, by_status, top_risks
  │   │   ├── <GoalsGrid />                  # Grouped by area
  │   │   │   └── <GoalCard />*              # Title, progress bar, status badge, deadline
  │   │   └── <CreateGoalDialog />           # Modal form
  │   └── </RbacGate>
  │
  ├── <GoalDetailPage>                      # /finance/goals/[id]
  │   ├── <RbacGate roles={['board','ceo']}>
  │   │   ├── <GoalHeader />                 # Title, area, company, status, deadline
  │   │   ├── <GoalProgressChart />          # Recharts: progress over time
  │   │   ├── <SubGoalsTree />               # Nested sub-goals with progress
  │   │   ├── <GoalDependencies />           # Dependency links
  │   │   └── <UpdateProgressForm />         # Value + note input
  │   └── </RbacGate>
  │
  ├── <ProcessPage>                         # /process
  │   ├── <RbacGate roles={['director','board','ceo']} permission="data:read:department">
  │   │   ├── <ProcessDashboardKpis />       # Business lines count, apps, optimizations savings
  │   │   ├── <BusinessLinesGrid />          # Card grid
  │   │   │   └── <BusinessLineCard />*      # Name, importance badge, signals count
  │   │   ├── <ProcessDiscoverySection />    # Processes list + mine button
  │   │   │   └── <ProcessCard />*           # Name, type, frequency, automation potential bar
  │   │   └── <OptimizationsSummary />       # Top optimizations with savings
  │   └── </RbacGate>
  │
  ├── <AppsPage>                            # /process/apps
  │   ├── <RbacGate roles={['director','board','ceo']}>
  │   │   ├── <AppToolbar />                 # Scan buttons (quick + deep)
  │   │   ├── <AppInventoryTable />          # Name, category, mentions, replacement, status
  │   │   ├── <AppRankingTable />            # Replacement ranking with savings
  │   │   └── <AppCostSummary />             # Total monthly/yearly + breakdown
  │   └── </RbacGate>
  │
  ├── <AppDetailPage>                       # /process/apps/[id]
  │   ├── <RbacGate roles={['director','board','ceo']}>
  │   │   ├── <AppHeader />                  # Name, vendor, category, cost
  │   │   ├── <AppUserDetails />             # User table with roles, frequency
  │   │   ├── <AppProcesses />               # Supported processes
  │   │   ├── <AppCostBreakdown />           # TCO analysis
  │   │   └── <AppReplacementPlan />         # Feasibility, plan, timeline
  │   └── </RbacGate>
  │
  ├── <FlowsPage>                           # /process/flows
  │   ├── <RbacGate roles={['director','board','ceo']}>
  │   │   ├── <FlowToolbar />                # Map flows button
  │   │   ├── <FlowTable />                  # Tabular view: source, channel, freq, automation, bottleneck
  │   │   └── <FlowBottleneckIndicators />   # Summary of bottlenecks
  │   └── </RbacGate>
  │
  ├── <TechRadarPage>                       # /process/tech-radar
  │   ├── <RbacGate roles={['board','ceo']} permission="config:write:system">
  │   │   ├── <TechRadarChart />             # Quadrant visualization (adopt/trial/assess/hold)
  │   │   ├── <TechSolutionsList />          # Filterable list by type/status
  │   │   │   └── <TechSolutionCard />*      # ROI, dev hours, savings, status actions
  │   │   ├── <TechRoadmapTimeline />        # Quarterly view
  │   │   ├── <StrategicAlignmentView />     # Goals → solutions mapping
  │   │   └── <DiscoverTechButton />         # Trigger discovery
  │   └── </RbacGate>
  │
  └── <WorkforcePage>                       # /process/workforce
      ├── <RbacGate roles={['ceo']} permission="evaluations:read:all">
      │   ├── <AutomationOverviewKpis />     # Total employees, avg automatable %, savings
      │   ├── <AutomationCandidatesTable />  # Top candidates with scores
      │   ├── <EmployeeProfileSection />     # Expandable per-person analysis
      │   │   ├── <WorkActivitiesTable />    # Activities with automation potential bars
      │   │   └── <AutomationRoadmapCards /> # Per-task automation plan
      │   ├── <AutomationRoadmapTimeline />  # Quarterly initiatives
      │   └── <AnalyzeAllButton />           # Trigger full analysis
      └── </RbacGate>
```

---

## 2. File Tree

```
frontend/
├── packages/
│   ├── api-client/src/
│   │   ├── market.ts                          # Market + competitor API functions
│   │   ├── market-types.ts                    # Market/competitor interfaces
│   │   ├── finance.ts                         # Finance + costs + goals API functions
│   │   ├── finance-types.ts                   # Finance/cost/goal interfaces
│   │   ├── process-intel.ts                   # Process intelligence API functions
│   │   ├── process-intel-types.ts             # Process intel interfaces
│   │   └── index.ts                           # (update: add new exports)
│   │
│   └── ui/src/components/
│       ├── market/
│       │   ├── insight-card.tsx                # Single insight display
│       │   ├── alert-item.tsx                  # Single alert with acknowledge
│       │   ├── source-table.tsx                # RSS sources table
│       │   ├── competitor-table.tsx            # Competitors landscape table
│       │   ├── swot-card.tsx                   # 4-quadrant SWOT display
│       │   └── signal-timeline.tsx             # Chronological signals list
│       │
│       ├── finance/
│       │   ├── budget-bar.tsx                  # Single budget category bar
│       │   ├── cost-trend-chart.tsx            # API cost line chart (recharts)
│       │   ├── metric-card.tsx                 # Single metric display
│       │   ├── goal-card.tsx                   # Goal summary card
│       │   ├── goal-progress-chart.tsx         # Goal progress over time (recharts)
│       │   └── budget-scope-table.tsx          # Cost budget scopes table
│       │
│       └── process/
│           ├── business-line-card.tsx           # Business line summary card
│           ├── process-card.tsx                 # Process with automation bar
│           ├── app-table.tsx                    # App inventory table
│           ├── app-ranking-table.tsx            # Replacement ranking
│           ├── flow-table.tsx                   # Data flows table
│           ├── tech-radar-chart.tsx             # Quadrant radar visualization
│           ├── tech-solution-card.tsx           # Single tech solution
│           ├── roadmap-timeline.tsx             # Quarterly timeline (reusable)
│           └── workforce-table.tsx              # Employee automation candidates
│
├── apps/web/
│   ├── lib/
│   │   ├── hooks/
│   │   │   ├── use-market.ts                  # Market + competitor React Query hooks
│   │   │   ├── use-finance.ts                 # Finance + costs + goals hooks
│   │   │   └── use-process-intel.ts           # Process intelligence hooks
│   │   │
│   │   └── stores/
│   │       ├── market-store.ts                # Market UI state
│   │       ├── finance-store.ts               # Finance UI state
│   │       └── process-store.ts               # Process intel UI state
│   │
│   └── app/(app)/
│       ├── market/
│       │   ├── page.tsx                        # Market dashboard + insights
│       │   ├── alerts/page.tsx                 # Alerts list
│       │   ├── sources/page.tsx                # Sources management
│       │   └── competitors/
│       │       ├── page.tsx                     # Landscape table
│       │       ├── [id]/page.tsx                # SWOT + signals detail
│       │       └── signals/page.tsx             # All signals timeline
│       │
│       ├── finance/
│       │   ├── page.tsx                        # Finance dashboard
│       │   ├── costs/page.tsx                  # Cost budget detail
│       │   └── goals/
│       │       ├── page.tsx                     # Goals list
│       │       └── [id]/page.tsx                # Goal detail
│       │
│       └── process/
│           ├── page.tsx                        # PI dashboard overview
│           ├── apps/
│           │   ├── page.tsx                     # App inventory + ranking
│           │   └── [id]/page.tsx                # App deep analysis
│           ├── flows/page.tsx                  # Data flows
│           ├── tech-radar/page.tsx             # Tech radar + roadmap
│           └── workforce/page.tsx              # CEO-only workforce analysis
```

**Total new files: 48** (6 api-client, 6 types, 3 hooks, 3 stores, 15 components, 15 pages)

---

## 3. API Integration Map

### Market Module
| Component | Endpoint | Method | Hook |
|-----------|----------|--------|------|
| `MarketPage` | `/market/dashboard` | GET | `useMarketDashboard(days)` |
| `MarketPage` scan button | `/market/scan` | POST | `useScanMarket()` |
| `MarketInsightsFeed` | `/market/insights` | GET | `useMarketInsights(type, minRelevance, limit)` |
| `AlertsList` | `/market/alerts` | GET | `useMarketAlerts(acknowledged)` |
| `AlertItem` acknowledge | `/market/alerts/{id}/acknowledge` | POST | `useAcknowledgeAlert()` — **NEEDS BACKEND** |
| `SourcesTable` | `/market/sources` (GET via dashboard) | GET | via `useMarketDashboard` |
| `AddSourceForm` | `/market/sources` | POST | `useAddMarketSource()` |
| `CompetitorTable` | `/competitors` | GET | `useCompetitors()` |
| `AddCompetitorDialog` | `/competitors` | POST | `useAddCompetitor()` |
| `CompetitorToolbar` scan | `/competitors/scan` | POST | `useScanCompetitors()` |
| `CompetitorDetailPage` | `/competitors/{id}/analysis` | GET | `useCompetitorAnalysis(id)` |
| `SignalTimeline` | `/competitors/signals` | GET | `useCompetitorSignals(competitorId, type, days)` |

### Finance Module
| Component | Endpoint | Method | Hook |
|-----------|----------|--------|------|
| `FinancePage` | `/finance` | GET | `useFinanceDashboard(company)` |
| `FinancePage` add metric | `/finance/metric` | POST | `useAddFinanceMetric()` |
| `FinancePage` add budget | `/finance/budget` | POST | `useAddBudget()` |
| `FinancePage` estimate | `/finance/estimate-cost` | POST | `useEstimateCost()` |
| `CostsPage` | `/costs/budget` | GET | `useCostBudget()` |
| `GoalsPage` | `/goals` | GET | `useGoals()` |
| `GoalDetailPage` | `/goals/{id}` | GET | `useGoalDetail(id)` |
| `CreateGoalDialog` | `/goals` | POST | `useCreateGoal()` |
| `UpdateProgressForm` | `/goals/{id}/progress` | POST | `useUpdateGoalProgress()` |

### Process Intelligence Module
| Component | Endpoint | Method | Hook |
|-----------|----------|--------|------|
| `ProcessPage` | `/process-intel/dashboard` | GET | `useProcessDashboard()` |
| `BusinessLinesGrid` | `/process-intel/business-lines` | GET | `useBusinessLines()` |
| `ProcessPage` discover | `/process-intel/discover` | POST | `useDiscoverBusinessLines()` |
| `ProcessDiscoverySection` | `/process-intel/processes` | GET | `useProcesses(type)` |
| `ProcessPage` mine | `/process-intel/mine` | POST | `useMineProcesses()` |
| `AppInventoryTable` | `/process-intel/apps` | GET | `useApps()` |
| `AppToolbar` scan | `/process-intel/scan-apps` | POST | `useScanApps()` |
| `AppToolbar` deep scan | `/process-intel/scan-apps-deep` | POST | `useScanAppsDeep()` |
| `AppsPage` analysis | `/process-intel/app-analysis` | GET | `useAppAnalysis()` |
| `AppDetailPage` | `/process-intel/app-analysis/{id}` | GET | `useAppDetail(id)` |
| `AppsPage` costs | `/process-intel/app-costs` | POST | `useAppCosts()` |
| `AppsPage` ranking | `/process-intel/app-replacement-ranking` | GET | `useAppRanking()` |
| `FlowTable` | `/process-intel/flows` | GET | `useFlows()` |
| `FlowToolbar` map | `/process-intel/map-flows` | POST | `useMapFlows()` |
| `OptimizationsSummary` | `/process-intel/optimizations` | GET | `useOptimizations()` |
| `ProcessPage` plan | `/process-intel/plan` | POST | `useGenerateOptimizations()` |
| `WorkforcePage` analyze | `/process-intel/analyze-employee/{slug}` | POST | `useAnalyzeEmployee()` |
| `WorkforcePage` analyze all | `/process-intel/analyze-all-employees` | POST | `useAnalyzeAllEmployees()` |
| `WorkforcePage` profile | `/process-intel/work-profile/{slug}` | GET | `useWorkProfile(slug)` |
| `AutomationOverviewKpis` | `/process-intel/automation-overview` | GET | `useAutomationOverview()` |
| `AutomationRoadmapTimeline` | `/process-intel/automation-roadmap` | GET | `useAutomationRoadmap()` |
| `TechRadarPage` discover | `/process-intel/discover-tech` | POST | `useDiscoverTech()` |
| `TechRadarChart` | `/process-intel/tech-radar` | GET | `useTechRadar()` |
| `TechSolutionCard` detail | `/process-intel/tech-radar/{id}` | GET | `useTechSolution(id)` |
| `TechRoadmapTimeline` | `/process-intel/tech-roadmap` | GET | `useTechRoadmap()` |
| `TechSolutionCard` status | `/process-intel/tech-solution/{id}/status` | POST | `useUpdateTechStatus()` |
| `StrategicAlignmentView` | `/process-intel/tech-strategic-alignment` | GET | `useTechAlignment()` |

---

## 4. RBAC Per View

| Page | Route | Roles | Permission | Fallback |
|------|-------|-------|------------|----------|
| Market Dashboard | `/market` | director, board, ceo | `data:read:department` | `<AccessDenied />` |
| Market Alerts | `/market/alerts` | director, board, ceo | `data:read:department` | `<AccessDenied />` |
| Market Sources | `/market/sources` | director, board, ceo | `data:read:department` | `<AccessDenied />` |
| Competitors | `/market/competitors` | board, ceo | `data:read:all` | `<AccessDenied />` |
| Competitor Detail | `/market/competitors/[id]` | board, ceo | `data:read:all` | `<AccessDenied />` |
| Competitor Signals | `/market/competitors/signals` | board, ceo | `data:read:all` | `<AccessDenied />` |
| Finance Dashboard | `/finance` | board, ceo | `financials:read` | `<AccessDenied />` |
| Cost Budget | `/finance/costs` | board, ceo | `financials:read` | `<AccessDenied />` |
| Goals | `/finance/goals` | board, ceo | `financials:read` | `<AccessDenied />` |
| Goal Detail | `/finance/goals/[id]` | board, ceo | `financials:read` | `<AccessDenied />` |
| Process Dashboard | `/process` | director, board, ceo | `data:read:department` | `<AccessDenied />` |
| Apps | `/process/apps` | director, board, ceo | `data:read:department` | `<AccessDenied />` |
| App Detail | `/process/apps/[id]` | director, board, ceo | `data:read:department` | `<AccessDenied />` |
| Data Flows | `/process/flows` | director, board, ceo | `data:read:department` | `<AccessDenied />` |
| Tech Radar | `/process/tech-radar` | board, ceo | `config:write:system` | `<AccessDenied />` |
| Workforce | `/process/workforce` | ceo | `evaluations:read:all` | `<AccessDenied />` |

---

## 5. State Management (Zustand Store Shapes)

### market-store.ts
```typescript
interface MarketStore {
  // Filters
  insightTypeFilter: string | null;        // 'price_change' | 'regulation' | ...
  minRelevance: number;                     // 0-1
  insightLimit: number;                     // default 20
  alertsShowAcknowledged: boolean;          // default false
  signalDays: number;                       // default 30
  signalTypeFilter: string | null;

  // UI
  activeTab: 'dashboard' | 'alerts' | 'sources' | 'competitors';
  sourcesExpanded: boolean;

  // Auto-refresh
  refreshInterval: number;                  // ms, 0 = disabled

  // Actions
  setInsightTypeFilter: (type: string | null) => void;
  setMinRelevance: (val: number) => void;
  setAlertsShowAcknowledged: (val: boolean) => void;
  setSignalDays: (days: number) => void;
  setSignalTypeFilter: (type: string | null) => void;
  setActiveTab: (tab: string) => void;
  toggleSourcesExpanded: () => void;
  setRefreshInterval: (ms: number) => void;
}
```

### finance-store.ts
```typescript
interface FinanceStore {
  // Filters
  selectedCompany: string | null;          // null = all companies
  goalsAreaFilter: string | null;          // 'business' | 'trading' | ...
  goalsStatusFilter: string | null;        // 'on_track' | 'at_risk' | ...

  // UI
  activeTab: 'overview' | 'costs' | 'goals';
  expandedCompanies: string[];             // company names that are expanded

  // Auto-refresh
  refreshInterval: number;

  // Actions
  setSelectedCompany: (company: string | null) => void;
  setGoalsAreaFilter: (area: string | null) => void;
  setGoalsStatusFilter: (status: string | null) => void;
  setActiveTab: (tab: string) => void;
  toggleCompanyExpanded: (company: string) => void;
  setRefreshInterval: (ms: number) => void;
}
```

### process-store.ts
```typescript
interface ProcessStore {
  // Filters
  processTypeFilter: string | null;        // 'decision' | 'approval' | ...
  appStatusFilter: string | null;
  techStatusFilter: string | null;
  techTypeFilter: string | null;           // 'build' | 'buy' | 'extend'

  // UI
  activeSection: 'overview' | 'apps' | 'flows' | 'tech' | 'workforce';
  appViewMode: 'inventory' | 'ranking' | 'costs';

  // Workforce (CEO)
  selectedEmployee: string | null;         // person slug

  // Auto-refresh
  refreshInterval: number;

  // Actions
  setProcessTypeFilter: (type: string | null) => void;
  setAppStatusFilter: (status: string | null) => void;
  setTechStatusFilter: (status: string | null) => void;
  setTechTypeFilter: (type: string | null) => void;
  setActiveSection: (section: string) => void;
  setAppViewMode: (mode: string) => void;
  setSelectedEmployee: (slug: string | null) => void;
  setRefreshInterval: (ms: number) => void;
}
```

---

## 6. UX Flows

### Flow 1: Market Scan & Review
1. User opens `/market` → sees dashboard KPIs + recent insights
2. Clicks "Skanuj rynek" button → loading spinner on button
3. Scan completes → toast: "Znaleziono X nowych insights, Y alertów"
4. Insights feed auto-refreshes → new items appear at top with "NEW" badge
5. User clicks insight → expands to show full description + impact
6. If alerts created → alert banner appears at top

### Flow 2: Competitor Deep Dive
1. User opens `/market/competitors` → sees landscape table
2. Clicks "Skanuj konkurencję" → scan runs, table refreshes
3. Clicks competitor row → navigates to `/market/competitors/[id]`
4. Sees SWOT analysis (4 quadrants) + signals timeline below
5. Can filter signals by type and severity

### Flow 3: Finance Budget Monitoring
1. User opens `/finance` → sees multi-company dashboard
2. Company tabs at top (or all companies view)
3. Budget utilization bars show planned vs actual per category
4. Red bars = over budget, amber = 80%+, green = under
5. API costs section: line chart with monthly trend + forecast
6. Scrolls to alerts section for financial warnings

### Flow 4: Goal Tracking
1. User opens `/finance/goals` → sees goals grouped by area
2. KPI row: total goals, on_track, at_risk, behind, achieved
3. Clicks goal card → navigates to `/finance/goals/[id]`
4. Detail view: progress chart over time, sub-goals tree, dependencies
5. Updates progress: enters value + optional note → chart updates
6. Status auto-changes based on thresholds

### Flow 5: Process Intelligence Discovery
1. User opens `/process` → sees PI dashboard with business lines
2. Clicks "Odkryj procesy" → mining runs, new processes appear
3. Each process card shows automation potential bar (0-100%)
4. Navigates to `/process/apps` → sees app inventory
5. Switches between inventory / ranking / costs tabs
6. Clicks "Głębokie skanowanie" → discovers more apps with details

### Flow 6: Tech Radar Review (Board+)
1. User opens `/process/tech-radar` → sees quadrant chart
2. Solutions plotted by status: adopt (deployed), trial (approved), assess (proposed), hold (rejected)
3. Solution cards below with ROI, dev hours, savings
4. Clicks solution → expands detail with strategic alignment
5. Can approve/reject solutions via status buttons
6. Roadmap timeline shows quarterly implementation plan

### Flow 7: Workforce Analysis (CEO only)
1. CEO opens `/process/workforce` → sees automation overview
2. KPIs: total employees analyzed, avg automatable %, total savings
3. Top candidates table: sorted by automatable_pct DESC
4. Clicks employee row → expands to show work activities + automation roadmap
5. Can trigger "Analizuj wszystkich" → full re-analysis
6. Automation roadmap: quarterly initiatives timeline

---

## 7. Chart & Visualization Specifications

### Cost Trend Chart (recharts)
- **Type:** LineChart
- **Data:** monthly API costs (last 12 months)
- **Lines:** total_usd (primary), api_calls (secondary axis)
- **Colors:** `var(--accent)` for cost, `var(--text-muted)` for calls
- **Extras:** Current month forecast as dashed line

### Goal Progress Chart (recharts)
- **Type:** AreaChart
- **Data:** progress entries over time
- **Area:** current_value vs target_value line
- **Colors:** `var(--accent)` fill, target as `var(--warning)` dashed

### Tech Radar Chart (custom SVG)
- **Type:** Custom quadrant chart (4 sections)
- **Quadrants:** Adopt (top-right), Trial (top-left), Assess (bottom-left), Hold (bottom-right)
- **Rings:** Build (inner), Buy (middle), Extend (outer)
- **Interaction:** Hover for tooltip, click for detail
- **Mapping:** status → quadrant (deployed=adopt, approved=trial, proposed=assess, rejected=hold)

### Budget Bars (custom)
- **Type:** Horizontal progress bars
- **Colors:** Green (<60%), Amber (60-80%), Red (>80%)
- **Labels:** Category name, planned amount, actual amount, percentage

---

## 8. Backend Gaps — Frontend Workarounds

| Gap | Frontend Approach |
|-----|-------------------|
| No alert acknowledge endpoint | Show alerts read-only, add TODO comment for backend |
| No delete sources/competitors | Show data without delete buttons, add later |
| No edit competitors | Show data read-only, add later |
| No delete goals | Show goals without delete, can cancel via status |
| Query param POSTs (competitors, sources) | Build URL with query params in API client |
| No pagination | Client-side pagination with `limit` param where available |
| No scan progress events | Use mutation loading state, show spinner, handle timeout (30s) |
| Tech radar no quadrant field | Map `status` → quadrant in frontend (deployed=adopt, approved=trial, proposed=assess, rejected=hold) |

---

## 9. Key Architectural Decisions

1. **3 separate stores** — one per module to keep state isolated and minimize re-renders
2. **Recharts for standard charts** — already installed, used for cost trends and goal progress
3. **Custom SVG for tech radar** — recharts doesn't support quadrant charts; D3 overkill for static quadrants
4. **Client-side pagination** — no backend support; use table component's built-in pagination
5. **Tab-based sub-navigation** within pages rather than deep nesting (e.g., app inventory/ranking/costs as tabs)
6. **Reusable RoadmapTimeline** — shared between tech roadmap and automation roadmap
7. **Polish labels** — all user-facing text in Polish (Skanuj, Odkryj, Analiza, etc.)
8. **Scan mutations** — show loading spinner on button, toast on completion, auto-invalidate related queries
