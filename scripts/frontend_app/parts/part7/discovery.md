# Part 7: Voice & Real-time — Discovery Report

**Date:** 2026-03-29
**Module:** P7 — Voice interface: push-to-talk, real-time transcription, TTS, voice commands

---

## 1. Current State

**No voice components exist in the frontend.** The navigation module config in `packages/rbac/src/navigation.ts` already registers:
```typescript
{ id: 'voice', icon: 'Mic', roles: ['ceo', 'board'], label: { pl: 'Głos', en: 'Voice' }, path: '/voice' }
```
But the `/voice` page and all voice-specific components are missing.

**Backend is fully ready** — 5 HTTP endpoints + 1 WebSocket endpoint exist in `app/api/voice.py` and `app/api/voice_ws.py`. Both are mounted in `main.py`.

**No audio libraries** in `package.json` — will need `wavesurfer.js` or Canvas-based waveform.

---

## 2. API Endpoint Inventory

### HTTP Endpoints (voice.py)

| Method | Path | Content-Type | Params | Response |
|--------|------|-------------|--------|----------|
| POST | `/voice/transcribe` | `multipart/form-data` | `audio` (File), `language` (Form, default `"pl"`) | `{"text": str, "language": str}` |
| POST | `/voice/ask` | `multipart/form-data` | `audio` (File), `language` (Form, default `"pl"`), `session_id` (Form, default `"anonymous"`) | `{"transcript": str, "answer": str, "tts_available": bool, "meta": dict\|null}` |
| POST | `/voice/command` | `multipart/form-data` | `audio` (File), `language` (Form, default `"pl"`) | JSON: `{"transcript": str, "command_type": str, "response": str}` **or** StreamingResponse (MP3) with headers `X-Transcript`, `X-Response-Text` |
| POST | `/voice/tts` | `application/x-www-form-urlencoded` | `text` (Form), `voice` (Form, default `"pl-PL-ZofiaNeural"`) | StreamingResponse `audio/mpeg` (MP3 binary) |
| GET | `/voice/health` | — | none | `{"whisper": "ok"\|"down", "whisper_url": str, "tts": "ok"\|"not_installed...", "tts_voice": str, "mode": str, "features": str[]}` |

### WebSocket Endpoint (voice_ws.py)

| Path | Protocol |
|------|----------|
| `WS /voice/ws` | Binary audio chunks + JSON text frames |

**WebSocket Protocol:**

1. **Client → Server:** `{"action": "start", "conversation_id": "optional-uuid"}`
2. **Server → Client:** `{"type": "ready", "conversation_id": str}`
3. **Audio loop:**
   - Client sends binary audio chunks
   - Client sends text `"END"` to signal end of utterance
   - Server sends `{"type": "transcript", "text": str}`
   - Server sends `{"type": "response", "text": str}`
   - Server sends binary MP3 (TTS audio)
   - Server sends `{"type": "done"}`
4. Repeat from step 3 for next utterance
5. Client sends `"CLOSE"` to terminate

**Error frame:** `{"type": "error", "message": str}`

### Voice Commands (classified from transcript)

| Command | Trigger words | Action |
|---------|--------------|--------|
| `brief` | "brief" | Today's morning brief |
| `market` | "market", "rynek" | Market intelligence (3 days) |
| `competitors` | "competitors", "konkurencja" | Competitive landscape |
| `status` | "status" | System status + DB stats |
| `scenarios` | "scenarios", "scenariusze" | Recent scenarios with impact |
| `alerts` | "alerts", "alerty" | Active market alerts |

### Conversation Storage

```sql
-- Table: voice_conversations
-- Columns: id TEXT PK, messages JSONB DEFAULT '[]', created_at, updated_at
-- Message format: {"role": "user"|"assistant", "text": str, "timestamp": ISO8601}
-- Context window: last 20 messages
```

---

## 3. RBAC Rules

### Module Access
- **Voice module:** `ceo` (level 60) and `board` (level 50) only
- `gilbertus_admin` (level 99) bypasses all checks
- Director, manager, specialist — **NO access**
- Operator — **NO access** (infra only, no business data)

### Backend Auth
- Voice HTTP endpoints: **No explicit RBAC** — they rely on API-level auth (X-API-Key header)
- Voice WebSocket: **No explicit auth check** in `voice_ws.py`
- Frontend must enforce module-level RBAC via navigation filtering + page guard

### Frontend RBAC Pattern
```typescript
// Navigation already filtered by role in packages/rbac/src/navigation.ts
// Page-level: wrap with role check or redirect if unauthorized
// Hook: useRole() → { role, roleLevel }
// Check: usePermissions().hasPermission('...')
```

---

## 4. Existing Patterns to Follow

### Component Architecture
- `'use client'` directive on interactive components
- Props interface exported: `export interface XxxProps { ... }`
- Named function export: `export function Xxx({ ... }: XxxProps)`
- Tailwind CSS classes, CSS variables for theming
- Lucide icons (`Mic`, `MicOff`, `Volume2`, `Square`, `Play`, `Pause`)

### API Client
- `customFetch<T>(config)` in `packages/api-client/src/base.ts`
- Auto-injects `X-API-Key` header
- For voice: need **FormData** support (multipart upload) and **blob response** (TTS audio)
- WebSocket: use browser-native `WebSocket` (no library needed)

### State Management (Zustand)
- `create<Store>()(persist((set, get) => ({ ... }), { name: 'gilbertus-xxx' }))`
- Typed interface for store shape
- `persist` middleware with localStorage
- Pattern from `chat-store.ts`: conversations, messages, CRUD actions

### Layout & Routing
- Pages at `app/(app)/voice/page.tsx`
- Layout inherits from `app/(app)/layout.tsx` (Sidebar + Topbar)
- Floating voice button (FAB) goes in `app/(app)/layout.tsx` as global overlay

