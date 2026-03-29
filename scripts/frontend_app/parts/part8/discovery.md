# Part 8: Settings, Admin & Omnius Bridge — Discovery Report

## 1. API Endpoint Inventory

### 1.1 Cron Management (Gilbertus)

| Method | Path | Params | Response Shape |
|--------|------|--------|---------------|
| GET | `/crons` | `?user=&category=` | `{ jobs: [{ job_name, schedule, command, description, category, log_file, enabled, username }] }` |
| GET | `/crons/summary` | — | `{ total, categories: [{ category, jobs, active_users }], by_user: [{ username, enabled, disabled }] }` |
| POST | `/crons/{job_name}/enable` | `?user=sebastian` | `{ job_name, username, enabled: true }` |
| POST | `/crons/{job_name}/disable` | `?user=sebastian` | `{ job_name, username, enabled: false }` |
| GET | `/crons/generate/{user}` | — | Plain text (crontab file) |

### 1.2 System Status (Gilbertus)

| Method | Path | Params | Response Shape |
|--------|------|--------|---------------|
| GET | `/status` | — | `{ db: { total_chunks, total_events, total_sources, data_volume_gb, tables }, embedding: { indexed_chunks, status, qdrant_status }, sources: { email, calendar, ... }, last_backup, services: { postgres, qdrant, whisper }, crons: { total, enabled, failed, upcoming } }` |
| GET | `/health` | — | `{ status }` |

**Auth:** X-API-Key header required for non-localhost requests (rate: 10/min).

### 1.3 Costs / Budget (Gilbertus)

| Method | Path | Params | Response Shape |
|--------|------|--------|---------------|
| GET | `/costs/budget` | — | `{ budgets: [{ scope, limit_usd, spent_usd, pct, hard_limit, status }], daily_total, module_costs: { module: cost }, alerts: [{ scope, alert_type, message, created_at }] }` |

**DB tables:** `api_costs` (module, model, input_tokens, output_tokens, cost_usd, created_at), `cost_budgets` (scope, limit_usd, alert_threshold_pct, hard_limit).

### 1.4 Code Review / Fixes (Gilbertus)

| Method | Path | Params | Response Shape |
|--------|------|--------|---------------|
| GET | `/code-fixes/manual-queue` | — | `[{ id, file, severity, category, title, description, attempts, last_attempt }]` |

**DB table:** `code_review_findings` (id, file_path, severity, category, title, description, fix_attempt_count, fix_attempted_at, manual_review, resolved).

### 1.5 Omnius Admin (per-tenant API at `/api/v1/`)

#### User Management
| Method | Path | Auth | Response Shape |
|--------|------|------|---------------|
| GET | `/api/v1/admin/users` | `users:manage:all` | `[{ id, email, name, role, level, department, active, created }]` |
| POST | `/api/v1/admin/users` | `users:manage:all` | `{ status: "created", user_id, email, role }` |

#### API Key Management
| Method | Path | Auth | Response Shape |
|--------|------|------|---------------|
| GET | `/api/v1/admin/api-keys` | `users:manage:all` | `[{ id, name, role, user_email, is_active, created_at, last_used_at }]` |
| POST | `/api/v1/admin/api-keys` | `users:manage:all` | `{ status: "created", key_id, api_key: "omnius_...", warning }` |

#### Config Management
| Method | Path | Auth | Response Shape |
|--------|------|------|---------------|
| GET | `/api/v1/admin/config` | `config:write:system` | `[{ key, value (JSONB), pushed_by, updated_at }]` |
| POST | `/api/v1/admin/config` | `config:write:system` + governance | `{ status: "ok", key }` |

#### Operator Tasks
| Method | Path | Auth | Response Shape |
|--------|------|------|---------------|
| GET | `/api/v1/admin/operator-tasks` | `dev:execute` | `[{ id, title, description, source, status, result, created, completed, assigned_to }]` |
| POST | `/api/v1/admin/operator-tasks` | `dev:execute` | `{ status: "created", task_id }` |
| PATCH | `/api/v1/admin/operator-tasks/{task_id}` | `dev:execute` | `{ status: "ok", task_id, new_status }` |

#### Audit Log
| Method | Path | Auth | Response Shape |
|--------|------|------|---------------|
| GET | `/api/v1/admin/audit` | `config:write:system` | `[{ id, user, action, resource, result, ip, at }]` |

