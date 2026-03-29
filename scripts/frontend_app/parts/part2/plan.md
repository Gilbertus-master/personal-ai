# Part 2: Dashboard & Alerts — Architecture Plan

**Module:** Dashboard — Morning Brief, KPIs, Alerts, Timeline, System Status
**Date:** 2026-03-29

---

## 1. Component Tree (Visual Hierarchy)

```
AppLayout (existing)
├── Sidebar (existing — /dashboard link already in nav)
├── Topbar (existing — Bell button placeholder at line 57-63)
│   └── NotificationBell (NEW — replaces placeholder button)
│       ├── Bell icon + badge count
│       └── NotificationDropdown (absolute positioned)
│           └── NotificationItem[] (alert type, title, severity, timestamp)
└── <main>
    └── /dashboard (page.tsx) ─────────────────────────────────
        │
        ├── RbacGate [ceo, gilbertus_admin]
        │   └── FULL DASHBOARD LAYOUT
        │       │
        │       ├── KpiGrid (top row, full width)
        │       │   └── KpiCard[] (4-6 cards in responsive grid)
        │       │       ├── label
        │       │       ├── value (number/string)
        │       │       ├── trend arrow (↑↓→)
        │       │       └── color indicator
        │       │
        │       ├── Two-column layout (desktop), single column (mobile)
        │       │   │
        │       │   ├── LEFT COLUMN (flex-1, wider)
        │       │   │   ├── MorningBrief
        │       │   │   │   ├── Header ("Poranny Brief" + date + refresh btn)
        │       │   │   │   ├── MarkdownRenderer (reuse from P1)
        │       │   │   │   └── CollapsibleSections
        │       │   │   │       ├── Events section
        │       │   │   │       ├── Alerts section
        │       │   │   │       ├── Commitments section
        │       │   │   │       └── Compliance section
        │       │   │   │
        │       │   │   └── ActivityTimeline
        │       │   │       ├── Header ("Oś czasu" + type filter dropdown)
        │       │   │       ├── TimelineEvent[] (scrollable, max-height)
        │       │   │       │   ├── event_type icon + badge
        │       │   │       │   ├── summary text
        │       │   │       │   ├── entities tags
        │       │   │       │   └── timestamp
        │       │   │       └── "Pokaż więcej" button (pagination)
        │       │   │
        │       │   └── RIGHT COLUMN (w-80 lg:w-96)
        │       │       ├── AlertsFeed
        │       │       │   ├── Header ("Alerty" + count badge)
        │       │       │   └── AlertItem[]
        │       │       │       ├── severity dot (red/amber/blue)
        │       │       │       ├── title
        │       │       │       ├── description (truncated)
        │       │       │       ├── created_at
        │       │       │       └── dismiss button (localStorage)
        │       │       │
        │       │       ├── SystemStatus
        │       │       │   ├── Header ("Status systemu")
        │       │       │   ├── ServiceIndicator[] (Postgres, Qdrant, Whisper)
        │       │       │   │   ├── traffic-light dot (green/red)
        │       │       │   │   └── service name + status
        │       │       │   └── DB stats mini grid (chunks, entities, events)
        │       │       │
        │       │       └── QuickActions
        │       │           └── ActionButton[] (4 buttons)
        │       │               ├── "Nowy czat" → /chat
        │       │               ├── "Meeting Prep" → ask action
        │       │               ├── "Scan Market" → ask action
        │       │               └── "Compliance Check" → ask action
        │
        ├── RbacGate [board]
        │   └── BOARD VIEW (brief general + KPI basic + timeline)
        │
        ├── RbacGate [director, manager]
        │   └── MANAGER VIEW (brief general + quick actions)
        │
        ├── RbacGate [operator]
        │   └── OPERATOR VIEW (SystemStatus only)
        │
        └── RbacGate [specialist]
            └── SPECIALIST VIEW (simplified — own tasks placeholder)
```

---

## 2. File Tree (Every File Path)

