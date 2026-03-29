# Part 0: Foundation — Architecture Plan

**Date:** 2026-03-29
**Status:** Ready for implementation

---

## 1. Component Tree

```
<html lang="pl" class="dark">
  <body>
    <ThemeProvider>                          # packages/ui — next-themes
      <NextIntlProvider locale="pl">        # packages/i18n
        <SessionProvider>                   # NextAuth v5
          <QueryClientProvider>             # @tanstack/react-query (for orval)

            # Route: /(auth)/login
            <LoginPage>
              <LoginForm>                   # API key input + Azure AD button
                <ApiKeyInput />
                <AzureAdButton />
              </LoginForm>
            </LoginPage>

            # Route: /(app)/* — requires auth
            <AppLayout>
              <Sidebar>                     # 260px, collapsible to 64px
                <SidebarLogo />
                <SidebarNav>                # filtered by RBAC
                  <SidebarNavItem />        # per module
                </SidebarNav>
                <SidebarFooter>
                  <UserMenu />              # avatar, role badge, logout
                </SidebarFooter>
              </Sidebar>
              <main>
                <Topbar>
                  <BreadcrumbNav />
                  <CommandPaletteTrigger /> # Cmd+K
                  <ThemeToggle />
                  <NotificationBell />     # placeholder for P2
                </Topbar>
                <PageContent>
                  {children}               # module pages (P1-P9)
                </PageContent>
              </main>
              <CommandPalette />           # global overlay, Cmd+K
            </AppLayout>

          </QueryClientProvider>
        </SessionProvider>
      </NextIntlProvider>
    </ThemeProvider>
  </body>
</html>
```

---

## 2. File Tree (every file)

```
frontend/
├── pnpm-workspace.yaml
├── package.json                           # root: scripts, devDeps (typescript, eslint)
├── tsconfig.base.json                     # shared TS config
├── .eslintrc.js                           # shared ESLint
├── .gitignore
├── .env.example                           # env template
│
├── apps/
│   ├── web/
│   │   ├── package.json                   # next, react, next-auth, zustand, next-intl
│   │   ├── tsconfig.json                  # extends ../../tsconfig.base.json
│   │   ├── next.config.ts                 # transpilePackages, i18n, env
│   │   ├── tailwind.config.ts             # dark theme, CSS vars, Inter font
│   │   ├── postcss.config.js
│   │   ├── middleware.ts                  # NextAuth + locale middleware
│   │   ├── .env.local.example             # NEXTAUTH_SECRET, API keys
│   │   ├── app/
│   │   │   ├── layout.tsx                 # RootLayout: html, body, providers
│   │   │   ├── globals.css                # Tailwind directives + CSS variables
│   │   │   ├── (auth)/
│   │   │   │   ├── layout.tsx             # centered card layout
│   │   │   │   └── login/
│   │   │   │       └── page.tsx           # LoginPage
│   │   │   ├── (app)/
│   │   │   │   ├── layout.tsx             # AppLayout: sidebar + topbar + main
│   │   │   │   ├── page.tsx               # redirect → /dashboard
│   │   │   │   └── dashboard/
│   │   │   │       └── page.tsx           # placeholder "Welcome" page
│   │   │   └── api/
│   │   │       └── auth/
│   │   │           └── [...nextauth]/
│   │   │               └── route.ts       # NextAuth API route
│   │   ├── lib/
│   │   │   ├── auth.ts                    # NextAuth config (providers, callbacks)
│   │   │   └── stores/
│   │   │       ├── sidebar-store.ts       # collapsed state
│   │   │       └── command-palette-store.ts  # open/close, search query
│   │   └── components/                    # app-specific wrappers if needed
│   │       └── providers.tsx              # all providers composed
│   │
│   └── desktop/                           # Tauri placeholder
│       ├── package.json
│       └── src-tauri/
│           ├── tauri.conf.json
│           ├── Cargo.toml
│           └── src/
│               └── main.rs                # minimal Tauri entry
│
├── packages/
│   ├── ui/
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   └── src/
│   │       ├── index.ts                   # re-exports
│   │       └── components/
│   │           ├── sidebar.tsx
│   │           ├── topbar.tsx
│   │           ├── command-palette.tsx
│   │           ├── theme-provider.tsx      # next-themes wrapper
│   │           ├── theme-toggle.tsx
│   │           ├── rbac-gate.tsx
│   │           ├── skeleton-card.tsx
│   │           ├── user-menu.tsx
│   │           └── login-form.tsx
│   │
│   ├── api-client/
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   ├── orval.config.ts                # orval configuration
│   │   ├── scripts/
│   │   │   └── generate.sh                # fetch openapi.json + run orval
│   │   └── src/
│   │       ├── index.ts                   # re-exports
│   │       ├── base.ts                    # fetch wrapper with auth interceptor
│   │       ├── gilbertus.ts               # generated (orval output)
│   │       └── types.ts                   # shared API types
│   │
│   ├── rbac/
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   └── src/
│   │       ├── index.ts                   # re-exports
│   │       ├── roles.ts                   # role definitions + level hierarchy
│   │       ├── permissions.ts             # role → permissions map
│   │       ├── classifications.ts         # role → allowed classifications
│   │       ├── hooks.ts                   # usePermissions(), useRole(), useClassifications()
│   │       └── navigation.ts              # MODULES config, getNavigationModules(role)
│   │
│   └── i18n/
│       ├── package.json
│       ├── tsconfig.json
│       ├── src/
│       │   ├── index.ts                   # re-exports, config
│       │   └── request.ts                 # next-intl request config
│       └── messages/
│           ├── pl.json                    # Polish (primary)
│           └── en.json                    # English
```

