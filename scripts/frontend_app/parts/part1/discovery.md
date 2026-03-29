# Part 1: Chat Core — Discovery Report

**Date:** 2026-03-29
**Module:** Multi-conversation AI Assistant (Chat Core)

---

## 1. API Endpoint Inventory

### Primary Endpoints

| Method | Path | Purpose | Params | Response |
|--------|------|---------|--------|----------|
| `POST` | `/ask` | Main query endpoint | `query`, `top_k`, `source_types[]`, `source_names[]`, `date_from`, `date_to`, `mode`, `include_sources`, `answer_style`, `answer_length`, `allow_quotes`, `debug`, `channel`, `session_id` | `{answer, sources[], matches[], meta{}, run_id}` |
| `GET` | `/conversation/windows` | List active conversations (24h) | none | `[{channel_key, message_count, total_chars, last_active, created_at}]` |

### Supporting Endpoints (useful for quick actions)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/brief/today` | Morning brief |
| `POST` | `/timeline` | Event timeline |
| `GET` | `/meeting-prep` | Meeting preparation |
| `GET` | `/alerts` | Active alerts |
| `GET` | `/commitments` | Commitment list |
| `POST` | `/summary/generate` | Generate summary |

### Relevant Voice Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/voice/transcribe` | Audio → text (for future voice input) |
| `POST` | `/voice/tts` | Text → audio (for future voice output) |

---

## 2. Request/Response Shapes

### AskRequest (POST /ask body)
```typescript
interface AskRequest {
  query: string              // max 4000 chars, required
  top_k?: number             // 1-50, default 8
  source_types?: string[]    // email|teams|whatsapp|chatgpt|plaud|document|calendar|whatsapp_live|pdf
  source_names?: string[]    // filter specific source names
  date_from?: string         // YYYY-MM-DD
  date_to?: string           // YYYY-MM-DD
  mode?: string              // default "auto"
  include_sources?: boolean  // default false
  answer_style?: string      // default "auto"
  answer_length?: string     // short|medium|long|auto, default "long"
  allow_quotes?: boolean     // default true
  debug?: boolean            // default false — includes sources[] and matches[]
  channel?: string           // "whatsapp"|"voice"|"api"|"web" etc.
  session_id?: string        // conversation session key
}
```

### AskResponse
```typescript
interface AskResponse {
  answer: string
  sources?: SourceItem[]     // only when debug=true
  matches?: MatchItem[]      // only when debug=true
  meta: {
    question_type: string
    analysis_depth: string
    used_fallback: boolean
    retrieved_count: number
    normalized_query: string
    date_from: string
    date_to: string
    answer_style: string
    answer_length: string
    channel: string
    debug: boolean
    latency_ms: number
    cache_hit: boolean
  }
  run_id?: number
}

interface SourceItem {
  document_id: number
  title: string
  source_type: string
  source_name: string
  created_at: string
}

interface MatchItem {
  chunk_id: number
  document_id: number
  score: float
  source_type: string
  source_name: string
  title: string
  created_at: string
  text: string
}
```

### ConversationWindow (GET /conversation/windows)
```typescript
interface ConversationWindow {
  channel_key: string       // e.g. "web:conv-uuid"
  message_count: number
  total_chars: number
  last_active: string       // ISO datetime
  created_at: string        // ISO datetime
}
```

---

## 3. Conversation Store (Backend)

**File:** `app/db/conversation_store.py`

- **Sliding window:** MAX_MESSAGES=20, MAX_CHARS=8000, CONTEXT_MSGS=10 (for prompt)
- **Storage:** PostgreSQL `conversation_windows` table (JSONB messages column)
- **Channel key format:** `"{channel}:{session_id}"` — e.g. `"web:conv-uuid-123"`
- **Message format in DB:** `{role: "user"|"assistant", text: string, ts: ISO}`
- **Auto-cleanup:** Windows inactive >24h are cleaned up
- **Upsert:** INSERT ON CONFLICT updates existing window

**Key insight:** The backend already supports multi-session conversations via `channel` + `session_id`. For the frontend, we'll use `channel="web"` and generate a UUID per conversation as `session_id`.

---

## 4. RBAC Rules

### Roles (7 levels)

| Role | Level | Scope |
|------|-------|-------|
| `gilbertus_admin` | 99 | Global — bypasses all checks |
| `operator` | 70 | Technical — NO business data |
| `ceo` | 60 | Global — full access |
| `board` | 50 | Global — no ceo_only |
| `director` | 40 | Department scoped |
| `manager` | 30 | Team scoped |
| `specialist` | 20 | Own data only |