```
frontend/
├── packages/
│   ├── api-client/src/
│   │   ├── dashboard-types.ts        # NEW — all dashboard response interfaces
│   │   ├── dashboard.ts              # NEW — API client functions
│   │   └── index.ts                  # MODIFY — add dashboard exports
│   └── ui/src/components/
│       └── dashboard/                # NEW directory
│           ├── index.ts              # Barrel export
│           ├── kpi-card.tsx          # Single KPI metric card
│           ├── kpi-grid.tsx          # Grid of KPI cards
│           ├── morning-brief.tsx     # Morning brief with markdown
│           ├── alerts-feed.tsx       # Active alerts list
│           ├── alert-item.tsx        # Single alert entry
│           ├── activity-timeline.tsx # Event timeline list
│           ├── timeline-event.tsx    # Single timeline entry
│           ├── system-status.tsx     # Service health + DB stats
│           ├── quick-actions.tsx     # Action buttons grid
│           └── notification-bell.tsx # Bell icon + dropdown for topbar
├── apps/web/
│   ├── app/(app)/dashboard/
│   │   └── page.tsx                  # MODIFY — replace placeholder
│   └── lib/
│       ├── stores/
│       │   └── dashboard-store.ts    # NEW — dashboard preferences
│       └── hooks/
│           └── use-dashboard.ts      # NEW — TanStack Query hooks
```

**Total: 14 new files, 2 modified files**

---

## 3. API Integration Map

| Component | Endpoint | Method | TanStack Query Key | Refresh |
|-----------|----------|--------|-------------------|---------|
| MorningBrief | `/brief/today` | GET | `['brief', date]` | 5 min |
| AlertsFeed | `/alerts` | GET | `['alerts', filters]` | 60s |
| KpiGrid (db stats) | `/status` | GET | `['status']` | 5 min |
| KpiGrid (commitments) | `/commitments?status=open` | GET | `['commitments', 'open']` | 5 min |
| KpiGrid (costs) | `/costs/budget` | GET | `['budget']` | 5 min |
| ActivityTimeline | `/timeline` | POST | `['timeline', filters]` | 5 min |
| SystemStatus | `/status` | GET | `['status']` | 60s (shared with KPI) |
| NotificationBell | `/alerts?active_only=true` | GET | `['alerts', 'bell']` | 60s |

---

## 4. RBAC Per View/Component

```typescript
// Role-based dashboard views
const DASHBOARD_VIEWS: Record<string, RoleName[]> = {
  full:      ['gilbertus_admin', 'ceo'],
  board:     ['board'],
  manager:   ['director', 'manager'],
  operator:  ['operator'],
  specialist: ['specialist'],
};

// Per-component visibility
const COMPONENT_ROLES: Record<string, RoleName[]> = {
  KpiGrid:          ['gilbertus_admin', 'ceo'],
  KpiGridBasic:     ['gilbertus_admin', 'ceo', 'board'],
  MorningBrief:     ['gilbertus_admin', 'ceo', 'board'],
  MorningBriefGen:  ['gilbertus_admin', 'ceo', 'board', 'director', 'manager'],
  AlertsFeed:       ['gilbertus_admin', 'ceo', 'board'],
  ActivityTimeline: ['gilbertus_admin', 'ceo', 'board'],
  SystemStatus:     ['gilbertus_admin', 'ceo', 'operator'],
  QuickActions:     ['gilbertus_admin', 'ceo', 'board', 'director', 'manager'],
  NotificationBell: ['gilbertus_admin', 'ceo', 'board', 'director', 'manager', 'specialist', 'operator'],
};
```

Implementation: Use `useRole()` in `page.tsx` to select dashboard variant. Each variant renders only its permitted components. Components themselves don't need additional RBAC checks.

---

## 5. State Management

### Zustand Store: `dashboard-store.ts`

```typescript
interface DashboardPreferences {
  collapsedSections: string[];      // ['brief', 'timeline', ...]
  dismissedAlertIds: number[];      // localStorage-based dismiss
  autoRefresh: boolean;             // default: true
  refreshInterval: number;          // default: 300_000 (5 min)
  timelineFilter: string | null;    // event_type filter
}

interface DashboardStore extends DashboardPreferences {
  toggleSection: (section: string) => void;
  dismissAlert: (alertId: number) => void;
  undismissAlert: (alertId: number) => void;
  setAutoRefresh: (enabled: boolean) => void;
  setRefreshInterval: (ms: number) => void;
  setTimelineFilter: (filter: string | null) => void;
}
```

Persisted with Zustand `persist` middleware, key: `'gilbertus-dashboard'`.

### TanStack Query Hooks: `use-dashboard.ts`

```typescript
// Each hook wraps useQuery with appropriate settings
export function useBrief(options?: { force?: boolean; date?: string })
export function useAlerts(options?: { activeOnly?: boolean; severity?: string })
export function useStatus()
export function useCommitmentsCount()
export function useBudget()
export function useTimeline(options?: { eventType?: string; limit?: number })
export function useAlertsBell()  // lightweight polling for notification count
```