**Total: ~55 files**

---

## 3. API Integration Map

| Component | Endpoint | Method | Auth | Purpose |
|-----------|----------|--------|------|---------|
| LoginForm (API key) | `GET /health` | GET | X-API-Key | Validate API key works |
| LoginForm (Azure AD) | NextAuth OAuth | — | Azure AD | OAuth flow |
| NextAuth callback | `GET /admin/users` | GET | Bearer JWT | Look up Omnius user after OAuth |
| API client (all) | Any endpoint | GET/POST | X-API-Key | Auth interceptor adds header |
| orval generate | `GET /openapi.json` | GET | None | Generate TypeScript client |

---

## 4. RBAC Per View/Component

| View/Component | Access Rule |
|----------------|------------|
| `/login` | Public (unauthenticated only) |
| `/(app)/*` | Any authenticated user (middleware enforced) |
| `/(app)/dashboard` | All roles (`*`) |
| Sidebar → People | `ceo`, `board`, `director` |
| Sidebar → Intelligence | `ceo`, `board` |
| Sidebar → Compliance | `ceo`, `board`, `director` |
| Sidebar → Market | `ceo`, `board`, `director` |
| Sidebar → Finance | `ceo`, `board` |
| Sidebar → Process | `ceo`, `board`, `director` |
| Sidebar → Decisions | `ceo` only |
| Sidebar → Calendar | `ceo`, `board`, `director`, `manager` |
| Sidebar → Documents | `ceo`, `board`, `director` |
| Sidebar → Voice | `ceo`, `board` |
| Sidebar → Settings | All roles (`*`) |
| Sidebar → Omnius | `gilbertus_admin` only |
| `<RbacGate>` | Generic permission check wrapper |

---

## 5. State Management (Zustand Stores)

### `sidebar-store.ts`
```typescript
interface SidebarStore {
  collapsed: boolean;
  toggle: () => void;
  setCollapsed: (v: boolean) => void;
}
```
Persisted to localStorage.

### `command-palette-store.ts`
```typescript
interface CommandPaletteStore {
  open: boolean;
  query: string;
  setOpen: (v: boolean) => void;
  setQuery: (q: string) => void;
}
```

---

## 6. UX Flows

### Flow 1: API Key Login (Sebastian)
1. User visits `/` → middleware redirects to `/login`
2. User enters API key in input field
3. Frontend calls `GET /health` with `X-API-Key: <key>` header
4. If 200 → NextAuth `signIn("credentials", { apiKey })` → JWT created with role `gilbertus_admin`
5. Redirect to `/dashboard`
6. If not 200 → show "Invalid API key" error

### Flow 2: Azure AD Login (Omnius users)
1. User clicks "Sign in with Microsoft" button
2. NextAuth redirects to Azure AD OAuth
3. On callback: NextAuth calls Omnius API `GET /admin/users` to find user by email
4. JWT populated with user's role, permissions, department
5. Redirect to `/dashboard`

