# Part 9: Desktop Build & Polish — Architecture Plan

## 1. Component Tree

```
<App>
  <ErrorBoundary fallback={<GlobalError />}>           # NEW: global catch
    <ThemeProvider>
      <OfflineProvider>                                 # NEW: network state context
        <QueryClientProvider>
          <Layout>
            <Sidebar />                                 # EXISTING (animation polish)
            <main>
              <Topbar>
                <OfflineBanner />                       # NEW: yellow banner when offline
              </Topbar>
              <AnimatedOutlet>                          # NEW: page transition wrapper
                {/* Per-route content */}
                <Suspense fallback={<PageSkeleton />}>  # NEW: consistent skeletons
                  <Page />
                </Suspense>
              </AnimatedOutlet>
            </main>
          </Layout>
        </QueryClientProvider>
      </OfflineProvider>
    </ThemeProvider>
  </ErrorBoundary>
</App>
```

### New Shared Components
```
<ErrorFallback error resetErrorBoundary moduleName? />   # Retry button + error display
<EmptyState icon title description action? />            # "No data" placeholder
<PageSkeleton variant="card|table|list|detail" rows? />  # Configurable skeleton
<OfflineBanner />                                        # "You're offline" top banner
<ButtonLoading loading children />                       # Button with spinner
<AnimatedPage>                                           # CSS transition wrapper
```

## 2. File Tree

### Phase 1: Polish Foundation
```
frontend/
  packages/ui/src/components/
    error-fallback.tsx                # Error fallback UI with retry
    empty-state.tsx                   # Generic empty state component
    page-skeleton.tsx                 # Configurable page skeleton loader
    offline-banner.tsx                # Offline indicator banner
    button-loading.tsx                # Button with loading spinner
    animated-page.tsx                 # CSS page transition wrapper
  apps/web/
    app/(app)/
      error.tsx                       # Root error boundary
      dashboard/error.tsx             # Dashboard error boundary
      chat/error.tsx                  # Chat error boundary
      chat/[id]/error.tsx             # Chat detail error boundary
      intelligence/error.tsx          # Intelligence error boundary
      people/error.tsx                # People error boundary
      people/[slug]/error.tsx         # Person detail error boundary
      compliance/error.tsx            # Compliance error boundary
      market/error.tsx                # Market error boundary
      finance/error.tsx               # Finance error boundary
      process/error.tsx               # Process error boundary
      decisions/error.tsx             # Decisions error boundary
      documents/error.tsx             # Documents error boundary
      calendar/error.tsx              # Calendar error boundary
      admin/error.tsx                 # Admin error boundary
      settings/error.tsx              # Settings error boundary
    lib/hooks/
      use-online-status.ts            # Network status hook (navigator.onLine + events)
    lib/providers/
      offline-provider.tsx            # OfflineProvider context
```

### Phase 2: Animations & Loading Polish
```
frontend/
  packages/ui/src/
    lib/animations.css                # Keyframe definitions (@keyframes fadeIn, slideIn, etc.)
  apps/web/
    app/(app)/
      template.tsx                    # AnimatedPage wrapper for route transitions
      dashboard/loading.tsx           # Dashboard skeleton
      chat/loading.tsx                # Chat skeleton
      intelligence/loading.tsx        # Intelligence skeleton
      people/loading.tsx              # People skeleton
      compliance/loading.tsx          # Compliance skeleton
      market/loading.tsx              # Market skeleton
      finance/loading.tsx             # Finance skeleton
      process/loading.tsx             # Process skeleton
      decisions/loading.tsx           # Decisions skeleton
      documents/loading.tsx           # Documents skeleton
      calendar/loading.tsx            # Calendar skeleton
      admin/loading.tsx               # Admin skeleton
      settings/loading.tsx            # Settings skeleton
```

### Phase 3: Tauri Desktop
```
frontend/
  apps/desktop/
    package.json                      # UPDATED: add @tauri-apps/cli, scripts
    src-tauri/
      tauri.conf.json                 # UPDATED: plugins, security, bundle config
      Cargo.toml                      # UPDATED: add plugin dependencies
      src/
        main.rs                       # UPDATED: plugin registration, tray, deep links
        tray.rs                       # System tray setup, menu, event handlers
        commands.rs                   # Tauri commands (get_platform, check_update, etc.)
      capabilities/
        default.json                  # Tauri v2 capability permissions
      icons/                          # App icons (.ico, .png, .icns)
        icon.ico
        icon.png
        32x32.png
        128x128.png
        128x128@2x.png
        icon.icns
  apps/web/
    next.config.ts                    # UPDATED: output: 'export' for Tauri
    lib/hooks/
      use-tauri.ts                    # Tauri detection + IPC bridge hook
    lib/providers/
      desktop-provider.tsx            # Desktop-specific context (tray state, deep links)
```

