# Part 9: Desktop Build & Polish — Discovery Report

## 1. Current State Assessment

### Tauri Desktop App (`apps/desktop/`)
- **Status**: Minimal scaffold — `tauri.conf.json` + bare `main.rs`
- **Config**: Tauri v2, identifier `com.gilbertus.app`, window 1280x800 (min 800x600)
- **Frontend dist**: Points to `../../apps/web/.next` (Next.js static export)
- **Dev URL**: `http://localhost:3000`
- **Missing**: system tray, plugins, deep links, auto-updater, native notifications, build scripts, icons

### Cargo.toml
```toml
[dependencies]
tauri = { version = "2", features = [] }
[build-dependencies]
tauri-build = { version = "2" }
```
No plugins enabled yet.

### Desktop package.json
Only has `"tauri": "cargo tauri"` script. No Tauri CLI dependency.

---

## 2. API Endpoints Relevant to Desktop / Polish

### Health & Status (system tray, offline detection)
| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| GET | `/health` | Simple health check | Public |
| GET | `/status` | Full system dashboard (DB stats, services, crons) | API Key |
| GET | `/version` | API version info | Public |
| GET | `/observability/dashboard` | Latency p50/p95, error rate, costs | API Key |

### Alerts & Notifications (system tray badge, native notifications)
| Method | Path | Purpose | Params |
|--------|------|---------|--------|
| GET | `/alerts` | Proactive alerts | `active_only`, `alert_type`, `severity`, `limit` |
| GET | `/alerts/guardian` | Guardian 3-tier alerts | `tier`, `limit=20` |
| POST | `/alerts/guardian/{id}/acknowledge` | Ack single alert | — |
| POST | `/alerts/guardian/acknowledge-all` | Bulk ack | `category` |
| GET | `/alerts/guardian/stats` | Alert stats (7 days) | — |
| GET | `/market/alerts` | Market alerts | — |
| GET | `/sentiment-alerts` | People sentiment alerts | — |

### Brief (quick tray action)
| Method | Path | Purpose | Params |
|--------|------|---------|--------|
| GET | `/brief/today` | Morning brief | `force`, `days`, `date` |

### Voice (quick tray action)
| Method | Path | Purpose |
|--------|------|---------|
| WS | `/voice/ws` | Bidirectional voice dialog |
| POST | `/voice/ask` | Audio → transcribe → answer → TTS |
| POST | `/voice/transcribe` | Audio → text |
| GET | `/voice/health` | Voice pipeline status |

