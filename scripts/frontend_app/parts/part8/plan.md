# Part 8: Settings, Admin & Omnius Bridge — Architecture Plan

**Module:** Settings (all users), Admin Panel (admin/operator), Omnius Bridge (gilbertus_admin only)
**Date:** 2026-03-29

---

## 1. Component Tree (Visual Hierarchy)

```
AppLayout (existing)
├── Sidebar (existing — /settings, /admin links)
├── Topbar (existing)
└── <main>

    ─── /settings (page.tsx) ──────────────────────────────
    │  SettingsPage
    │  ├── SettingsHeader (title + breadcrumb)
    │  └── Tabs: Profile | Preferences | API Keys
    │      ├── ProfileCard (read-only)
    │      │   ├── Avatar (initials-based)
    │      │   ├── Name, Email, Role, Department
    │      │   └── SessionInfo (auth type, last login, permissions badge list)
    │      ├── PreferencesForm
    │      │   ├── LanguageSelect (PL/EN toggle)
    │      │   ├── ThemeSelect (dark/light — uses existing theme-toggle)
    │      │   └── NotificationToggles (email, whatsapp, daily brief)
    │      └── ApiKeyManager
    │          ├── MaskedKeyDisplay (omnius_****...)
    │          ├── CopyButton
    │          └── RotateButton (with confirm dialog)

    ─── /admin (layout.tsx) ───────────────────────────────
    │  RbacGate roles=['gilbertus_admin', 'operator']
    │  ├── AdminSidebar (left nav)
    │  │   ├── NavItem: Cron Manager → /admin/crons
    │  │   ├── NavItem: System Status → /admin/status
    │  │   ├── NavItem: API Costs → /admin/costs
    │  │   ├── NavItem: Code Review → /admin/code-review
    │  │   ├── NavItem: Users → /admin/users
    │  │   ├── NavItem: Audit Log → /admin/audit (gilbertus_admin only)
    │  │   └── NavItem: Omnius Bridge → /admin/omnius (gilbertus_admin only)
    │  └── <main> (content area)

    ─── /admin/crons (page.tsx) ───────────────────────────
    │  CronManager
    │  ├── CronSummaryBar (total, by category pie, by user counts)
    │  ├── CronFilters (category dropdown, user dropdown, enabled toggle)
    │  └── CronTable
    │      └── CronRow[]
    │          ├── job_name, schedule (cron expression + human-readable)
    │          ├── category badge, username
    │          ├── description (expandable)
    │          └── EnableToggle (switch)

    ─── /admin/status (page.tsx) ──────────────────────────
    │  SystemStatusDashboard
    │  ├── ServiceHealthGrid (postgres, qdrant, whisper — status badges)
    │  ├── DatabaseStats (chunks, events, sources, volume — stat cards)
    │  ├── EmbeddingStatus (indexed chunks, qdrant status)
    │  ├── SourceSyncTable (source_type → last import timestamp)
    │  ├── BackupInfo (last backup time)
    │  └── CronHealth (total, enabled, failed list, upcoming)

    ─── /admin/costs (page.tsx) ───────────────────────────
    │  CostsDashboard
    │  ├── BudgetBars (scope → progress bar with pct, color by status)
    │  ├── DailyTotalCard (today's spend)
    │  ├── ModuleCostBreakdown (bar chart or table: module → cost_usd)
    │  └── CostAlerts (alert cards: scope, type, message, timestamp)

    ─── /admin/code-review (page.tsx) ─────────────────────
    │  CodeReviewQueue
    │  ├── FindingsFilters (severity dropdown, category dropdown)
    │  ├── FindingsStats (count by severity — badges)
    │  └── FindingsTable
    │      └── FindingRow[]
    │          ├── severity badge (color-coded)
    │          ├── file path (monospace, truncated)
    │          ├── title + description (expandable)
    │          └── attempts count + last attempt timestamp

    ─── /admin/users (page.tsx) ───────────────────────────
    │  UserManager
    │  ├── UserListHeader (count + "Add User" button)
    │  ├── UserTable
    │  │   └── UserRow[]
    │  │       ├── name, email, role badge, department
    │  │       ├── active status indicator
    │  │       └── Actions: Edit, Deactivate
    │  └── UserFormDialog (create/edit modal)
    │      ├── name, email inputs
    │      ├── role select, department input
    │      └── Save / Cancel buttons

    ─── /admin/audit (page.tsx) ───────────────────────────
    │  AuditLog (gilbertus_admin ONLY)
    │  ├── AuditFilters (user, action, result, date range)
    │  └── AuditTable
    │      └── AuditRow[]
    │          ├── timestamp, user, action, resource
    │          ├── result badge (ok/denied/error/governance_violation)
    │          └── IP address

    ─── /admin/omnius (page.tsx) ──────────────────────────
    │  OmniusBridge (gilbertus_admin ONLY)
    │  ├── Tabs: Overview | Tasks | Audit | Config | Sync
    │  ├── TenantOverview
    │  │   ├── TenantCard (REH) — users, docs, chunks, pending
    │  │   └── TenantCard (REF) — users, docs, chunks, pending
    │  ├── OperatorTasks
    │  │   ├── TenantTabs (REH | REF)
    │  │   ├── TaskFilters (status dropdown)
    │  │   ├── TaskTable (id, title, status, assigned_to, created)
    │  │   └── CreateTaskDialog
    │  ├── CrossTenantAudit
    │  │   ├── TenantTabs (REH | REF | Both)
    │  │   └── AuditTable (reuses AuditLog component pattern)
    │  ├── ConfigPush
    │  │   ├── ConfigList (current config per tenant)
    │  │   └── ConfigPushForm (key, value, target tenant)
    │  └── SyncTrigger
    │      ├── TenantCard (REH) + "Sync" button
    │      └── TenantCard (REF) + "Sync" button
```