### Phase 4: Offline Support
```
frontend/
  apps/web/
    public/
      sw.js                           # Service worker (cache-first for assets)
    lib/
      offline/
        idb.ts                        # IndexedDB wrapper (open, get, put, delete)
        cache-manager.ts              # Cache strategies per data type
        message-queue.ts              # Offline message queue (queue, flush, retry)
        sw-register.ts                # Service worker registration helper
    lib/hooks/
      use-offline-cache.ts            # Hook: read from IDB, fallback to API
      use-message-queue.ts            # Hook: queue messages offline, flush online
    lib/stores/
      offline-store.ts                # Zustand: queue count, last online, sync status
```

### Phase 5: Build & Verification
```
frontend/
  scripts/
    verify-build.sh                   # pnpm build + tsc --noEmit + lint check
    e2e-checklist.md                  # Manual E2E test checklist
  apps/desktop/
    scripts/
      build-all.sh                    # Build for all platforms
```

## 3. API Integration Map

### Offline Banner / Provider
| Component | Endpoint | Cache Strategy |
|-----------|----------|---------------|
| `OfflineProvider` | `GET /health` | Poll every 30s, no cache |
| `OfflineBanner` | — | Reads from OfflineProvider context |

### System Tray (Desktop)
| Tray Action | Endpoint | Trigger |
|-------------|----------|---------|
| Alert badge count | `GET /alerts?active_only=true` | Poll every 60s |
| "Today's Brief" | `GET /brief/today` | User click |
| "New Chat" | — | Navigate to `/chat` |
| "Voice" | — | Navigate to `/chat` + activate voice |
| "Status" | `GET /status` | Hover tooltip |

### Deep Links
| Protocol | Route | Endpoint |
|----------|-------|----------|
| `gilbertus://ask?q=...` | `/chat?q={q}` | `POST /ask` |
| `gilbertus://brief` | `/dashboard` | `GET /brief/today` |
| `gilbertus://person/{slug}` | `/people/{slug}` | `GET /people/{slug}` |
| `gilbertus://chat/{id}` | `/chat/{id}` | `GET /conversations/{id}` |

### Offline Cache Priorities
| Data Type | Cache Strategy | TTL | IDB Store |
|-----------|---------------|-----|-----------|
| Morning brief | Cache-first, refresh bg | 4h | `briefs` |
| Dashboard stats | Cache-first, refresh bg | 15m | `dashboard` |
| Conversations list | Cache-first, refresh bg | 5m | `conversations` |
| Last 5 conversation messages | Cache-first, refresh bg | 5m | `messages` |
| People directory | Cache-first, refresh bg | 1h | `people` |
| Chat messages (offline) | Queue in IDB, flush on reconnect | — | `outbox` |

## 4. RBAC Per View

No new RBAC requirements for Part 9. All new components are infrastructure-level:
- Error boundaries: visible to all roles
- Skeleton loaders: visible to all roles
- Empty states: visible to all roles (content gated by existing page RBAC)
- Offline banner: visible to all roles
- System tray: inherits page-level RBAC (opens web views)
- Deep links: route to pages that already have RBAC gates

## 5. State Management

### New Zustand Store: `offline-store.ts`
```typescript
interface OfflineStore {
  // State
  isOnline: boolean;
  lastOnlineAt: string | null;
  queuedMessageCount: number;
  syncStatus: 'idle' | 'syncing' | 'error';

  // Actions
  setOnline: (online: boolean) => void;
  incrementQueue: () => void;
  decrementQueue: () => void;
  setSyncStatus: (status: 'idle' | 'syncing' | 'error') => void;
}
```
Persisted to localStorage via Zustand `persist` middleware (key: `gilbertus-offline`).

### Existing Store Modifications
- **`sidebar-store.ts`**: Add `animateCollapse: boolean` (default true) for sidebar animation toggle
- **`dashboard-store.ts`**: No changes (already has refresh logic)