#### Sync Trigger
| Method | Path | Auth | Response Shape |
|--------|------|------|---------------|
| POST | `/api/v1/admin/sync` | `sync:manage` | `{ status: "queued", source }` |

#### Omnius Status
| Method | Path | Auth | Response Shape |
|--------|------|------|---------------|
| GET | `/api/v1/status` | none | `{ tenant, company, users, documents, chunks, pending_tasks }` |
| GET | `/health` | none | `{ status, tenant, company, checks: { db } }` |

---

## 2. RBAC Rules

### Role Hierarchy (Omnius)
| Role | Level | Scope |
|------|-------|-------|
| `gilbertus_admin` | 99 | Full bypass — ALL permissions, ALL classifications |
| `operator` | 70 | Infrastructure only, no data access |
| `ceo` | 60 | All data classifications except: cannot modify RBAC/governance config |
| `board` | 50 | public + internal + confidential + personal |
| `director` | 40 | public + internal + personal |
| `manager` | 30 | public + internal + personal |
| `specialist` | 20 | public + personal |

### Module Access Matrix
| Feature | gilbertus_admin | operator | ceo | board | director+ |
|---------|----------------|----------|-----|-------|-----------|
| **Settings (profile, theme)** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Session info** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **API key (own)** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **User Management** | ✅ | ✅ | ❌ | ❌ | ❌ |
| **Cron Manager** | ✅ | ✅ | ❌ | ❌ | ❌ |
| **System Status** | ✅ | ✅ | ❌ | ❌ | ❌ |
| **API Costs** | ✅ | ✅ | ❌ | ❌ | ❌ |
| **Code Review Queue** | ✅ | ✅ | ❌ | ❌ | ❌ |
| **Audit Log** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Omnius Bridge** | ✅ | ❌ | ❌ | ❌ | ❌ |

### Governance Layer
- CEO/board can propose features (LLM value-gated)
- CEO/board CANNOT: delete features, reduce data scope, modify RBAC, disable syncs/crons
- Protected config keys: `rbac:permissions:*`, `governance:*`, `data_sources:*`, `sync:schedule:*`, `prompt:system`
- `gilbertus_admin` (level 99) bypasses all governance checks

---

## 3. Existing Frontend Patterns to Follow

### Architecture
- **Monorepo:** `apps/web/` (Next.js 16) + `packages/ui/`, `packages/api-client/`, `packages/rbac/`, `packages/i18n/`
- **React 19**, TypeScript 5.7, Tailwind CSS v4, shadcn/ui + Radix UI

### API Client (`packages/api-client/src/`)
- `customFetch<T>({ url, method, data?, signal? })` base wrapper
- Domain modules: one file per domain (e.g., `finance.ts` + `finance-types.ts`)
- Functions: `async function verbNoun(params, signal?): Promise<Type>`
- Env: `NEXT_PUBLIC_GILBERTUS_API_URL` (default `http://127.0.0.1:8000`)

### State Management
- **React Query v5** for server state (caching, refetching)
- **Zustand v5** with persist middleware for UI state
- Custom hooks combine both: `use-[domain].ts`
- Store naming: `[domain]-store.ts`, hook naming: `use-[domain].ts`

### RBAC (frontend)
- `RbacGate` component: `<RbacGate roles={[...]} permission="...">{children}</RbacGate>`
- Hooks: `useRole()`, `usePermissions()`, `useClassifications()`
- Roles defined in `@gilbertus/rbac` package

### Routing
- App Router: `app/(app)/[module]/page.tsx`
- Auth layout: `app/(auth)/login/`
- Middleware: auth check, redirect to `/login` if unauthenticated

### Naming
- Components: PascalCase (`CronManager`, `UserList`)
- Files: kebab-case (`cron-manager.tsx`, `user-list.tsx`)
- Stores: `[domain]-store.ts`
- Types: `[domain]-types.ts`

---

## 4. Data Types / Interfaces Needed

### Settings Types
```typescript
interface UserProfile {
  id: number;
  email: string;
  display_name: string;
  role: string;
  role_level: number;
  department: string | null;
  language: 'pl' | 'en';
  theme: 'dark' | 'light';
  notification_prefs: NotificationPrefs;
}

interface NotificationPrefs {
  email_alerts: boolean;
  whatsapp_alerts: boolean;
  daily_brief: boolean;
}

interface SessionInfo {
  auth_type: 'api_key' | 'azure_ad' | 'dev';
  role: string;
  role_level: number;
  permissions: string[];
  tenant?: string;
  last_login?: string;
}
```

