# Autofixer Dashboard — Orchestrator Prompt

## Goal
Add an "Autofixers" tab to the Gilbertus App showing real-time status of both repair systems:
1. **Code Autofixer** (backend: tier 1/2/3 — code_review_findings table)
2. **Webapp AutoFix** (frontend: HTTP monitoring, TS errors — app_errors table + logs)

## Architecture Reference

### Frontend Stack
- **Framework:** Next.js 16 App Router, React 19, TypeScript 5.7
- **Styling:** Tailwind CSS 4 + CSS variables (dark mode: `var(--bg)`, `var(--surface)`, `var(--text)`, `var(--accent)`, `var(--success)`, `var(--warning)`, `var(--danger)`)
- **Data fetching:** TanStack React Query (`useQuery`) + custom hooks
- **State:** Zustand stores with `persist` middleware
- **API client:** `customFetch<T>()` from `packages/api-client/src/base.ts`
- **Icons:** Lucide React
- **RBAC:** `@gilbertus/rbac` — navigation modules
- **UI components:** `packages/ui/src/components/`
- **Pages:** `frontend/apps/web/app/(app)/` — all routes use `(app)` layout with sidebar

### Existing Patterns to Follow
- **Page example:** `frontend/apps/web/app/(app)/admin/code-review/page.tsx` — uses `<CodeReviewQueue />` from `@gilbertus/ui`
- **Hook example:** `frontend/apps/web/lib/hooks/use-dashboard.ts` — wraps `useQuery` with store config
- **API client example:** `packages/api-client/src/dashboard.ts` — typed functions calling `customFetch`
- **Component example:** `packages/ui/src/components/admin/code-review-queue.tsx`
- **Navigation:** `packages/rbac/src/navigation.ts` — defines modules with `{id, path, icon, label}`

### Existing Backend Endpoints
- `GET /code-fixes/manual-queue` → manual review findings (app/api/main.py:490)
- `GET /errors/unresolved` → frontend errors (app/api/errors.py:51)
- `GET /status` → system status (app/api/main.py:541)

### Database Tables
**code_review_findings** (backend autofixer):
- id, file_path, severity, category, title, description
- line_start, line_end, suggested_fix, model_used
- resolved (bool), resolved_at, created_at
- fix_attempt_count, fix_attempted_at, manual_review
- tier (1/2/3), cluster_id
- tier3_attempted, tier3_attempt_count, tier3_last_error

**app_errors** (webapp autofix):
- id, user_id, route, error_type, error_message, error_stack
- component, module, browser, resolved, fix_commit, created_at

## Implementation Plan

### STEP 1: Backend API endpoint
**File:** `app/api/main.py`

Add endpoint `GET /autofixers/dashboard` returning:
```json
{
  "code_fixer": {
    "total": 1406,
    "resolved": 1189,
    "open": 217,
    "stuck": 89,
    "manual_review": 57,
    "by_severity": {"critical": 5, "high": 30, "medium": 120, "low": 62},
    "by_category": {"correctness": 48, "quality": 59, ...},
    "by_tier": {"tier1": 30, "tier2": 1177, "tier3": 1},
    "success_rate": 85.1,
    "last_fix": "2026-03-31T09:32:22"
  },
  "webapp_fixer": {
    "total_errors": 45,
    "resolved": 38,
    "open": 7,
    "server_status": "up",
    "consecutive_failures": 0,
    "last_check": "2026-03-31T09:14:02",
    "routes_monitored": 15
  },
  "daily_history": [
    {"date": "2026-03-31", "found": 20, "fixed": 15, "webapp_errors": 3, "webapp_fixed": 2},
    {"date": "2026-03-30", "found": 45, "fixed": 38, "webapp_errors": 5, "webapp_fixed": 4},
    ...
  ],
  "manual_queue": [
    {"id": 123, "file_path": "app/api/main.py", "severity": "high", "category": "correctness",
     "title": "...", "description": "...", "attempts": 6, "tier3_attempted": true,
     "created_at": "...", "suggested_fix": "..."},
    ...
  ]
}
```