### Flow 3: Sidebar Navigation
1. On `(app)/layout.tsx` mount, read session → extract role
2. Call `getNavigationModules(role)` from `@gilbertus/rbac`
3. Render only modules user has access to
4. Active module highlighted based on pathname
5. Click → navigate to `/(app)/[module]`
6. Collapse button toggles sidebar width (260px ↔ 64px), persisted to localStorage

### Flow 4: Command Palette (Cmd+K)
1. User presses Cmd+K (or Ctrl+K)
2. Overlay opens with search input
3. Options: navigation modules (filtered by RBAC) + quick actions
4. Select → navigate or execute action
5. Escape → close

### Flow 5: Theme Toggle
1. Default: dark theme (system preference respected)
2. Click theme toggle in topbar → cycles dark/light/system
3. Persisted via next-themes to localStorage

---

## 7. Auth Configuration Detail

### NextAuth v5 Config (`lib/auth.ts`)

```typescript
// Providers:
// 1. CredentialsProvider — API key login
//    - authorize(): call GET /health with X-API-Key
//    - If 200: return { id: "gilbertus", role: "gilbertus_admin", ... }
//    - If fail: return null
//
// 2. AzureADProvider — OAuth for Omnius users
//    - clientId, clientSecret, tenantId from env
//    - After sign-in: look up user via Omnius API
//
// Callbacks:
// - jwt(): merge role, permissions, tenant into token
// - session(): expose role, permissions in session.user
//
// Pages:
// - signIn: "/login"
```

### Middleware (`middleware.ts`)

```typescript
// 1. Check if path is public (login, api/auth, _next, static)
// 2. If not public: check NextAuth session
// 3. If no session: redirect to /login
// 4. If session: allow through
// 5. Handle locale (next-intl)
```

---

## 8. Design Tokens (CSS Variables)

```css
:root {
  /* Dark theme (default) */
  --bg: #0f1117;
  --surface: #1a1d27;
  --surface-hover: #252836;
  --accent: #6366f1;
  --accent-hover: #818cf8;
  --text: #e2e8f0;
  --text-muted: #94a3b8;
  --border: #2d3148;
  --error: #ef4444;
  --success: #22c55e;
  --warning: #f59e0b;
  --radius: 8px;
  --sidebar-width: 260px;
  --sidebar-collapsed: 64px;
  --topbar-height: 56px;
  --font-sans: 'Inter', system-ui, sans-serif;
}

[data-theme="light"] {
  --bg: #ffffff;
  --surface: #f8fafc;
  --surface-hover: #f1f5f9;
  --text: #1e293b;
  --text-muted: #64748b;
  --border: #e2e8f0;
}
```

---

## 9. Package Dependencies

### `apps/web/package.json`
- next@15, react@19, react-dom@19
- next-auth@5 (beta), @auth/core
- @azure/msal-browser (Azure AD)
- zustand
- next-intl
- @tanstack/react-query (for orval hooks)
- next-themes
- lucide-react (icons)
- clsx, tailwind-merge
- @gilbertus/ui, @gilbertus/api-client, @gilbertus/rbac, @gilbertus/i18n (workspace)

### `packages/ui/package.json`
- react@19, react-dom@19 (peer)
- @radix-ui/react-dialog, @radix-ui/react-dropdown-menu, @radix-ui/react-tooltip
- cmdk (command palette)
- class-variance-authority
- lucide-react (peer)
- next-themes (peer)
- tailwind-merge, clsx

### `packages/api-client/package.json`
- orval (devDep)
- @tanstack/react-query

### `packages/rbac/package.json`
- react@19 (peer) — for hooks
- zustand (peer) — if needed for auth state

### `packages/i18n/package.json`
- next-intl

---

## 10. Key Decisions

1. **No Omnius TypeScript client generation yet** — Omnius OpenAPI spec not confirmed available. Manual types for P0 auth flow only; full Omnius client in P8.
2. **orval with react-query** — generates hooks like `useGetHealth()`, `usePostAsk()` etc. Standard pattern for data fetching.
3. **next-intl over next-i18next** — better App Router support, smaller bundle.
4. **cmdk for command palette** — same library powering shadcn/ui Command component.
5. **Sidebar state in Zustand + localStorage** — simple, no server component complications.
6. **Dark theme as default** — matches Sebastian's preference. Light theme available via toggle.
7. **No Tauri build in P0** — only placeholder config files. Full Tauri integration in P9.
