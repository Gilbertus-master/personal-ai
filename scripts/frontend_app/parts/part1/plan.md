# Part 1: Chat Core — Architecture Plan

**Module:** Multi-conversation AI Assistant
**Date:** 2026-03-29

---

## 1. Component Tree (Visual Hierarchy)

```
AppLayout (existing)
├── Sidebar (existing — with /chat link already in nav)
├── Topbar (existing)
└── <main>
    └── /chat (page.tsx) ─────────────────────────────────
        │                                                  │
        ├── ChatLayout                                     │
        │   ├── ChatSidebar (left panel, 280px)            │
        │   │   ├── NewChatButton                          │
        │   │   ├── SearchInput                            │
        │   │   └── ConversationList                       │
        │   │       └── ConversationItem[] (mapped)        │
        │   │           ├── title                          │
        │   │           ├── last message preview            │
        │   │           ├── timestamp                       │
        │   │           └── DeleteButton (hover)            │
        │   │                                              │
        │   └── ChatMain (flex-1)                          │
        │       ├── ChatHeader                             │
        │       │   ├── conversation title                 │
        │       │   ├── RenameButton                       │
        │       │   └── ChatSidebar toggle (mobile)        │
        │       │                                          │
        │       ├── MessageList (scrollable)               │
        │       │   └── MessageBubble[]                    │
        │       │       ├── UserMessage                    │
        │       │       │   └── content (text)             │
        │       │       └── AssistantMessage               │
        │       │           ├── content (markdown)         │
        │       │           ├── SourcePanel (collapsible)  │
        │       │           │   └── SourceCard[]           │
        │       │           └── meta (latency, cache)      │
        │       │                                          │
        │       ├── EmptyState (when no messages)          │
        │       │   ├── Logo + greeting                    │
        │       │   └── QuickActions grid                  │
        │       │                                          │
        │       └── ChatInput (fixed bottom)               │
        │           ├── textarea (auto-resize)             │
        │           ├── QuickActionsMenu (/ trigger)       │
        │           ├── AttachButton (Phase 2 — disabled)  │
        │           └── SendButton                         │
        │                                                  │
        └── /chat/[id] (page.tsx) ── same layout ─────────
            └── loads conversation by id from store
```

---

## 2. File Tree (Every File Path)

```
frontend/
├── apps/web/
│   ├── app/(app)/chat/
│   │   ├── page.tsx                          # Chat page — creates or shows active conv
│   │   ├── [id]/
│   │   │   └── page.tsx                      # Specific conversation by ID
│   │   └── layout.tsx                        # Chat-specific layout (sidebar + main)
│   │
│   └── lib/
│       ├── stores/
│       │   └── chat-store.ts                 # Zustand: conversations, messages, CRUD
│       └── hooks/
│           └── use-chat.ts                   # Hook: sendMessage, quickActions, abort
│
├── packages/
│   ├── ui/src/components/chat/
│   │   ├── chat-sidebar.tsx                  # Left panel: conversation list
│   │   ├── conversation-item.tsx             # Single conversation in list
│   │   ├── chat-header.tsx                   # Top bar of chat area
│   │   ├── message-list.tsx                  # Scrollable message container
│   │   ├── message-bubble.tsx                # Single message (user or assistant)
│   │   ├── markdown-renderer.tsx             # Markdown → React (react-markdown)
│   │   ├── source-panel.tsx                  # Collapsible sources under AI message
│   │   ├── source-card.tsx                   # Single source reference card
│   │   ├── chat-input.tsx                    # Input area with textarea + actions
│   │   ├── quick-actions.tsx                 # Quick action buttons/menu
│   │   ├── empty-state.tsx                   # Welcome screen for new conversations
│   │   └── index.ts                          # Re-exports
│   │
│   └── api-client/src/
│       ├── types.ts                          # Add: AskRequest, AskResponse, etc.
│       ├── chat.ts                           # Chat-specific API functions
│       └── index.ts                          # Add: chat exports
```

---

## 3. API Integration Map

| Component | Endpoint | Method | When |
|-----------|----------|--------|------|
| `use-chat.ts` → `sendMessage()` | `/ask` | POST | User sends message |
| `use-chat.ts` → `quickAction('brief')` | `/brief/today` | GET | User clicks /brief |
| `use-chat.ts` → `quickAction('timeline')` | `/timeline` | POST | User clicks /timeline |
| `use-chat.ts` → `quickAction('meeting-prep')` | `/meeting-prep` | GET | User clicks /meeting-prep |
| `use-chat.ts` → `quickAction('alerts')` | `/alerts` | GET | User clicks /alerts |
| `use-chat.ts` → `quickAction('commitments')` | `/commitments` | GET | User clicks /commitments |
| `chat-store.ts` | — (localStorage) | — | Conversation CRUD |

### API Call Details

**POST /ask** (primary):
```typescript
{
  query: string,
  top_k: 8,
  answer_length: roleLevel >= 60 ? "long" : "medium",
  channel: "web",
  session_id: conversationId,     // UUID — enables backend sliding window
  debug: true,                     // always — to get sources[]
  include_sources: true,
}
```

**Quick Actions** map to dedicated endpoints — response is displayed as an assistant message with the raw answer text.

---

## 4. RBAC per View/Component

| Component | Access Rule | Implementation |
|-----------|-------------|----------------|
| `/chat` page | All authenticated users | `roles: ['*']` in navigation (already configured) |
| Chat sidebar | All users | No gate needed |
| Source panel | All users (backend filters by role) | No frontend filtering — backend enforces classification |
| Quick actions | All users (backend validates) | No gate needed |
| answer_length default | CEO/admin → "long", others → "medium" | `useRole()` hook in `use-chat.ts` |