### Admin Types
```typescript
interface CronJob {
  job_name: string;
  schedule: string;
  command: string;
  description: string;
  category: string;
  log_file: string;
  enabled: boolean;
  username: string;
}

interface CronSummary {
  total: number;
  categories: { category: string; jobs: number; active_users: number }[];
  by_user: { username: string; enabled: number; disabled: number }[];
}

interface SystemStatus {
  db: { total_chunks: number; total_events: number; total_sources: number; data_volume_gb: number; tables: Record<string, number> };
  embedding: { indexed_chunks: number; status: 'ok' | 'degraded' | 'error'; qdrant_status: any };
  sources: Record<string, number>;
  last_backup: string;
  services: Record<string, { status: 'ok' | 'error' }>;
  crons: { total: number; enabled: number; failed: string[]; upcoming: any[] };
}

interface BudgetStatus {
  budgets: BudgetItem[];
  daily_total: number;
  module_costs: Record<string, number>;
  alerts: CostAlert[];
}

interface BudgetItem {
  scope: string;
  limit_usd: number;
  spent_usd: number;
  pct: number;
  hard_limit: boolean;
  status: 'ok' | 'warning' | 'exceeded';
}

interface CostAlert {
  scope: string;
  alert_type: string;
  message: string;
  created_at: string;
}

interface CodeFinding {
  id: number;
  file: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  category: string;
  title: string;
  description: string;
  attempts: number;
  last_attempt: string;
}

interface OmniusUser {
  id: number;
  email: string;
  name: string;
  role: string;
  level: number;
  department: string | null;
  active: boolean;
  created: string;
}

interface AuditLogEntry {
  id: number;
  user: string | null;
  action: string;
  resource: string;
  result: 'ok' | 'denied' | 'error' | 'governance_violation';
  ip: string;
  at: string;
}

interface OperatorTask {
  id: number;
  title: string;
  description: string;
  source: string;
  status: 'pending' | 'in_progress' | 'done' | 'blocked';
  result: string | null;
  created: string;
  completed: string | null;
  assigned_to: string;
}
```

### Omnius Bridge Types
```typescript
interface OmniusTenantStatus {
  tenant: string;
  company: string;
  users: number;
  documents: number;
  chunks: number;
  pending_tasks: number;
}

interface OmniusBridgeOverview {
  reh: OmniusTenantStatus;
  ref: OmniusTenantStatus;
}
```

---

## 5. Backend Gaps

### Missing Endpoints (need creation)

| Feature | Gap | Priority |
|---------|-----|----------|
| **User Profile CRUD** | No `/profile` or `/settings` endpoint on Gilbertus API. Omnius has user management but no self-service profile edit. | HIGH |
| **Language/Theme preferences** | No user preferences storage. Need new endpoint or extend Omnius user model. | HIGH |
| **Notification preferences** | No notification prefs API. Need new table + endpoints. | MEDIUM |
| **API key rotation (own)** | Omnius has admin-only key creation. No self-service key rotation endpoint. | MEDIUM |
| **Omnius Bridge cross-tenant** | No unified bridge endpoint. Must query each Omnius tenant separately (two API calls). Consider adding a bridge proxy on Gilbertus side. | HIGH |
| **Cross-tenant search** | No endpoint to search across REH + REF simultaneously. | MEDIUM |
| **Cross-tenant audit** | Must query each tenant's audit log separately. | LOW |
| **Config push** | Omnius has `POST /api/v1/admin/config` per-tenant. No batch push from Gilbertus. | LOW |
| **Cost history/trends** | Only current-day budget status. No historical cost data endpoint (e.g., `/costs/history?days=30`). | MEDIUM |
| **Code findings stats** | Only manual queue. No resolution rate or findings dashboard aggregate endpoint. | LOW |

### Workarounds
- **Profile/Settings:** Can store in `omnius_config` with user-scoped keys (e.g., `user:sebastian:theme`)
- **Omnius Bridge:** Frontend can make parallel calls to both tenant APIs and merge client-side
- **Cost history:** Can add a simple SQL endpoint querying `api_costs` grouped by day

---

## 6. Complexity Estimates