### Chat (deep link: `gilbertus://ask?q=...`)
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/ask` | Core Q&A endpoint |
| GET | `/conversations` | List conversations |
| POST | `/conversations` | Create conversation |

---

## 3. RBAC Rules

### Frontend RBAC Package (`packages/rbac/`)
| Role | Level | Key Access |
|------|-------|------------|
| `gilbertus_admin` | 99 | Everything (all classifications, all modules) |
| `operator` | 70 | Admin, system tools (no classified data) |
| `ceo` | 60 | All data incl. ceo_only, all intelligence |
| `board` | 50 | Confidential + below, most modules |
| `director` | 40 | Internal + below |
| `manager` | 30 | Internal + below |
| `specialist` | 20 | Public + personal only |

### Navigation Module Visibility (from `packages/rbac/src/navigation.ts`)
- `dashboard`, `chat`, `settings`: All roles (`*`)
- `intelligence`, `market`, `finance`, `decisions`: CEO + Board
- `compliance`: CEO + Board + Director
- `process`: CEO + Board + Director + Manager
- `admin`: Admin + Operator only
- `people`, `documents`, `calendar`: All roles

### Backend Auth
- Single API key auth (env-based), no per-user RBAC enforcement at endpoint level
- Trusted IPs (localhost) bypass rate limits
- Desktop app connects to localhost → trusted IP applies

---

## 4. Existing Patterns to Follow

### Component Architecture
- **Monorepo**: `packages/ui` (131 components), `packages/api-client`, `packages/rbac`, `packages/i18n`
- **Naming**: PascalCase exports, `{Name}Props` interfaces
- **Styling**: Tailwind CSS with CSS variable theming (`--bg`, `--surface`, `--text`, etc.)
- **UI primitives**: Radix UI (dialog, dropdown, separator, avatar, tooltip) + cmdk

### API Client Pattern (`packages/api-client/src/base.ts`)
```typescript
customFetch<T>({ url, method, params?, body?, signal? }): Promise<T>
```
- Auto-injects `X-API-Key` header
- Handles 401 → clear key → redirect to login
- Base URL from `NEXT_PUBLIC_GILBERTUS_API_URL`

### State Management
- **Zustand** with `persist` middleware → localStorage
- Stores: `dashboard-store`, `chat-store`, `sidebar-store`, `command-palette-store` + 26 more
- Pattern: `create<T>()(persist((set, get) => ({...}), { name: 'gilbertus-xxx' }))`

### Data Fetching
- **TanStack React Query v5** with 60s default staleTime
- Custom hooks per domain in `apps/web/lib/hooks/`

### Theme
- `next-themes` with class-based dark mode (default: dark)
- CSS variables in `globals.css` for `:root` and `.dark`

### i18n
- `next-intl` — Polish (default) + English
- Messages in `packages/i18n/messages/{pl,en}.json`

### Loading States
- `SkeletonCard` component (`animate-pulse rounded-lg bg-muted`)
- Per-component skeleton patterns (dashboard sections, message bubbles)
- React Query loading/error states

---

## 5. What's Missing / Gaps

### No Error Boundaries
- No `error.tsx` files in any route segment
- No React ErrorBoundary components
- No per-page error catch with retry

### No Service Worker
- No `sw.ts`, `sw.js`, or service worker registration
- No offline caching strategy

### No IndexedDB
- No IndexedDB usage for offline data cache
- Only localStorage via Zustand persist

### No Animations Library
- Only basic Tailwind transitions (`animate-pulse`, `transition-colors`, `transition-[width]`)
- No framer-motion or CSS animation system

### No Testing Framework
- No Jest, Vitest, Playwright, or Cypress
- No test files anywhere
- No test scripts in package.json

### Tauri Desktop — Bare Minimum
- No plugins (tray, updater, deep-link, notification, shell)
- No `tauri dev`/`tauri build` scripts properly configured
- No app icons
- No system tray config
- No deep link protocol handler
- No Tauri CLI as devDependency

### No Empty State Components
- No consistent "no data" illustrations or messages

### No Keyboard Shortcut Documentation
- Command palette exists but no shortcut reference panel

---

## 6. Data Types / Interfaces Needed

### Desktop-Specific
```typescript
// System tray state
interface TrayState {
  unreadAlerts: number;
  lastBriefTime: string | null;
  isOnline: boolean;
}

// Offline queue
interface QueuedMessage {
  id: string;
  type: 'chat' | 'voice';
  payload: unknown;
  createdAt: string;
  retries: number;
}

// Deep link
interface DeepLinkAction {
  protocol: 'gilbertus';
  action: 'ask' | 'brief' | 'chat' | 'person';
  params: Record<string, string>;
}
```

### Polish Components
```typescript
// Error boundary
interface ErrorFallbackProps {
  error: Error;
  resetErrorBoundary: () => void;
  moduleName?: string;
}

// Empty state
interface EmptyStateProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  action?: { label: string; onClick: () => void };
}

// Offline indicator
interface OfflineState {
  isOnline: boolean;
  lastOnlineAt: string | null;
  queuedMessages: number;
}