**Key decision:** No frontend RBAC gating needed within the chat module. The backend `/ask` endpoint handles all data access filtering based on the auth context (API key or Omnius token). The frontend simply passes `debug: true` and renders whatever the backend returns.

---

## 5. State Management (Zustand Store)

### `chat-store.ts`

```typescript
interface Conversation {
  id: string;                    // UUID
  title: string;                 // Auto from first message, editable
  createdAt: string;             // ISO datetime
  lastActive: string;            // ISO datetime
  messages: Message[];           // Full message history (client-side)
}

interface Message {
  id: string;                    // UUID
  role: 'user' | 'assistant';
  content: string;
  sources?: SourceItem[];        // From /ask debug response
  meta?: AskResponseMeta;        // latency, cache_hit, etc.
  timestamp: string;             // ISO datetime
  isLoading?: boolean;           // True while waiting for response
  error?: string;                // Error message if failed
}

interface ChatStore {
  // State
  conversations: Conversation[];
  activeConversationId: string | null;

  // Computed (via selectors)
  // activeConversation: Conversation | undefined

  // Actions
  createConversation: () => string;                    // Returns new ID
  deleteConversation: (id: string) => void;
  renameConversation: (id: string, title: string) => void;
  setActiveConversation: (id: string | null) => void;

  // Message actions
  addUserMessage: (convId: string, content: string) => string;  // Returns msg ID
  addAssistantMessage: (convId: string, content: string, sources?: SourceItem[], meta?: AskResponseMeta) => void;
  setMessageLoading: (convId: string, msgId: string, loading: boolean) => void;
  setMessageError: (convId: string, msgId: string, error: string) => void;

  // Search
  searchConversations: (query: string) => Conversation[];
}
```

**Persistence:** `zustand/middleware/persist` → localStorage key `'gilbertus-chat'`

**Storage limit strategy:** Keep max 50 conversations in localStorage. Auto-prune oldest when exceeded.

---

## 6. UX Flows

### Flow 1: New Conversation (from /chat)
```
1. User navigates to /chat
2. EmptyState shown: greeting, QuickActions grid
3a. User types message → createConversation() → addUserMessage() → POST /ask → addAssistantMessage()
3b. User clicks QuickAction → createConversation() → addUserMessage(action label) → GET endpoint → addAssistantMessage()
4. Title auto-set from first ~50 chars of user message
5. URL updates to /chat/{id}
6. Conversation appears in sidebar
```

### Flow 2: Continue Conversation
```
1. User clicks conversation in sidebar
2. URL → /chat/{id}
3. Messages loaded from Zustand store
4. Auto-scroll to bottom
5. User types → addUserMessage() → POST /ask (with session_id=id) → addAssistantMessage()
6. Backend uses sliding window context for better answers
```

### Flow 3: Send Message
```
1. User types in ChatInput textarea
2. Enter (without Shift) → submit
3. Shift+Enter → newline
4. Message appears in MessageList as UserMessage
5. AssistantMessage placeholder appears with loading skeleton
6. POST /ask fires with: query, channel="web", session_id, debug=true
7. On success: loading skeleton replaced with full response + sources
8. On error: error state with retry button
9. Auto-scroll to new message
```

### Flow 4: Quick Actions
```
1. User types "/" in ChatInput → QuickActionsMenu appears
2. Shows: /brief, /timeline, /meeting-prep, /alerts, /commitments
3. User selects → fires specific endpoint
4. Response rendered as assistant message
5. Displayed in current conversation context
```

### Flow 5: Source References
```
1. Assistant message rendered
2. If sources[] non-empty: SourcePanel toggle shown ("3 źródła")
3. Click toggle → panel expands with SourceCard list
4. Each SourceCard: icon (by type), title, source_name, date
5. Icons: Mail (email), Users (teams), MessageCircle (whatsapp),
   FileText (document), Mic (plaud), Calendar (calendar)
```

### Flow 6: Delete/Rename Conversation
```
Delete:
1. Hover conversation → trash icon appears
2. Click → confirmation inline ("Usuń?")
3. Confirm → conversation removed from store
4. If was active → redirect to /chat (empty state)

Rename:
1. Click conversation title in ChatHeader
2. Inline edit input appears
3. Enter/blur → save new title
4. Esc → cancel
```

---

## 7. Key Technical Decisions

### No Streaming (Phase 1)
Backend `/ask` returns complete response synchronously (2-8s). UI shows:
- Loading skeleton with animated dots
- Elapsed time counter ("Myślę... 3s")
- Full response appears at once
- Future: SSE streaming when backend supports it

### No assistant-ui (Simplified)
After analysis, assistant-ui adds complexity without clear benefit given:
- No streaming support
- Custom backend (not OpenAI-compatible)
- Simple request/response pattern
- Custom source panel and quick actions

**Decision:** Build with plain React components + Zustand. Less abstraction, full control, easier to debug. If streaming is added later, can adopt assistant-ui's runtime adapter then.

### Markdown Rendering
Use `react-markdown` + `remark-gfm` + `rehype-highlight` for:
- Headers, bold, italic, lists
- Code blocks with syntax highlighting
- Tables (GFM)
- Links (open in new tab)

### localStorage vs Backend for Conversations
Conversations managed client-side only. Backend's `conversation_windows` table handles context window (20 messages) for prompt construction. This means:
- Client keeps full history (for display)
- Backend keeps sliding window (for context)
- No sync needed — they serve different purposes

---

## 8. Dependencies to Add

```json
{
  "packages/ui": {
    "react-markdown": "^9.0.0",
    "remark-gfm": "^4.0.0",
    "rehype-highlight": "^7.0.0"
  }
}
```

No other new dependencies needed. Existing: zustand, lucide-react, @radix-ui/* are sufficient.
