# Part 0: Foundation — Discovery Report

**Date:** 2026-03-29
**Module:** P0 — Scaffolding, API Client, Auth, Layout, i18n

---

## 1. Current State

**No frontend code exists.** The directory `/home/sebastian/personal-ai/frontend/` does not exist yet — everything must be scaffolded from scratch.

An orchestration system exists at `scripts/frontend_app/` with prompts for all 10 parts (P0–P9) and a `queue.json` tracking progress.

---

## 2. API Endpoint Inventory (Relevant to P0)

P0 needs only auth, health, and OpenAPI endpoints. The full API has **116+ endpoints** — below are the ones relevant to foundation:

### Auth & System Endpoints (Gilbertus API — port 8000)

| Method | Path | Auth | Purpose | Response |
|--------|------|------|---------|----------|
| GET | `/health` | None | Health check | `{"status": "ok"}` |
| GET | `/version` | None | App version | `{"version": "0.1.0", ...}` |
| GET | `/status` | None | System status | JSON with DB stats, sync status |
| GET | `/openapi.json` | None | OpenAPI spec | Full spec (for orval generation) |
| GET | `/docs` | None | Swagger UI | HTML |

### Auth Mechanism (Gilbertus)

- **No dedicated login endpoint** — stateless API key auth
- **API key sent via:** `X-API-Key` header, `Authorization: Bearer <key>`, or `?api_key=` query param
- **Trusted IPs bypass auth:** `127.0.0.1`, `localhost`, `::1`
- **Dev mode:** If `GILBERTUS_API_KEY` env var is unset, auth is disabled entirely
- **CORS:** Allows `localhost:3000`, `localhost:8080` by default; customizable via `CORS_ALLOWED_ORIGINS`
- **Allowed methods:** GET, POST only
- **Allowed headers:** Content-Type, X-API-Key, Authorization

### Auth Mechanism (Omnius API — separate service)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/admin/api-keys` | `users:manage:all` | Create API key |
| GET | `/admin/users` | `users:manage:all` | List users |
| POST | `/admin/users` | `users:manage:all` | Create user |

Three auth methods:
1. **API Key:** SHA-256 hashed lookup in `omnius_api_keys` table → returns role + permissions
2. **Azure AD JWT:** Validates against Azure tenant, maps `preferred_username` → user lookup
3. **Dev mode:** `X-User-Email` header when `OMNIUS_DEV_AUTH=1` and localhost

**User dict after auth:**
```typescript
{
  auth_type: "api_key" | "azure_ad" | "dev";
  user_id: number;
  email: string;
  display_name: string;
  role_name: string;
  role_level: number;
  department: string | null;
  permissions: string[];
}
```

---

## 3. RBAC Rules

### Roles (7 total, hierarchical by level)

| Role | Level | Description |
|------|-------|-------------|
| `gilbertus_admin` | 99 | System admin — bypass all checks |
| `operator` | 70 | IT ops — infra only, NO business data |
| `ceo` | 60 | Full company access + user mgmt |
| `board` | 50 | Company-wide data, manage directors+ |
| `director` | 40 | Department scope |
| `manager` | 30 | Team scope |
| `specialist` | 20 | Own tasks only |

### Sidebar Navigation RBAC Mapping

```typescript
const MODULES = {
  dashboard:    { roles: ['*'] },                              // all roles
  chat:         { roles: ['*'] },                              // all roles
  people:       { roles: ['ceo', 'board', 'director'] },
  intelligence: { roles: ['ceo', 'board'] },
  compliance:   { roles: ['ceo', 'board', 'director'] },
  market:       { roles: ['ceo', 'board', 'director'] },
  finance:      { roles: ['ceo', 'board'] },
  process:      { roles: ['ceo', 'board', 'director'] },
  decisions:    { roles: ['ceo'] },
  calendar:     { roles: ['ceo', 'board', 'director', 'manager'] },
  documents:    { roles: ['ceo', 'board', 'director'] },
  voice:        { roles: ['ceo', 'board'] },
  settings:     { roles: ['*'] },                              // all roles
  omnius:       { roles: ['gilbertus_admin'] },                // admin only
}
```

### Classification Levels (data access)

| Role | Visible Classifications |
|------|------------------------|
| `gilbertus_admin` | public, internal, confidential, ceo_only, personal |
| `ceo` | public, internal, confidential, ceo_only, personal |
| `board` | public, internal, confidential, personal |
| `director` | public, internal, personal |
| `manager` | public, internal, personal |
| `specialist` | public, personal |
| `operator` | (none — infra only) |

### Permission Checking Logic

```python
def has_permission(user, permission):
    if user.role_level >= 99:  # ADMIN_BYPASS
        return True
    return permission in user.permissions
```

### Key Permissions (relevant to frontend)

- `data:read:all` / `data:read:department` / `data:read:team` / `data:read:own`
- `financials:read`
- `evaluations:read:all` / `evaluations:read:reports`
- `communications:read:all` / `communications:read:department`
- `users:manage:all` / `users:manage:below`
- `config:write:system` / `config:write:department` / `config:write:own`
- `queries:create` / `queries:create:department`
- `commands:email`, `commands:ticket`, `commands:meeting`, `commands:task`, `commands:sync`
- `views:configure:own`

---

## 4. Existing Patterns to Follow

**No existing frontend patterns** — P0 establishes all conventions. Backend patterns to mirror:

- **Structured logging:** Backend uses `structlog` → frontend should use structured console or reporting
- **Connection pooling:** Backend uses `app/db/postgres.py` pool → frontend API client should use single configured fetch wrapper
- **Auth middleware:** Backend uses `@require_permission` decorators → frontend should use `<RbacGate>` component + `usePermissions()` hook
- **Naming:** Backend uses snake_case Python → frontend uses camelCase TypeScript, PascalCase components