SQL queries needed:
```sql
-- Overview stats
SELECT
  COUNT(*) as total,
  SUM(CASE WHEN resolved THEN 1 ELSE 0 END) as resolved,
  SUM(CASE WHEN NOT resolved THEN 1 ELSE 0 END) as open,
  SUM(CASE WHEN NOT resolved AND fix_attempt_count >= 2 THEN 1 ELSE 0 END) as stuck,
  SUM(CASE WHEN manual_review THEN 1 ELSE 0 END) as manual_review
FROM code_review_findings;

-- By severity (open only)
SELECT severity, COUNT(*) FROM code_review_findings WHERE NOT resolved GROUP BY severity;

-- By category (open only)
SELECT category, COUNT(*) FROM code_review_findings WHERE NOT resolved GROUP BY category;

-- Daily history (last 14 days)
SELECT DATE(created_at) as day,
  COUNT(*) as found,
  SUM(CASE WHEN resolved THEN 1 ELSE 0 END) as fixed
FROM code_review_findings
WHERE created_at > NOW() - INTERVAL '14 days'
GROUP BY DATE(created_at) ORDER BY day;

-- Manual queue
SELECT id, file_path, severity, category, title, description,
  fix_attempt_count, tier3_attempted, tier3_last_error, created_at, suggested_fix
FROM code_review_findings
WHERE NOT resolved AND (manual_review OR fix_attempt_count >= 3)
ORDER BY
  CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
  created_at;

-- Webapp errors (from app_errors table)
SELECT COUNT(*) as total,
  SUM(CASE WHEN resolved THEN 1 ELSE 0 END) as resolved,
  SUM(CASE WHEN NOT resolved THEN 1 ELSE 0 END) as open
FROM app_errors;
```

For webapp_fixer status, read state from `logs/webapp_autofix_state.json`.

### STEP 2: API client function
**File:** `frontend/packages/api-client/src/admin.ts`

Add:
```typescript
export interface AutofixerDashboard {
  code_fixer: {
    total: number;
    resolved: number;
    open: number;
    stuck: number;
    manual_review: number;
    by_severity: Record<string, number>;
    by_category: Record<string, number>;
    by_tier: Record<string, number>;
    success_rate: number;
    last_fix: string | null;
  };
  webapp_fixer: {
    total_errors: number;
    resolved: number;
    open: number;
    server_status: string;
    consecutive_failures: number;
    last_check: string | null;
    routes_monitored: number;
  };
  daily_history: Array<{
    date: string;
    found: number;
    fixed: number;
    webapp_errors: number;
    webapp_fixed: number;
  }>;
  manual_queue: Array<{
    id: number;
    file_path: string;
    severity: string;
    category: string;
    title: string;
    description: string;
    attempts: number;
    tier3_attempted: boolean;
    tier3_last_error: string | null;
    created_at: string;
    suggested_fix: string | null;
  }>;
}

export async function getAutofixerDashboard(): Promise<AutofixerDashboard> {
  return customFetch<AutofixerDashboard>({
    url: '/autofixers/dashboard',
    method: 'GET',
  });
}
```

Also export the type and function from `packages/api-client/src/index.ts`.

### STEP 3: React hook
**File:** `frontend/apps/web/lib/hooks/use-admin.ts`

Add:
```typescript
export function useAutofixerDashboard() {
  return useQuery<AutofixerDashboard>({
    queryKey: ['autofixer-dashboard'],
    queryFn: getAutofixerDashboard,
    refetchInterval: 60_000, // refresh every minute
  });
}
```

### STEP 4: UI components
**File:** `frontend/packages/ui/src/components/admin/autofixer-dashboard.tsx`

Create a dashboard component with 3 sections:

**Section 1: Overview Cards (top)**
Two side-by-side cards:
- Code Autofixer: total/resolved/open/stuck/success_rate, circular progress
- Webapp AutoFix: server_status, total/resolved/open, routes_monitored

**Section 2: Daily Performance Chart (middle)**
Simple bar/line chart showing found vs fixed per day for the last 14 days.
Use a simple HTML/CSS bar chart (no external chart library needed).

**Section 3: Manual Review Queue (bottom)**
Table with columns: Severity | File | Category | Title | Attempts | Tier3 | Actions
- Color-coded severity badges
- Expandable rows showing description + suggested_fix
- File path as monospace text

### STEP 5: Page route
**File:** `frontend/apps/web/app/(app)/admin/autofixers/page.tsx`

```tsx
'use client';
import { AutofixerDashboard } from '@gilbertus/ui';
import { useAutofixerDashboard } from '@/lib/hooks/use-admin';

export default function AutofixersPage() {
  const { data, isLoading, error } = useAutofixerDashboard();
  return <AutofixerDashboard data={data} isLoading={isLoading} error={error} />;
}
```

### STEP 6: Navigation
**File:** `frontend/packages/rbac/src/navigation.ts`

Add autofixers module under admin section:
```typescript
{ id: 'admin-autofixers', path: '/admin/autofixers', icon: 'Wrench', label: { pl: 'Autofixery', en: 'Autofixers' } }
```

Also add `Wrench` to the ICON_MAP in sidebar.tsx.

## Rules
- All SQL MUST be parameterized (use %s with params tuple)
- Use `get_pg_connection()` from `app/db/postgres.py`
- Use `structlog` for logging (never print())
- Follow existing component patterns (CSS variables, Tailwind classes)
- Use `customFetch` from api-client base.ts
- Export new types from api-client index.ts
- Use TanStack React Query for data fetching
- Polish labels (pl) as primary language
- Dark mode compatible (use CSS variables)
- No external chart libraries — use simple HTML/CSS bars