---

## 2. File Tree (Every File Path)

```
frontend/
├── apps/web/
│   ├── app/(app)/
│   │   ├── settings/
│   │   │   └── page.tsx                              # Settings page (all users)
│   │   └── admin/
│   │       ├── layout.tsx                            # Admin layout with sidebar + RBAC gate
│   │       ├── page.tsx                              # Redirect to /admin/crons
│   │       ├── crons/
│   │       │   └── page.tsx                          # Cron Manager page
│   │       ├── status/
│   │       │   └── page.tsx                          # System Status page
│   │       ├── costs/
│   │       │   └── page.tsx                          # API Costs page
│   │       ├── code-review/
│   │       │   └── page.tsx                          # Code Review Queue page
│   │       ├── users/
│   │       │   └── page.tsx                          # User Management page
│   │       ├── audit/
│   │       │   └── page.tsx                          # Audit Log page
│   │       └── omnius/
│   │           └── page.tsx                          # Omnius Bridge page
│   │
│   └── lib/
│       ├── stores/
│       │   ├── settings-store.ts                     # Settings UI state
│       │   └── admin-store.ts                        # Admin UI state (filters, tabs)
│       └── hooks/
│           ├── use-settings.ts                       # React Query hooks for settings
│           ├── use-admin.ts                          # React Query hooks for admin endpoints
│           └── use-omnius-bridge.ts                  # React Query hooks for Omnius Bridge
│
├── packages/
│   ├── api-client/src/
│   │   ├── settings.ts                               # Settings API functions
│   │   ├── settings-types.ts                         # Settings types
│   │   ├── admin.ts                                  # Admin API functions (crons, status, costs, code-fixes, users)
│   │   ├── admin-types.ts                            # Admin types
│   │   ├── omnius-bridge.ts                          # Omnius Bridge API functions
│   │   ├── omnius-bridge-types.ts                    # Omnius Bridge types
│   │   └── index.ts                                  # Updated with new exports
│   │
│   ├── ui/src/components/
│   │   ├── settings/
│   │   │   ├── profile-card.tsx                      # Read-only profile display
│   │   │   ├── preferences-form.tsx                  # Language, theme, notification prefs
│   │   │   ├── api-key-manager.tsx                   # View/rotate API key
│   │   │   └── index.ts                              # Re-exports
│   │   ├── admin/
│   │   │   ├── admin-sidebar.tsx                     # Admin navigation sidebar
│   │   │   ├── cron-manager.tsx                      # Cron list + filters + enable/disable
│   │   │   ├── system-status.tsx                     # System health dashboard
│   │   │   ├── costs-dashboard.tsx                   # Budget bars + module costs
│   │   │   ├── code-review-queue.tsx                 # Findings table + filters
│   │   │   ├── user-manager.tsx                      # User CRUD table + dialog
│   │   │   ├── audit-log.tsx                         # Audit log table + filters
│   │   │   └── index.ts                              # Re-exports
│   │   └── omnius-bridge/
│   │       ├── tenant-overview.tsx                    # Side-by-side tenant status cards
│   │       ├── operator-tasks.tsx                     # Cross-tenant task management
│   │       ├── cross-tenant-audit.tsx                 # Combined audit view
│   │       ├── config-push.tsx                        # Push config to tenants
│   │       ├── sync-trigger.tsx                       # Trigger sync buttons
│   │       └── index.ts                              # Re-exports
│   │
│   └── rbac/src/
│       ├── navigation.ts                             # Updated: add 'admin' module
│       └── permissions.ts                            # Updated: add admin permissions if needed
```

---

## 3. API Integration Map (Component → Endpoint)