### Settings
| Feature | Complexity | Notes |
|---------|-----------|-------|
| Profile display | Simple | Read from session/auth |
| Language toggle | Simple | i18n already set up in frontend |
| Theme toggle | Simple | NextThemes already integrated |
| Notification prefs | Medium | Needs new backend endpoint + table |
| API key view/rotate | Medium | Needs self-service endpoint on Omnius |
| Session info display | Simple | Available from NextAuth session |

### Admin
| Feature | Complexity | Notes |
|---------|-----------|-------|
| Cron Manager | Medium | List/filter/enable/disable — all endpoints exist |
| System Status | Medium | Single endpoint, rich dashboard rendering |
| API Costs / Budget | Medium | Budget status exists; trends need new endpoint |
| Code Review Queue | Simple | Single list endpoint, display + filter |
| User Management | Medium | CRUD exists on Omnius; need forms + validation |
| Audit Log | Simple | Single list endpoint with filters |

### Omnius Bridge
| Feature | Complexity | Notes |
|---------|-----------|-------|
| Cross-tenant dashboard | Medium | Parallel fetch from 2 tenants, merge client-side |
| Cross-tenant search | Complex | Need to query both `/api/v1/ask` and merge results |
| Cross-tenant audit | Medium | Parallel audit log fetches |
| Operator tasks (both) | Medium | Manage tasks across tenants |
| Config push | Complex | Push to multiple tenants with governance checks |
| Sync trigger | Simple | POST to each tenant's sync endpoint |

### Overall Module Complexity: **Medium-High**
- ~15 distinct features
- 6 require new/extended backend endpoints
- Omnius Bridge is the most complex sub-module (cross-tenant orchestration)
- Settings is the lightest (mostly frontend state + session data)

---

## 7. Recommended Page Structure

```
/settings
  ├── Profile (name, email, role — read-only from session)
  ├── Preferences (language, theme, notifications)
  └── API Keys (view masked key, rotate)

/admin
  ├── /admin/crons — Cron Manager (list, filter by category, enable/disable)
  ├── /admin/status — System Status dashboard (DB, services, embedding, backups)
  ├── /admin/costs — API Costs (budget bars, module breakdown, alerts)
  ├── /admin/code-review — Code findings queue (severity filter, file links)
  ├── /admin/users — User Management (CRUD, roles)
  └── /admin/audit — Audit Log (table with filters)

/admin/omnius — Omnius Bridge (gilbertus_admin ONLY)
  ├── Overview (REH + REF side-by-side status)
  ├── Search (cross-tenant query)
  ├── Tasks (operator tasks across tenants)
  ├── Audit (cross-tenant audit log)
  ├── Config (push config to tenants)
  └── Sync (trigger sync per tenant)
```

---

## 8. Files to Create

### API Client
- `packages/api-client/src/admin.ts` + `admin-types.ts` — Cron, status, costs, code-fixes, user management
- `packages/api-client/src/settings.ts` + `settings-types.ts` — Profile, preferences
- `packages/api-client/src/omnius-bridge.ts` + `omnius-bridge-types.ts` — Cross-tenant operations

### Stores
- `apps/web/lib/stores/admin-store.ts` — Admin UI state (filters, selected cron, etc.)
- `apps/web/lib/stores/settings-store.ts` — Settings UI state

### Hooks
- `apps/web/lib/hooks/use-admin.ts` — React Query hooks for admin endpoints
- `apps/web/lib/hooks/use-settings.ts` — React Query hooks for settings
- `apps/web/lib/hooks/use-omnius-bridge.ts` — React Query hooks for bridge

### UI Components
- `packages/ui/src/components/admin/` — CronManager, SystemStatus, CostsDashboard, CodeReviewQueue, UserManager, AuditLog
- `packages/ui/src/components/settings/` — ProfileCard, PreferencesForm, ApiKeyManager
- `packages/ui/src/components/omnius-bridge/` — TenantOverview, CrossTenantSearch, TaskManager, ConfigPush

### Pages
- `apps/web/app/(app)/settings/page.tsx`
- `apps/web/app/(app)/admin/page.tsx` (redirect to /admin/crons or overview)
- `apps/web/app/(app)/admin/crons/page.tsx`
- `apps/web/app/(app)/admin/status/page.tsx`
- `apps/web/app/(app)/admin/costs/page.tsx`
- `apps/web/app/(app)/admin/code-review/page.tsx`
- `apps/web/app/(app)/admin/users/page.tsx`
- `apps/web/app/(app)/admin/audit/page.tsx`
- `apps/web/app/(app)/admin/omnius/page.tsx`