All hooks use:
- `staleTime`: inherited from QueryClient (60s)
- `refetchInterval`: from dashboard store preferences (300_000 default)
- Error handling: return `{ error }` for component-level error display
- Loading: return `{ isLoading }` for skeleton states

---

## 6. UX Flows

### Morning Brief
1. Page loads → `useBrief()` fires → skeleton shown
2. Data arrives → MarkdownRenderer renders brief content
3. Sections auto-detected from markdown headings → collapsible
4. User clicks "Odśwież" → `useBrief({ force: true })` refetches
5. Brief cached for 5 min unless force-refreshed

### Alerts Feed
1. `useAlerts()` loads active alerts → rendered as severity-colored list
2. User clicks dismiss → `dismissAlert(id)` in Zustand → alert hidden
3. Alert still exists in backend, just hidden client-side
4. New alerts appear on next poll (every 60s)

### KPI Grid
1. Three queries fire in parallel: `/status`, `/commitments`, `/costs/budget`
2. KpiCard components render with values once any query resolves
3. Individual cards show skeleton while their specific data loads
4. Trend arrows derived from comparison logic (up/down/flat)

### Notification Bell (Topbar)
1. `useAlertsBell()` polls `/alerts?active_only=true&limit=5` every 60s
2. Badge shows count of active alerts
3. Click opens dropdown with latest 5 alerts
4. Click on alert → scrolls to AlertsFeed or navigates to relevant page
5. Badge count decrements when alert is dismissed from dashboard

### Activity Timeline
1. `useTimeline()` loads last 20 events
2. Type filter dropdown filters by event_type
3. "Pokaż więcej" loads next 20 (offset pagination)
4. Each event shows type icon, summary, entity tags, timestamp

---

## 7. Component Specifications

### KpiCard
- Props: `{ label, value, trend?, trendValue?, color?, icon? }`
- Sizes: compact card, number prominent (text-2xl font-bold)
- Trend arrow: green ↑ for positive, red ↓ for negative, gray → for flat
- Colors: `default` (accent), `success` (green), `warning` (amber), `danger` (red)
- Icon: Lucide icon component passed as prop

### KPI Cards Data Sources
1. **Dokumenty** — `status.db.documents` (FileText icon)
2. **Eventy** — `status.db.events` (Calendar icon)
3. **Encje** — `status.db.entities` (Users icon)
4. **Zobowiązania** — `commitments.length` where status=open (Target icon)
5. **Koszty dziś** — `budget.daily_total_usd` formatted as "$X.XX" (DollarSign icon)
6. **Alerty** — `status.db.alerts` active count (AlertTriangle icon)

### NotificationBell
- Reuses existing Bell button position in Topbar (line 57-63)
- Badge: absolute positioned red dot with count
- Dropdown: max-h-80, scrollable, positioned below bell
- Close: click outside or Escape key
- Items: alert title + severity color + relative timestamp

---

## 8. Error & Loading States

| State | Component | Behavior |
|-------|-----------|----------|
| Loading | KpiCard | SkeletonCard with matching height |
| Loading | MorningBrief | Skeleton lines (3-4 animated bars) |
| Loading | AlertsFeed | SkeletonCard x3 |
| Loading | Timeline | SkeletonCard x5 |
| Error | Any widget | Red border, error message, retry button |
| Empty | AlertsFeed | "Brak aktywnych alertów" with CheckCircle icon |
| Empty | Timeline | "Brak wydarzeń w wybranym okresie" |
| Empty | Brief | "Brief nie został jeszcze wygenerowany" |

---

## 9. Responsive Breakpoints

| Breakpoint | Layout |
|-----------|--------|
| `< sm` (< 640px) | Single column, all widgets stacked |
| `sm-lg` (640-1024px) | KPIs: 2 cols. Content: single column |
| `>= lg` (1024px+) | KPIs: 3 cols. Content: 2 columns (brief+timeline left, alerts+status+actions right) |
| `>= xl` (1280px+) | KPIs: 4-6 cols. Same 2-column content layout |

---

## 10. Backend Gap Workarounds (MVP)

| Gap | MVP Workaround |
|-----|----------------|
| No alert dismiss endpoint | Store dismissed IDs in Zustand (localStorage persist) |
| No notification read state | Same — localStorage via dashboard store |
| No SSE/WebSocket | Poll `/alerts` every 60s for bell, 5 min for feed |
| No KPI trend data | Show current values only, no trend arrows in MVP |
| No commitments total count | Use `.length` of returned array |