### Settings
| Component | API Function | Endpoint | Method |
|-----------|-------------|----------|--------|
| ProfileCard | `getSessionInfo()` | Session/auth context | READ |
| PreferencesForm | `getUserPreferences()` | `GET /api/v1/admin/config` (user-scoped) | GET |
| PreferencesForm | `updateUserPreferences()` | `POST /api/v1/admin/config` (user-scoped) | POST |
| ApiKeyManager | `getOwnApiKeys()` | `GET /api/v1/admin/api-keys` (filtered own) | GET |
| ApiKeyManager | `rotateApiKey()` | `POST /api/v1/admin/api-keys` | POST |

**Note:** Profile data comes from session/auth context (NextAuth). Preferences stored via Omnius config with user-scoped keys (`user:{email}:theme`, `user:{email}:language`, etc.). Alternatively, stored client-side in Zustand (MVP approach — no new backend needed).

### Admin
| Component | API Function | Endpoint | Method |
|-----------|-------------|----------|--------|
| CronManager | `getCrons()` | `GET /crons` | GET |
| CronManager | `getCronSummary()` | `GET /crons/summary` | GET |
| CronManager | `enableCron()` | `POST /crons/{name}/enable` | POST |
| CronManager | `disableCron()` | `POST /crons/{name}/disable` | POST |
| SystemStatus | `getSystemStatus()` | `GET /status` | GET |
| CostsDashboard | `getCostBudget()` | `GET /costs/budget` | GET |
| CodeReviewQueue | `getCodeFindings()` | `GET /code-fixes/manual-queue` | GET |
| UserManager | `getUsers()` | `GET /api/v1/admin/users` (Omnius) | GET |
| UserManager | `createUser()` | `POST /api/v1/admin/users` (Omnius) | POST |
| AuditLog | `getAuditLog()` | `GET /api/v1/admin/audit` (Omnius) | GET |

### Omnius Bridge
| Component | API Function | Endpoint | Method |
|-----------|-------------|----------|--------|
| TenantOverview | `getTenantStatus(tenant)` | `GET /api/v1/status` (per tenant) | GET |
| OperatorTasks | `getOperatorTasks(tenant)` | `GET /api/v1/admin/operator-tasks` | GET |
| OperatorTasks | `createTask(tenant, data)` | `POST /api/v1/admin/operator-tasks` | POST |
| OperatorTasks | `updateTask(tenant, id, data)` | `PATCH /api/v1/admin/operator-tasks/{id}` | PATCH |
| CrossTenantAudit | `getAuditLog(tenant)` | `GET /api/v1/admin/audit` (per tenant) | GET |
| ConfigPush | `getConfig(tenant)` | `GET /api/v1/admin/config` | GET |
| ConfigPush | `pushConfig(tenant, key, value)` | `POST /api/v1/admin/config` | POST |
| SyncTrigger | `triggerSync(tenant, source)` | `POST /api/v1/admin/sync` | POST |

**Omnius tenant routing:** The bridge API functions accept a `tenant` param ('reh' | 'ref') that determines the base URL. Env vars: `NEXT_PUBLIC_OMNIUS_REH_URL`, `NEXT_PUBLIC_OMNIUS_REF_URL`.

---

## 4. RBAC Per View/Component

| Route | Roles | Gate Method |
|-------|-------|-------------|
| `/settings` | `['*']` (all users) | No gate needed — in MODULES nav |
| `/admin` (layout) | `['gilbertus_admin', 'operator']` | `RbacGate` in layout.tsx |
| `/admin/crons` | `['gilbertus_admin', 'operator']` | Inherited from layout |
| `/admin/status` | `['gilbertus_admin', 'operator']` | Inherited from layout |
| `/admin/costs` | `['gilbertus_admin', 'operator']` | Inherited from layout |
| `/admin/code-review` | `['gilbertus_admin', 'operator']` | Inherited from layout |
| `/admin/users` | `['gilbertus_admin', 'operator']` | Inherited from layout |
| `/admin/audit` | `['gilbertus_admin']` | Additional `RbacGate` on page |
| `/admin/omnius` | `['gilbertus_admin']` | Additional `RbacGate` on page |

**AdminSidebar:** Conditionally shows Audit Log and Omnius Bridge links only for `gilbertus_admin` using `useRole()` check.

---

## 5. State Management (Zustand Store Shapes)

### settings-store.ts
```typescript
interface SettingsStore {
  activeTab: 'profile' | 'preferences' | 'api-keys';
  language: 'pl' | 'en';          // persisted, used for i18n
  theme: 'dark' | 'light';        // persisted, syncs with next-themes
  notifications: {
    email_alerts: boolean;
    whatsapp_alerts: boolean;
    daily_brief: boolean;
  };

  setActiveTab: (tab) => void;
  setLanguage: (lang) => void;
  setTheme: (theme) => void;
  setNotifications: (prefs) => void;
}
// persist key: 'gilbertus-settings'
```

