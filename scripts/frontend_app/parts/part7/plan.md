# Part 7: Voice & Real-time — Architecture Plan

## 1. Component Tree

```
app/(app)/layout.tsx
├── ... existing layout ...
└── <VoiceFab />                          ← NEW: floating voice button (ceo/board only)
    └── <VoiceQuickPanel />               ← overlay mini-panel on FAB click

app/(app)/voice/page.tsx                  ← NEW: full voice page
├── <VoiceHeader />                       ← title, health indicator, mode toggle
├── <VoiceSessionList />                  ← left sidebar: past sessions
│   └── <VoiceSessionItem />             ← single session entry
├── <VoiceConversation />                 ← main area: transcript display
│   └── <VoiceMessage />                 ← single message bubble (user/assistant)
│       └── <VoiceWaveform />            ← inline audio waveform (Canvas)
├── <VoiceControls />                     ← bottom: PTT button, mode selector, settings
│   ├── <PushToTalkButton />             ← main record button with animation
│   └── <VoiceCommandBar />             ← quick command chips
└── <VoiceHealthBadge />                 ← status indicator
```

## 2. File Tree

```
frontend/
├── packages/
│   ├── api-client/src/
│   │   ├── voice-types.ts               ← TypeScript types for voice API
│   │   ├── voice.ts                     ← API client (FormData + blob + WS)
│   │   └── index.ts                     ← add voice exports
│   └── ui/src/components/
│       └── voice/
│           ├── index.ts                 ← barrel exports
│           ├── push-to-talk-button.tsx   ← PTT button with ring animation
│           ├── voice-waveform.tsx        ← Canvas-based waveform visualizer
│           ├── voice-message.tsx         ← single transcript/response bubble
│           ├── voice-conversation.tsx    ← message list + auto-scroll
│           ├── voice-session-list.tsx    ← session history sidebar
│           ├── voice-session-item.tsx    ← single session row
│           ├── voice-controls.tsx        ← bottom control bar
│           ├── voice-command-bar.tsx     ← quick command chips
│           ├── voice-header.tsx          ← page header + health + mode toggle
│           ├── voice-health-badge.tsx    ← health status indicator
│           ├── voice-fab.tsx             ← floating action button
│           └── voice-quick-panel.tsx     ← overlay panel from FAB
├── apps/web/
│   ├── app/(app)/voice/
│   │   └── page.tsx                     ← voice page composition
│   ├── lib/stores/
│   │   └── voice-store.ts              ← Zustand store
│   └── lib/hooks/
│       ├── use-voice.ts                ← main voice hook (recording, WS, playback)
│       └── use-voice-health.ts         ← health polling hook
```

## 3. API Integration Map

| Component | Endpoint | Method | Notes |
|-----------|----------|--------|-------|
| `use-voice.ts` (HTTP mode) | `/voice/ask` | POST multipart | Audio file + language + session_id |
| `use-voice.ts` (WS mode) | `/voice/ws` | WebSocket | Binary audio chunks + JSON control |
| `use-voice.ts` (command) | `/voice/command` | POST multipart | Dual response: JSON or MP3 stream |
| `VoiceControls` | `/voice/tts` | POST form | Text → MP3 for replay |
| `use-voice-health.ts` | `/voice/health` | GET | Polls every 30s |
| `VoiceQuickPanel` | `/voice/ask` | POST multipart | Simplified flow from FAB |

## 4. RBAC

| Component | Access | Implementation |
|-----------|--------|---------------|
| `/voice` page | ceo, board | Navigation filter already in place; page imports `useRole()` guard |
| `VoiceFab` | ceo, board | Conditional render in layout via `useRole()` |
| `VoiceQuickPanel` | ceo, board | Only reachable from FAB (inherits) |
| Voice API calls | API key auth | `X-API-Key` header via `getApiKey()` from base |

## 5. State Management — Zustand Store