### Desktop-Specific State (Context, not Zustand — ephemeral)
```typescript
interface DesktopContext {
  isTauri: boolean;         // window.__TAURI__ detection
  platform: 'windows' | 'macos' | 'linux' | null;
  trayAlertCount: number;
  deepLinkPending: DeepLinkAction | null;
}
```

## 6. UX Flows

### Flow 1: Page Load with Error
```
User navigates to /intelligence
  → loading.tsx renders IntelligenceSkeleton (grid of SkeletonCards)
  → React Query fetches data
  → IF error: error.tsx catches → renders ErrorFallback
    → User clicks "Retry" → resetErrorBoundary() → re-renders page
    → User clicks "Go to Dashboard" → router.push('/dashboard')
  → IF success: page renders normally, skeleton fades out
```

### Flow 2: Offline Detection
```
API /health poll fails (or navigator.onLine → false)
  → OfflineProvider sets isOnline=false
  → OfflineBanner slides down from top: "Jestes offline. Dane mogla byc nieaktualne."
  → React Query queries use staleTime: Infinity (don't refetch)
  → IDB cached data serves reads
  → User sends chat message → queued in IDB outbox → badge shows "1 w kolejce"
  → Connection restored:
    → OfflineBanner slides away
    → message-queue flushes outbox → sends queued messages
    → React Query invalidates all queries → fresh data
```

### Flow 3: System Tray (Desktop)
```
App starts → system tray icon appears (Gilbertus logo)
  → Every 60s: poll /alerts?active_only=true → update badge count
  → Right-click tray:
    ├── "Dzisiejszy Brief" → open window, navigate to /dashboard
    ├── "Nowy Chat" → open window, navigate to /chat
    ├── "Asystent Glosowy" → open window, navigate to /chat + voice mode
    ├── separator
    ├── "Status: Online (3 alerty)" → disabled, info only
    ├── separator
    └── "Zamknij" → quit app
  → New critical alert → native OS notification toast
    → Click notification → open window, navigate to /dashboard
```

### Flow 4: Deep Link
```
User clicks gilbertus://ask?q=jaki%20jest%20status%20REH
  → OS routes to Tauri app
  → Tauri deep-link plugin fires event
  → desktop-provider parses URL → DeepLinkAction { action: 'ask', params: { q: '...' } }
  → Router navigates to /chat?q=jaki+jest+status+REH
  → Chat page auto-submits question
```

### Flow 5: Empty State
```
User navigates to /decisions (no decisions created yet)
  → Page renders, API returns empty array
  → EmptyState renders:
    - Icon: Scale (from lucide)
    - Title: "Brak decyzji"
    - Description: "Nie masz jeszcze zadnych decyzji do przegladania."
    - Action button: "Utworz pierwsza decyzje" → opens create dialog
```

### Flow 6: Page Transition
```
User clicks sidebar link (e.g., Dashboard → Intelligence)
  → Current page fades out (opacity 1→0, 150ms ease-out)
  → New page fades in (opacity 0→1, 200ms ease-in)
  → Implemented via template.tsx with CSS transitions
  → No JS animation library needed
```

## 7. CSS Animation Definitions

```css
/* animations.css — imported in globals.css */

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes slideInLeft {
  from { opacity: 0; transform: translateX(-8px); }
  to { opacity: 1; transform: translateX(0); }
}

@keyframes slideInRight {
  from { opacity: 0; transform: translateX(8px); }
  to { opacity: 1; transform: translateX(0); }
}

@keyframes slideDown {
  from { opacity: 0; transform: translateY(-100%); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes scaleIn {
  from { opacity: 0; transform: scale(0.95); }
  to { opacity: 1; transform: scale(1); }
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Utility classes */
.animate-fade-in { animation: fadeIn 200ms ease-out; }
.animate-slide-left { animation: slideInLeft 200ms ease-out; }
.animate-slide-right { animation: slideInRight 200ms ease-out; }
.animate-slide-down { animation: slideDown 300ms ease-out; }
.animate-scale-in { animation: scaleIn 200ms ease-out; }
```

## 8. Tauri v2 Plugin Architecture

### Plugins Required
| Plugin | Crate | Purpose |
|--------|-------|---------|
| `tauri-plugin-notification` | `tauri-plugin-notification` | Native OS notifications |
| `tauri-plugin-deep-link` | `tauri-plugin-deep-link` | `gilbertus://` protocol |
| `tauri-plugin-updater` | `tauri-plugin-updater` | Auto-update checks |
| `tauri-plugin-shell` | `tauri-plugin-shell` | Open external URLs |

