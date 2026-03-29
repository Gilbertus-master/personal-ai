import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface VoiceMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  audioUrl?: string;
  timestamp: string;
}

export interface VoiceSession {
  id: string;
  startedAt: string;
  title: string;
  messages: VoiceMessage[];
}

const MAX_SESSIONS = 30;

interface VoiceStore {
  // --- Transient state (not persisted) ---
  isRecording: boolean;
  isProcessing: boolean;
  isPlaying: boolean;
  error: string | null;
  wsConnected: boolean;
  conversationId: string | null;

  // --- Persisted preferences ---
  mode: 'http' | 'websocket';
  language: 'pl' | 'en';
  autoPlayTts: boolean;
  voiceName: string;

  // --- Persisted sessions ---
  sessions: VoiceSession[];
  activeSessionId: string | null;

  // --- Transient actions ---
  setRecording: (v: boolean) => void;
  setProcessing: (v: boolean) => void;
  setPlaying: (v: boolean) => void;
  setError: (e: string | null) => void;
  setWsConnected: (v: boolean) => void;
  setConversationId: (id: string | null) => void;

  // --- Preference actions ---
  setMode: (m: 'http' | 'websocket') => void;
  setLanguage: (l: 'pl' | 'en') => void;
  setAutoPlayTts: (v: boolean) => void;
  setVoiceName: (v: string) => void;

  // --- Session actions ---
  createSession: () => string;
  addMessage: (sessionId: string, msg: Omit<VoiceMessage, 'id' | 'timestamp'>) => void;
  setActiveSession: (id: string | null) => void;
  deleteSession: (id: string) => void;
  clearSessions: () => void;
}

function updateSession(
  sessions: VoiceSession[],
  sessionId: string,
  updater: (s: VoiceSession) => VoiceSession,
): VoiceSession[] {
  return sessions.map((s) => (s.id === sessionId ? updater(s) : s));
}

export const useVoiceStore = create<VoiceStore>()(
  persist(
    (set) => ({
      // Transient defaults
      isRecording: false,
      isProcessing: false,
      isPlaying: false,
      error: null,
      wsConnected: false,
      conversationId: null,

      // Persisted preference defaults
      mode: 'http',
      language: 'pl',
      autoPlayTts: true,
      voiceName: 'pl-PL-ZofiaNeural',

      // Persisted session defaults
      sessions: [],
      activeSessionId: null,

      // Transient setters
      setRecording: (v) => set({ isRecording: v }),
      setProcessing: (v) => set({ isProcessing: v }),
      setPlaying: (v) => set({ isPlaying: v }),
      setError: (e) => set({ error: e }),
      setWsConnected: (v) => set({ wsConnected: v }),
      setConversationId: (id) => set({ conversationId: id }),

      // Preference setters
      setMode: (m) => set({ mode: m }),
      setLanguage: (l) => set({ language: l }),
      setAutoPlayTts: (v) => set({ autoPlayTts: v }),
      setVoiceName: (v) => set({ voiceName: v }),

      // Session actions
      createSession: () => {
        const id = crypto.randomUUID();
        const now = new Date().toISOString();
        const session: VoiceSession = {
          id,
          startedAt: now,
          title: 'Nowa sesja głosowa',
          messages: [],
        };
        set((s) => {
          let sessions = [session, ...s.sessions];
          if (sessions.length > MAX_SESSIONS) {
            sessions = sessions
              .sort((a, b) => b.startedAt.localeCompare(a.startedAt))
              .slice(0, MAX_SESSIONS);
          }
          return { sessions, activeSessionId: id };
        });
        return id;
      },

      addMessage: (sessionId, msg) => {
        const newMsg: VoiceMessage = {
          ...msg,
          id: crypto.randomUUID(),
          timestamp: new Date().toISOString(),
        };
        set((s) => ({
          sessions: updateSession(s.sessions, sessionId, (session) => {
            const messages = [...session.messages, newMsg];
            const isFirstUserMessage =
              msg.role === 'user' &&
              !session.messages.some((m) => m.role === 'user');
            const title = isFirstUserMessage
              ? msg.text.length > 50
                ? msg.text.slice(0, 50) + '...'
                : msg.text
              : session.title;
            return { ...session, messages, title };
          }),
        }));
      },

      setActiveSession: (id) => set({ activeSessionId: id }),

      deleteSession: (id) =>
        set((s) => ({
          sessions: s.sessions.filter((session) => session.id !== id),
          activeSessionId: s.activeSessionId === id ? null : s.activeSessionId,
        })),

      clearSessions: () => set({ sessions: [], activeSessionId: null }),
    }),
    {
      name: 'gilbertus-voice',
      partialize: (state) => ({
        mode: state.mode,
        language: state.language,
        autoPlayTts: state.autoPlayTts,
        voiceName: state.voiceName,
        sessions: state.sessions,
        activeSessionId: state.activeSessionId,
      }),
    },
  ),
);

/** Selector: sessions sorted by startedAt DESC */
export const selectSortedSessions = (s: { sessions: VoiceSession[] }) =>
  [...s.sessions].sort((a, b) => b.startedAt.localeCompare(a.startedAt));

/** Selector: active session */
export const selectActiveSession = (s: {
  sessions: VoiceSession[];
  activeSessionId: string | null;
}) => s.sessions.find((session) => session.id === s.activeSessionId) ?? null;