```typescript
// voice-store.ts — persisted to localStorage as 'gilbertus-voice'

interface VoiceStore {
  // Recording state (not persisted)
  isRecording: boolean;
  isProcessing: boolean;
  isPlaying: boolean;
  error: string | null;

  // WebSocket state (not persisted)
  wsConnected: boolean;
  conversationId: string | null;

  // Preferences (persisted)
  mode: 'http' | 'websocket';           // default: 'http'
  language: 'pl' | 'en';                // default: 'pl'
  autoPlayTts: boolean;                  // default: true
  voiceName: string;                     // default: 'pl-PL-ZofiaNeural'

  // Session history (persisted, max 30)
  sessions: VoiceSession[];
  activeSessionId: string | null;

  // Actions
  setRecording: (v: boolean) => void;
  setProcessing: (v: boolean) => void;
  setPlaying: (v: boolean) => void;
  setError: (e: string | null) => void;
  setWsConnected: (v: boolean) => void;
  setConversationId: (id: string | null) => void;
  setMode: (m: 'http' | 'websocket') => void;
  setLanguage: (l: 'pl' | 'en') => void;
  setAutoPlayTts: (v: boolean) => void;

  // Session CRUD
  createSession: () => string;
  addMessage: (sessionId: string, msg: VoiceMessage) => void;
  setActiveSession: (id: string | null) => void;
  deleteSession: (id: string) => void;
}
```

**Partialize:** Only persist `mode`, `language`, `autoPlayTts`, `voiceName`, `sessions`, `activeSessionId`. Transient state (`isRecording`, `isProcessing`, etc.) resets on reload.

## 6. UX Flows

### Flow A: HTTP Push-to-Talk (default mode)
1. User holds PTT button (or Space key)
2. `MediaRecorder` starts → `isRecording: true` → waveform animates
3. User releases → `MediaRecorder.stop()` → blob captured → `isRecording: false`
4. `isProcessing: true` → POST `/voice/ask` with FormData(audio, language, session_id)
5. Response: `{ transcript, answer, tts_available }`
6. Add user message (transcript) + assistant message (answer) to session
7. If `autoPlayTts && tts_available`: POST `/voice/tts` → blob → play via `<audio>`
8. `isProcessing: false`

### Flow B: WebSocket Real-time Mode
1. User toggles to WS mode → connect to `/voice/ws`
2. Send `{"action": "start"}` → receive `{"type": "ready", "conversation_id": "..."}`
3. User holds PTT → `MediaRecorder` with `timeslice=250ms` → sends binary chunks over WS
4. User releases → send text `"END"`
5. Server sends: `transcript` → `response` → binary MP3 → `done`
6. Display transcript + response, play MP3
7. Repeat for next utterance

### Flow C: Voice Command (quick action)
1. User taps command chip ("Brief", "Status", "Market")
2. Record short audio or use pre-set command text
3. POST `/voice/command` → check Content-Type
4. If JSON: display `command_type` + `response`
5. If MP3: play audio, extract text from `X-Response-Text` header

### Flow D: FAB Quick Voice
1. User clicks floating mic button → `VoiceQuickPanel` slides up
2. Single PTT button + transcript display
3. Uses HTTP mode (`/voice/ask`)
4. Shows response text + plays TTS
5. Click away or X to dismiss

### Flow E: Keyboard Shortcut
1. Space keydown (not in input/textarea) → start recording
2. Space keyup → stop recording → process
3. Escape → cancel recording (discard audio)

## 7. Key Technical Decisions

1. **Canvas waveform** — no external dependency. `AnalyserNode` from Web Audio API feeds `requestAnimationFrame` Canvas draw loop. Simple bar visualization.

2. **MediaRecorder config:** `{ mimeType: 'audio/webm;codecs=opus' }` with fallback to `audio/webm`. Whisper handles both.

3. **FormData API client:** Voice module uses raw `fetch` with `getApiKey()` for auth header — `customFetch` hardcodes `Content-Type: application/json` which conflicts with `multipart/form-data`. The voice.ts client builds its own fetch with proper headers.

4. **Audio playback:** `new Audio(URL.createObjectURL(blob))` — simple, no library needed. Track blob URLs and revoke them on cleanup.

5. **WS reconnection:** Exponential backoff (1s, 2s, 4s, max 16s). Max 5 retries. Show connection state in UI.

6. **i18n:** Add `voice` section to `messages/pl.json` and `messages/en.json` with all UI strings.

## 8. Integration with Layout

The `VoiceFab` component is added to `app/(app)/layout.tsx` as a sibling to `CommandPalette`:

```tsx
{/* After CommandPalette */}
<VoiceFab />  {/* Role-gated internally */}
```

The FAB manages its own open/close state and renders `VoiceQuickPanel` as a portal/overlay.
