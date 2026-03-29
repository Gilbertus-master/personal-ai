# Part 0: Foundation — Scaffolding, API Client, Auth, Layout, i18n

## Cel
Zbuduj fundament aplikacji: monorepo, konfiguracja, design system, auth, nawigacja, i18n.
To jest PIERWSZY moduł — nie ma jeszcze żadnego kodu frontendowego.

## Tech Stack
- **pnpm** workspaces monorepo
- **Next.js 15** (App Router, TypeScript, React 19)
- **Tauri 2.0** (desktop shell — placeholder config, build later in P9)
- **Tailwind CSS v4** + **shadcn/ui** (design system)
- **assistant-ui** (AI chat components — install, use in P1)
- **Zustand** (state management)
- **next-intl** (i18n, Polish primary)
- **NextAuth.js** v5 (auth — Azure AD + API key)
- **orval** (OpenAPI → TypeScript client)

## Monorepo structure
```
/home/sebastian/personal-ai/frontend/
├── apps/
│   ├── web/                    # Next.js 15
│   │   ├── app/
│   │   │   ├── (auth)/         # login, callback
│   │   │   ├── (app)/          # authenticated routes (sidebar layout)
│   │   │   │   ├── layout.tsx  # sidebar + topbar shell
│   │   │   │   └── page.tsx    # redirect to /dashboard
│   │   │   ├── api/auth/       # NextAuth route
│   │   │   ├── layout.tsx      # root layout (providers, fonts, theme)
│   │   │   └── globals.css     # Tailwind + CSS variables
│   │   ├── lib/
│   │   │   ├── auth.ts         # NextAuth config
│   │   │   └── stores/         # Zustand stores
│   │   ├── middleware.ts        # auth middleware
│   │   ├── next.config.ts
│   │   ├── tailwind.config.ts
│   │   └── tsconfig.json
│   └── desktop/                # Tauri 2.0 (placeholder)
│       └── src-tauri/
│           ├── tauri.conf.json
│           └── Cargo.toml
├── packages/
│   ├── ui/                     # shadcn/ui + custom components
│   │   ├── src/components/
│   │   │   ├── sidebar.tsx
│   │   │   ├── topbar.tsx
│   │   │   ├── command-palette.tsx
│   │   │   ├── theme-provider.tsx
│   │   │   ├── rbac-gate.tsx
│   │   │   └── skeleton-card.tsx
│   │   └── package.json
│   ├── api-client/             # Generated TypeScript client
│   │   ├── scripts/generate.sh
│   │   ├── src/
│   │   │   ├── gilbertus.ts    # Generated from OpenAPI
│   │   │   ├── omnius.ts       # Generated
│   │   │   ├── base.ts         # Fetch wrapper with auth
│   │   │   └── index.ts
│   │   └── package.json
│   ├── rbac/                   # Permissions
│   │   ├── src/
│   │   │   ├── permissions.ts  # Role → permissions map (mirrors omnius/core/permissions.py)
│   │   │   ├── hooks.ts        # usePermissions(), useRole()
│   │   │   ├── navigation.ts   # Module list filtered by role
│   │   │   └── index.ts
│   │   └── package.json
│   └── i18n/                   # Translations
│       ├── messages/
│       │   ├── pl.json         # Polish (primary)
│       │   └── en.json         # English
│       └── package.json
├── pnpm-workspace.yaml
├── package.json
├── .eslintrc.js
└── tsconfig.base.json
```

## Design System
- **Dark theme** primary: `--bg: #0f1117`, `--surface: #1a1d27`, `--surface-hover: #252836`, `--accent: #6366f1`, `--accent-hover: #818cf8`, `--text: #e2e8f0`, `--text-muted: #94a3b8`, `--border: #2d3148`, `--error: #ef4444`, `--success: #22c55e`, `--warning: #f59e0b`
- **Font**: Inter (sans-serif)
- **Radius**: 8px default
- **Sidebar**: 260px wide, collapsible to 64px (icons only)
- **Command palette**: Cmd+K / Ctrl+K

## Auth flow
- **Sebastian (Gilbertus)**: Login with API key → role `gilbertus_admin`
- **Omnius users**: Azure AD OAuth → lookup user in `omnius_users` → get role
- **Session**: NextAuth JWT with `{userId, email, role, permissions[], tenant}`

## RBAC navigation (sidebar modules per role)
```typescript
const MODULES = {
  dashboard: { icon: 'LayoutDashboard', roles: ['*'] },
  chat:      { icon: 'MessageSquare',   roles: ['*'] },
  people:    { icon: 'Users',           roles: ['ceo', 'board', 'director'] },
  intelligence: { icon: 'Lightbulb',    roles: ['ceo', 'board'] },
  compliance:   { icon: 'Shield',       roles: ['ceo', 'board', 'director'] },
  market:    { icon: 'TrendingUp',      roles: ['ceo', 'board', 'director'] },
  finance:   { icon: 'DollarSign',      roles: ['ceo', 'board'] },
  process:   { icon: 'GitBranch',       roles: ['ceo', 'board', 'director'] },
  decisions: { icon: 'Scale',           roles: ['ceo'] },
  calendar:  { icon: 'Calendar',        roles: ['ceo', 'board', 'director', 'manager'] },
  documents: { icon: 'FileText',        roles: ['ceo', 'board', 'director'] },
  voice:     { icon: 'Mic',             roles: ['ceo', 'board'] },
  settings:  { icon: 'Settings',        roles: ['*'] },
  omnius:    { icon: 'Globe',           roles: ['gilbertus_admin'] },
}
```

## Backend API
- Gilbertus: http://127.0.0.1:8000 (X-API-Key header)
- Omnius REF: configurable URL (X-API-Key or Bearer JWT)
- Omnius REH: configurable URL

## Acceptance criteria
- `pnpm install` → zero errors
- `pnpm --filter web dev` → localhost:3000 shows login page
- After login → dark-themed app shell with sidebar navigation
- Sidebar modules filtered by role
- Cmd+K opens command palette
- Polish language by default
- API client generates typed functions from OpenAPI spec
- `pnpm --filter web build` → zero errors