### i18n
- `next-intl` v4, Polish default, English secondary
- Message files in `messages/pl.json` and `messages/en.json`

---

## 5. Data Types / Interfaces Needed

```typescript
// --- Voice Store ---
interface VoiceState {
  isRecording: boolean;
  isProcessing: boolean;
  isPlaying: boolean;
  transcript: string | null;
  response: string | null;
  error: string | null;
  conversationId: string | null;
  wsConnected: boolean;
  sessions: VoiceSession[];
}

interface VoiceSession {
  id: string;
  conversationId: string;
  startedAt: string;
  messages: VoiceMessage[];
}

interface VoiceMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  audioUrl?: string; // blob URL for playback
  timestamp: string;
}

// --- API Response Types ---
interface TranscribeResponse {
  text: string;
  language: string;
}

interface VoiceAskResponse {
  transcript: string;
  answer: string;
  tts_available: boolean;
  meta: Record<string, unknown> | null;
}

interface VoiceCommandResponse {
  transcript: string;
  command_type: string;
  response: string;
}

interface VoiceHealthResponse {
  whisper: 'ok' | 'down';
  whisper_url: string;
  tts: string;
  tts_voice: string;
  mode: string;
  features: string[];
}

// --- WebSocket Message Types ---
type WsClientMessage =
  | { action: 'start'; conversation_id?: string }
  | 'END'
  | 'CLOSE'
  | ArrayBuffer; // binary audio

type WsServerMessage =
  | { type: 'ready'; conversation_id: string }
  | { type: 'transcript'; text: string }
  | { type: 'response'; text: string }
  | { type: 'done' }
  | { type: 'error'; message: string }
  | ArrayBuffer; // binary TTS audio
```

---

## 6. Backend Gaps & Integration Notes

### No Gaps (Backend is complete)
All 6 endpoints exist and are functional. No new backend work needed.

### Integration Notes

1. **FormData for audio upload:** `customFetch` currently handles JSON. Voice endpoints need `multipart/form-data` — must extend API client or use raw `fetch` for voice calls.

2. **Binary response handling:** `/voice/tts` and `/voice/command` return MP3 binary streams. Frontend needs `response.blob()` → `URL.createObjectURL()` for `<audio>` playback.

3. **WebSocket auth:** `/voice/ws` has **no auth check**. If API key is needed, must pass via query param (`?api_key=xxx`) or first message. Currently backend has no WS auth — acceptable for localhost, but flagged for future hardening.

4. **MediaRecorder format:** Backend Whisper accepts WAV, MP3, WebM. Browser `MediaRecorder` typically outputs `audio/webm;codecs=opus`. Verify Whisper handles this — if not, need client-side transcoding.

5. **Dual response from /voice/command:** Returns JSON **or** MP3 StreamingResponse depending on TTS availability. Frontend must check `Content-Type` header to determine response format.

6. **No transcript history endpoint:** Backend stores conversations in `voice_conversations` table but has **no GET endpoint** to list/retrieve past sessions. Frontend can:
   - (a) Store transcript history locally in Zustand (simpler, chosen approach)
   - (b) Request a new backend endpoint (future enhancement)

7. **Floating voice button:** Must be added to the shared `app/(app)/layout.tsx`. Should only render for `ceo`/`board` roles (use `useRole()` check).

---

## 7. Complexity Estimate

| Feature | Complexity | Notes |
|---------|-----------|-------|
| Voice page layout + routing | Simple | Standard page scaffold |
| Push-to-Talk button + MediaRecorder | Medium | Browser API, permissions, format handling |
| HTTP voice API client (transcribe, ask, command, tts) | Medium | FormData upload + binary response + dual Content-Type |
| WebSocket voice client | Complex | Binary frames, reconnection, state machine |
| Waveform visualization | Medium | Canvas API or wavesurfer.js integration |
| TTS audio playback | Simple | HTMLAudioElement + blob URL |
| Voice commands (quick actions) | Simple | Mapping command types to UI actions |
| Floating voice button (FAB) | Simple | Positioned overlay, role-gated |
| Zustand voice store | Medium | Recording state, WS connection, sessions |
| Transcript history (local) | Simple | Zustand persist, list UI |
| Keyboard shortcut (Space PTT) | Simple | Global keydown/keyup listener |
| Voice health indicator | Simple | GET /voice/health polling |

**Total estimate:** Medium-Complex (WebSocket + audio APIs are the main complexity drivers)

---

## 8. Key Decisions for Implementation

1. **Waveform library:** Use Canvas API (no extra dependency) for simple waveform during recording; consider `wavesurfer.js` only if playback waveform needed. Recommend: **Canvas API** (lighter).

2. **WebSocket vs HTTP mode:** Offer both — HTTP mode (simple ask/command) as default, WebSocket mode (real-time conversation) as toggle. HTTP is simpler and works for most use cases.

3. **Audio format:** Use `MediaRecorder` with `audio/webm;codecs=opus` (browser default). Whisper supports this. Fallback to `audio/wav` if needed.

4. **FAB placement:** Right-bottom corner, `fixed` position, `z-50`. Renders globally in `app/(app)/layout.tsx` behind role guard. Click opens voice panel/modal.

5. **Voice panel UX:** Two modes:
   - **Quick mode** (from FAB): overlay/modal with PTT button, shows transcript + response
   - **Full mode** (`/voice` page): full conversation view with history, waveform, settings

6. **No new npm packages required** for MVP. Canvas waveform + native WebSocket + native MediaRecorder. Add `wavesurfer.js` later if richer waveform needed.

7. **API client extension:** Add `voiceApi` module alongside existing `gilbertus.ts` in `packages/api-client/src/voice.ts` — handles FormData and blob responses.