### admin-store.ts
```typescript
interface AdminStore {
  // Cron filters
  cronCategoryFilter: string | null;
  cronUserFilter: string | null;
  cronEnabledFilter: boolean | null;

  // Code review filters
  codeReviewSeverityFilter: string | null;
  codeReviewCategoryFilter: string | null;

  // Audit filters
  auditUserFilter: string | null;
  auditActionFilter: string | null;
  auditResultFilter: string | null;

  // Omnius Bridge
  omniusActiveTab: 'overview' | 'tasks' | 'audit' | 'config' | 'sync';
  omniusActiveTenant: 'reh' | 'ref';

  // Admin sidebar
  adminActiveSection: string;

  // Setters
  setCronCategoryFilter: (v) => void;
  setCronUserFilter: (v) => void;
  setCronEnabledFilter: (v) => void;
  setCodeReviewSeverityFilter: (v) => void;
  setCodeReviewCategoryFilter: (v) => void;
  setAuditUserFilter: (v) => void;
  setAuditActionFilter: (v) => void;
  setAuditResultFilter: (v) => void;
  setOmniusActiveTab: (tab) => void;
  setOmniusActiveTenant: (tenant) => void;
  setAdminActiveSection: (section) => void;
}
// persist key: 'gilbertus-admin'
```

---

## 6. UX Flows

### Settings — Change Theme
1. User navigates to `/settings` → Preferences tab
2. Clicks theme toggle (dark/light)
3. `settingsStore.setTheme()` updates Zustand → persisted to localStorage
4. `next-themes` provider picks up change → immediate visual switch
5. No backend call needed (MVP — client-side only)

### Settings — View API Key
1. User navigates to `/settings` → API Keys tab
2. `useOwnApiKeys()` hook fetches `GET /api/v1/admin/api-keys` filtered to own user
3. Key displayed masked: `omnius_abc...xyz`
4. Copy button → copies full key to clipboard, toast confirmation

### Admin — Enable/Disable Cron
1. Admin navigates to `/admin/crons`
2. `useCrons()` + `useCronSummary()` load data
3. Admin toggles switch on a cron job
4. Mutation: `POST /crons/{job_name}/enable` or `/disable` with `?user=sebastian`
5. Optimistic update: toggle immediately, revert on error
6. Success toast: "Cron {name} włączony/wyłączony"

### Admin — System Status
1. Admin navigates to `/admin/status`
2. `useSystemStatus()` hook fetches `GET /status`
3. Dashboard renders: service health badges (green/red), DB stats cards, source sync table
4. Auto-refresh every 30s (`refetchInterval: 30000`)

### Admin — Manage Users
1. Admin navigates to `/admin/users`
2. `useOmniusUsers()` fetches user list from Omnius
3. Click "Dodaj użytkownika" → UserFormDialog opens
4. Fill name, email, role, department → Submit
5. `createOmniusUser()` mutation → `POST /api/v1/admin/users`
6. Success → dialog closes, list refetches

### Omnius Bridge — Cross-Tenant Overview
1. gilbertus_admin navigates to `/admin/omnius`
2. Two parallel fetches: `getTenantStatus('reh')` + `getTenantStatus('ref')`
3. Side-by-side TenantCards show: users, documents, chunks, pending tasks
4. Cards color-coded: green (healthy), yellow (pending > 10), red (error)

### Omnius Bridge — Trigger Sync
1. Admin clicks "Sync" on a tenant card
2. Confirm dialog: "Uruchomić synchronizację dla {tenant}?"
3. `triggerSync(tenant, source)` → `POST /api/v1/admin/sync`
4. Response: `{ status: "queued" }` → success toast
5. Tenant card shows "Synchronizacja w toku..." badge

---

## 7. Navigation Updates

Add 'admin' module to `packages/rbac/src/navigation.ts`:
```typescript
{ id: 'admin', icon: 'Shield', roles: ['gilbertus_admin', 'operator'],
  label: { pl: 'Admin', en: 'Admin' }, path: '/admin' },
```

Existing 'settings' and 'omnius' modules already defined — 'omnius' route will be removed from top-level nav and moved under /admin/omnius instead. Update 'omnius' module path to '/admin/omnius'.

---

## 8. MVP vs Future Scope

### MVP (this implementation)
- Settings: profile display from session, theme/language toggle (client-side), API key view
- Admin: cron list + enable/disable, system status, cost budget, code findings list, user list + create
- Omnius Bridge: tenant overview, operator tasks, sync trigger

### Future (not in this implementation)
- Notification preferences backend (needs new table + endpoints)
- API key rotation (needs self-service endpoint)
- Cost history/trends chart (needs new endpoint)
- Code findings resolution tracking
- Cross-tenant search
- Config push with governance validation
- Cross-tenant audit aggregation