// Skeleton config per page
interface SkeletonConfig {
  rows?: number;
  columns?: number;
  variant: 'card' | 'table' | 'list' | 'detail';
}
```

### Existing Types (from api-client, reuse)
- `MorningBriefResponse` — brief endpoint
- `Alert`, `GuardianAlert` — alert endpoints
- `SystemStatus` — status endpoint
- `Conversation`, `Message` — chat endpoints

---

## 7. Complexity Estimates

### Tauri Desktop
| Feature | Complexity | Notes |
|---------|-----------|-------|
| Build config (window, title, menu) | Simple | Extend existing tauri.conf.json |
| System tray (icon, quick actions, badge) | Medium | Tauri tray plugin + Rust event handlers |
| Auto-update | Medium | Tauri updater plugin + update server needed |
| Deep links (`gilbertus://`) | Medium | Tauri deep-link plugin + OS registration |
| Native notifications | Simple | Tauri notification plugin |
| Build scripts (.msi/.dmg/.AppImage) | Medium | CI pipeline + code signing |

### Offline Support
| Feature | Complexity | Notes |
|---------|-----------|-------|
| IndexedDB cache (brief, dashboard, convos) | Medium | New layer, need idb wrapper |
| Service Worker | Medium | next-pwa or custom SW, cache strategies |
| Offline indicator banner | Simple | Network status hook + UI component |
| Offline message queue | Medium | Queue in IndexedDB, sync on reconnect |

### Polish & UX
| Feature | Complexity | Notes |
|---------|-----------|-------|
| Page transition animations | Simple | CSS transitions or framer-motion |
| Sidebar collapse animation | Simple | Already has basic transition |
| Card hover animations | Simple | Tailwind hover utilities |
| Skeleton loaders (consistent) | Simple | Extend SkeletonCard, per-page configs |
| Error boundaries (per page) | Simple | Next.js error.tsx convention |
| Empty states | Simple | New component + per-module instances |
| Responsive polish | Medium | Audit all 14 pages for breakpoints |
| Keyboard shortcuts doc | Simple | Settings page panel |
| Button spinners / progress bars | Simple | Shared component |

### Testing / Build Gates
| Feature | Complexity | Notes |
|---------|-----------|-------|
| Build gate (`pnpm build` zero errors) | Simple | Script + CI check |
| Lint zero warnings | Simple | ESLint config + fix existing |
| TypeScript `tsc --noEmit` | Simple | Already configured |
| Manual E2E checklist | Simple | Documentation only |

---

## 8. Implementation Priority

### Phase 1: Polish Foundation (pre-desktop)
1. Error boundaries (`error.tsx` per route group)
2. Consistent skeleton loaders
3. Empty state component
4. Offline indicator hook + banner
5. Button loading states

### Phase 2: Animations
1. Page transitions (CSS or framer-motion)
2. Sidebar animation polish
3. Card hover effects
4. Skeleton fade-in

### Phase 3: Tauri Desktop
1. Add Tauri plugins (tray, notification, deep-link, updater)
2. System tray with quick actions
3. Deep link protocol handler
4. Native notifications bridged from alert polling
5. Build scripts + icons

### Phase 4: Offline
1. Service Worker for static assets
2. IndexedDB wrapper for data cache
3. Offline message queue
4. Sync-on-reconnect logic

### Phase 5: Build Gates
1. `pnpm build` verification
2. Lint + typecheck CI
3. Manual E2E checklist document

---

## 9. Key Architecture Decisions

1. **Tauri v2** is already chosen — use plugin system for tray/notifications/deep-links
2. **Next.js static export** needed for Tauri (no server-side rendering in desktop)
3. **Offline-first**: IndexedDB for data, Service Worker for assets, Zustand for UI state
4. **Animations**: Recommend framer-motion for page transitions (already React ecosystem), CSS for micro-interactions
5. **Error boundaries**: Use Next.js `error.tsx` convention (built-in, no extra lib)
6. **Testing**: No framework exists — out of scope for Part 9 implementation (manual E2E checklist instead)