### System Tray (Built-in Tauri v2)
Tauri v2 has built-in tray support — no plugin needed. Configure via `tray` in tauri.conf.json + Rust `SystemTray` API.

### Capabilities (Tauri v2 Security)
```json
// capabilities/default.json
{
  "identifier": "default",
  "description": "Default capability for Gilbertus",
  "windows": ["main"],
  "permissions": [
    "core:default",
    "notification:default",
    "notification:allow-notify",
    "deep-link:default",
    "updater:default",
    "shell:allow-open"
  ]
}
```

### Build Configuration
```json
// tauri.conf.json additions
{
  "bundle": {
    "active": true,
    "targets": ["msi", "dmg", "appimage"],
    "icon": ["icons/32x32.png", "icons/128x128.png", "icons/128x128@2x.png", "icons/icon.icns", "icons/icon.ico"],
    "windows": {
      "wix": { "language": "pl-PL" }
    }
  },
  "plugins": {
    "deep-link": {
      "desktop": { "schemes": ["gilbertus"] }
    },
    "updater": {
      "endpoints": ["https://releases.gilbertus.app/{{target}}/{{arch}}/{{current_version}}"],
      "pubkey": ""
    }
  }
}
```

### Next.js Static Export for Tauri
```typescript
// next.config.ts — add output: 'export'
const nextConfig: NextConfig = {
  output: 'export',
  // ... existing config
};
```
**Note**: This disables server-side features (API routes, middleware, ISR). All data fetching must be client-side (already the case — React Query + API client).

## 9. Service Worker Strategy

### Cache Strategies
| Resource Type | Strategy | Max Age |
|---------------|----------|---------|
| Static assets (JS, CSS, fonts) | Cache-first | 7 days |
| Images | Cache-first | 30 days |
| API responses (`/health`) | Network-only | — |
| API responses (`/brief/*`, `/status`) | Network-first, fallback cache | 4h |
| API responses (all other) | Network-first, fallback cache | 15m |

### Service Worker Scope
- Registered from `sw-register.ts` in root layout
- Scope: `/` (all routes)
- Skip waiting + claim clients on update (immediate activation)

## 10. IndexedDB Schema

```typescript
// Database: 'gilbertus-offline', version 1
const stores = {
  briefs: { keyPath: 'date' },          // Morning briefs by date
  dashboard: { keyPath: 'key' },         // Dashboard widgets data
  conversations: { keyPath: 'id' },      // Conversation list
  messages: { keyPath: 'id', indexes: [  // Chat messages
    { name: 'by-conversation', keyPath: 'conversationId' }
  ]},
  people: { keyPath: 'id' },             // People directory
  outbox: { keyPath: 'id', indexes: [    // Queued messages
    { name: 'by-created', keyPath: 'createdAt' }
  ]},
  meta: { keyPath: 'key' },             // Cache timestamps
};
```

## 11. Build Verification Pipeline

```bash
#!/bin/bash
# verify-build.sh

set -e

echo "=== TypeScript Check ==="
pnpm --filter @gilbertus/web exec tsc --noEmit

echo "=== ESLint ==="
pnpm --filter @gilbertus/web lint

echo "=== Build Web ==="
pnpm --filter @gilbertus/web build

echo "=== Build Desktop ==="
cd apps/desktop && pnpm tauri build

echo "=== All checks passed ==="
```

## 12. Key Architecture Decisions

1. **No framer-motion**: CSS keyframe animations are sufficient for fade/slide transitions. Avoids 30KB+ bundle addition for simple effects.
2. **Next.js `output: 'export'`**: Required for Tauri. All rendering is already client-side via React Query, so no functionality lost.
3. **Service Worker**: Hand-written (not next-pwa) for precise control over cache strategies. Minimal — only caches assets and select API responses.
4. **IndexedDB via raw API wrapper**: No idb library needed — 6 stores with simple get/put operations. Keep it lightweight.
5. **System tray in Rust**: All tray logic in `tray.rs`. Frontend communicates via Tauri events/commands, not direct tray manipulation.
6. **Error boundaries**: Next.js `error.tsx` convention — one per route group. All share the same `ErrorFallback` component from `@gilbertus/ui`.
7. **Loading states**: Next.js `loading.tsx` convention with `PageSkeleton` variants per module.
8. **Offline store**: Zustand (persisted) for UI state, IndexedDB for data cache. Clear separation.