---

## 5. Data Types / Interfaces Needed for P0

### NextAuth Session (JWT payload)

```typescript
interface Session {
  user: {
    id: number;
    email: string;
    displayName: string;
    role: RoleName;
    roleLevel: number;
    permissions: string[];
    department: string | null;
    tenant: "gilbertus" | "ref" | "reh";
    authType: "api_key" | "azure_ad" | "dev";
  };
}

type RoleName = "gilbertus_admin" | "operator" | "ceo" | "board" | "director" | "manager" | "specialist";
```

### RBAC Types

```typescript
interface ModuleConfig {
  icon: string;
  roles: RoleName[] | ["*"];
  label: { pl: string; en: string };
  path: string;
}

interface Permission {
  resource: string;  // e.g. "data", "users", "config"
  action: string;    // e.g. "read", "manage", "write"
  scope: string;     // e.g. "all", "department", "own"
}
```

### API Client Base Config

```typescript
interface ApiConfig {
  baseUrl: string;        // http://127.0.0.1:8000
  apiKey?: string;        // X-API-Key header
  bearerToken?: string;   // Authorization: Bearer
  timeout?: number;       // ms
}
```

---

## 6. Backend Gaps & Integration Notes

### Auth Flow Gaps

| Gap | Impact | Workaround |
|-----|--------|------------|
| No `/login` endpoint for API key validation | Can't verify API key server-side before setting session | Frontend validates by calling `/health` with API key; if 200 → key is valid |
| No `/me` or `/whoami` endpoint | Can't fetch current user profile after login | For Gilbertus: hardcode `gilbertus_admin` role. For Omnius: use Omnius API user lookup |
| CORS allows only GET/POST | No PUT/DELETE from browser | Some endpoints use POST for updates (backend design choice) |
| No session/refresh tokens | API key is the only credential | Store API key in NextAuth JWT, send on every request |

### Recommendations

1. **Add `/auth/validate` endpoint** to Gilbertus API — accepts API key, returns user info (or 401). This avoids hardcoding roles.
2. **Add `/me` endpoint** to Omnius API — returns authenticated user's profile + permissions.
3. **Extend CORS methods** to include PUT, DELETE, PATCH for full REST support.

### SSE / WebSocket Needs (future parts)

- Voice (P7): WebSocket at `/voice/ws` already exists
- Chat streaming (P1): Will need SSE on `/ask` endpoint
- Not needed for P0.

---

## 7. Complexity Estimate

| Feature | Complexity | Notes |
|---------|-----------|-------|
| Monorepo scaffolding (pnpm, tsconfig) | Simple | Standard pnpm workspace setup |
| Next.js 15 + App Router setup | Simple | Standard Next.js init |
| Tailwind v4 + dark theme | Simple | CSS variables + tailwind config |
| shadcn/ui installation + base components | Simple | CLI init + component add |
| NextAuth v5 (API key flow) | **Medium** | Custom credentials provider, no standard `/login` endpoint |
| NextAuth v5 (Azure AD flow) | **Medium** | Standard Azure AD provider, but need Omnius user lookup |
| Auth middleware (route protection) | Simple | Standard NextAuth middleware pattern |
| RBAC package (permissions, hooks) | **Medium** | Mirror Python permissions.py → TypeScript, usePermissions() hook |
| Sidebar with RBAC filtering | Simple | Map MODULES config, filter by role |
| Command palette (Cmd+K) | Simple | shadcn/ui `<Command>` component |
| i18n (next-intl, PL primary) | Simple | Standard next-intl setup with PL/EN JSON |
| API client generation (orval) | **Medium** | Requires working OpenAPI spec, orval config, auth interceptor |
| Zustand stores (auth, sidebar) | Simple | 2-3 small stores |
| Tauri 2.0 placeholder | Simple | Cargo.toml + tauri.conf.json skeleton |
| **Total P0** | **Medium** | ~15-20 files to create, 2-3 medium complexity items |

---

## 8. OpenAPI Spec Availability

The Gilbertus API exposes OpenAPI spec at `http://127.0.0.1:8000/openapi.json` with **116+ endpoints**. This can be used by orval to generate a typed TypeScript client.

**Full endpoint count by category:**
- System: 3 (health, version, status)
- Core AI: 5 (ask, timeline, summary, brief, alerts)
- People: 8 (CRUD + scorecard + evaluation + sentiment)
- Compliance: 25+ (matters, obligations, documents, trainings, risks, RACI)
- Market/Competitors: 8
- Finance: 4
- Process Intel: 20+
- Decisions: 6
- Voice: 5
- Calendar: 5
- Delegation: 5
- Others: 20+

---

## 9. Key Decisions for Implementation

1. **Auth strategy for Sebastian (Gilbertus):**
   - Use NextAuth `CredentialsProvider` with API key
   - Validate by calling `GET /health` with key
   - Store key in JWT, set role to `gilbertus_admin`

2. **Auth strategy for Omnius users:**
   - Use NextAuth `AzureADProvider`
   - After OAuth callback, call Omnius API to get user role/permissions
   - Store user profile in JWT

3. **API client generation:**
   - Use orval with `http://127.0.0.1:8000/openapi.json`
   - Generate to `packages/api-client/src/gilbertus.ts`
   - Add auth interceptor in `packages/api-client/src/base.ts`

4. **RBAC package:**
   - Mirror `omnius/core/permissions.py` role→permission mapping
   - Export `usePermissions()`, `useRole()` hooks
   - Export `<RbacGate permission="..." />` component
   - Export `getNavigationModules(role)` for sidebar filtering