### Classification Access

| Role | Can See |
|------|---------|
| `ceo` / `admin` | public, internal, confidential, ceo_only, personal |
| `board` | public, internal, confidential, personal |
| `director` / `manager` | public, internal, personal |
| `specialist` | public, personal |
| `operator` | NONE (no business data) |

### Chat-Specific RBAC Rules
1. **All authenticated users** can access `/chat` — it's in navigation with `roles: ['*']`
2. **Source filtering** is backend-enforced via classification + ownership + department
3. **No frontend source_type filtering needed** — backend handles it based on user identity
4. **answer_length defaults:**
   - CEO/admin: `"long"` (default)
   - Specialist: should default to `"medium"` (frontend UX decision)

### Omnius Auth on `/ask`
The Gilbertus `/ask` endpoint uses simple API key auth (no per-user RBAC). But the Omnius `/ask` endpoint (`omnius/api/routes/ask.py`) does full RBAC:
- Classification filtering per role
- Department filtering for director/manager/specialist
- Personal doc ownership checks

**Decision needed:** Chat module should use Omnius `/ask` when user is logged in via Omnius auth (Azure AD), and Gilbertus `/ask` for API key auth (admin mode).

---

## 5. Existing Frontend Patterns

### Project Structure
```
frontend/
├── pnpm-workspace.yaml
├── apps/web/                    # Next.js 16 app
│   ├── app/
│   │   ├── (app)/               # Protected routes (sidebar + topbar)
│   │   │   ├── layout.tsx       # Sidebar, Topbar, CommandPalette
│   │   │   └── page.tsx         # Redirects to /dashboard
│   │   ├── (auth)/login/        # Login page
│   │   └── layout.tsx           # Root layout (Providers)
│   ├── lib/
│   │   ├── auth.ts              # NextAuth v5 config
│   │   └── stores/              # Zustand stores
│   └── components/
│       └── providers.tsx        # SessionProvider + QueryClient + ThemeProvider
├── packages/
│   ├── api-client/              # Orval-generated React Query hooks
│   │   └── src/base.ts          # customFetch() with API key management
│   ├── rbac/                    # Roles, permissions, navigation
│   ├── ui/                      # Shared components (Sidebar, Topbar, etc.)
│   └── i18n/                    # next-intl (not yet wired)
```

### API Client Pattern
- **Orval** generates React Query hooks from OpenAPI spec
- **Custom fetch wrapper** (`packages/api-client/src/base.ts`):
  - Base URL from `NEXT_PUBLIC_GILBERTUS_API_URL`
  - API key via `X-API-Key` header
  - 401 → clear key + redirect to `/login`
- **Usage:** Import generated hooks, or use `customFetch()` directly for custom calls

### State Management Pattern
- **Zustand** with simple interfaces
- **Persistence:** `zustand/middleware` persist to localStorage
- **Naming:** `use{Name}Store` with `{Name}Store` interface
- **Location:** `apps/web/lib/stores/`

### Component Patterns
- **shadcn/ui philosophy** — custom components, not pre-built
- **`cn()` utility** for Tailwind class merging
- **`'use client'`** for all interactive components
- **Props:** `interface ComponentNameProps`
- **RbacGate** for role-based rendering

### Styling
- **Tailwind CSS 4** with CSS variables for theming
- **Dark/light mode** via `.dark` class (next-themes)
- **Color vars:** `--bg`, `--surface`, `--surface-hover`, `--border`, `--text`, `--text-secondary`, `--accent`
- **No external CSS** in components — all inline Tailwind

### Auth
- **NextAuth v5** with API key + Azure AD providers
- **Session:** Augmented with `role`, `roleLevel`, `permissions[]`, `tenant`, `authType`
- **Hooks:** `useRole()`, `usePermissions()`, `useClassifications()`
- **Middleware:** Protects all routes except `/login`, `/api/auth`

---

## 6. Data Types/Interfaces Needed

```typescript
// Conversation management
interface Conversation {
  id: string                 // UUID
  title: string              // Auto-generated or user-set
  channelKey: string         // "web:{id}"
  messageCount: number
  lastActive: string
  createdAt: string
}

interface Message {
  id: string                 // client-generated UUID
  role: 'user' | 'assistant'
  content: string
  sources?: SourceItem[]
  matches?: MatchItem[]
  meta?: AskResponseMeta
  attachments?: Attachment[]
  timestamp: string
  isStreaming?: boolean
}

interface Attachment {
  id: string
  name: string
  type: string              // mime type
  size: number
  preview?: string          // base64 thumbnail or text preview
  file?: File               // client-side only
}

// Quick actions
interface QuickAction {
  command: string            // /brief, /timeline, /meeting-prep
  label: string
  description: string
  endpoint: string
  method: 'GET' | 'POST'
}

// Source reference display
interface SourceReference {
  documentId: number
  title: string
  sourceType: 'email' | 'teams' | 'whatsapp' | 'document' | 'plaud' | 'calendar' | 'chatgpt' | 'pdf'
  sourceName: string
  createdAt: string
  relevanceScore?: number
}
```

---

## 7. Backend Gaps

### Critical Gaps

| Gap | Impact | Workaround |
|-----|--------|------------|
| **No SSE/streaming on `/ask`** | Cannot do token-by-token streaming | Polling or show full response after completion. Backend returns full answer synchronously (~2-8s latency) |
| **No file upload endpoint** | Cannot attach files to queries | Phase 2 — needs new backend endpoint |
| **`sources[]` only with `debug=true`** | Need to always pass `debug=true` for source references | Send `debug: true` from frontend; or add `include_sources` flag (exists but may not return same data) |
| **No conversation CRUD API** | No create/delete/rename/list-by-user conversation endpoints | Manage conversations client-side (Zustand + localStorage). Backend only stores sliding window. |
| **No per-user conversation isolation** | `conversation_windows` keyed by `channel_key`, not `user_id` | Use unique session_id per conversation (UUID). User isolation via frontend session. |

### Nice-to-Have Gaps

| Gap | Impact |
|-----|--------|
| No conversation title generation | Frontend must auto-generate titles from first message |
| No conversation search API | Search must be client-side across localStorage |
| No message edit/delete | Messages are immutable in backend |
| No typing indicator / progress | No partial response streaming |
| No read receipts / status | N/A for single-user chat |

---

## 8. Complexity Estimates

| Feature | Complexity | Notes |
|---------|-----------|-------|
| **Conversation list (sidebar)** | Medium | Client-side CRUD, localStorage sync, no backend API |
| **Chat message display** | Medium | Markdown rendering, code blocks, tables via `react-markdown` + `rehype` |
| **Source references** | Simple | Render `sources[]` from `debug=true` response, icon per type |
| **Attachments** | Complex | No backend support — Phase 2. Can build UI shell now |
| **Streaming** | Complex | No SSE — must show loading state then full response |
| **Conversation context** | Simple | Pass `channel="web"` + `session_id=convId` to `/ask` |
| **Persist (Zustand + localStorage)** | Simple | Standard Zustand persist pattern, already used in codebase |
| **Quick actions** | Simple | Map `/brief` → `GET /brief/today`, etc. |

### Overall Module Complexity: **Medium**

Main risk: No streaming support means UX will feel less responsive than ChatGPT. Mitigations: good loading states, skeleton animations, latency display.

---

## 9. Architecture Decision: Conversation Management

**Recommendation:** Hybrid approach

1. **Frontend-managed conversations:** Zustand store persisted to localStorage holds conversation list, titles, and message history
2. **Backend-managed context:** Each conversation sends `channel="web"` + `session_id={convId}` to `/ask`, so backend maintains sliding window for prompt context
3. **Source data:** Always send `debug: true` (or `include_sources: true`) to get source references
4. **No backend CRUD:** Creating/deleting/renaming conversations is purely client-side

This avoids needing new backend endpoints while still leveraging the existing conversation window system for context continuity.

---

## 10. Component Plan (assistant-ui Integration)

```
/app/(app)/chat/
├── page.tsx                    # Chat page — new conversation or active conversation
├── [id]/
│   └── page.tsx                # Specific conversation view
├── _components/
│   ├── ChatSidebar.tsx         # Conversation list panel
│   ├── ChatWindow.tsx          # Main message area (uses assistant-ui Thread)
│   ├── MessageBubble.tsx       # Custom message rendering (markdown, code, tables)
│   ├── SourcePanel.tsx         # Collapsible source references under AI responses
│   ├── ChatInput.tsx           # Input field with quick actions (uses assistant-ui Composer)
│   ├── QuickActions.tsx        # /brief, /timeline, /meeting-prep buttons
│   ├── AttachmentChip.tsx      # File attachment preview (Phase 2)
│   └── EmptyState.tsx          # New conversation welcome screen
└── _stores/
    └── chat-store.ts           # Zustand store for conversations
```

**assistant-ui usage:**
- `Thread` component for message list + auto-scroll
- `Composer` for input field
- Custom `AssistantMessage` / `UserMessage` for rendering
- Custom runtime adapter to connect to our `/ask` endpoint (not OpenAI-compatible)
