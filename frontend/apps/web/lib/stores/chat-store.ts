import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// TODO: import from @gilbertus/api-client once P1T1 lands
export interface SourceItem {
  source_type: string;
  source_name: string;
  content: string;
  score?: number;
  date?: string;
}

export interface AskResponseMeta {
  run_id?: string;
  latency_ms?: number;
  model?: string;
  cached?: boolean;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: SourceItem[];
  meta?: AskResponseMeta;
  timestamp: string;
  isLoading?: boolean;
  error?: string;
}

export interface Conversation {
  id: string;
  title: string;
  createdAt: string;
  lastActive: string;
  messages: ChatMessage[];
}

const MAX_CONVERSATIONS = 50;

interface ChatStore {
  conversations: Conversation[];
  activeConversationId: string | null;

  createConversation: () => string;
  deleteConversation: (id: string) => void;
  renameConversation: (id: string, title: string) => void;
  setActiveConversation: (id: string | null) => void;

  addUserMessage: (convId: string, content: string) => string;
  addAssistantMessage: (convId: string, content: string, sources?: SourceItem[], meta?: AskResponseMeta) => void;
  updateAssistantMessage: (convId: string, msgId: string, content: string, sources?: SourceItem[], meta?: AskResponseMeta) => void;
  setMessageLoading: (convId: string, msgId: string, loading: boolean) => void;
  setMessageError: (convId: string, msgId: string, error: string) => void;
}

function updateConversation(
  conversations: Conversation[],
  convId: string,
  updater: (conv: Conversation) => Conversation,
): Conversation[] {
  return conversations.map((c) => (c.id === convId ? updater(c) : c));
}

function updateMessage(
  messages: ChatMessage[],
  msgId: string,
  updater: (msg: ChatMessage) => ChatMessage,
): ChatMessage[] {
  return messages.map((m) => (m.id === msgId ? updater(m) : m));
}

export const useChatStore = create<ChatStore>()(
  persist(
    (set, get) => ({
      conversations: [],
      activeConversationId: null,

      createConversation: () => {
        const id = crypto.randomUUID();
        const now = new Date().toISOString();
        const conv: Conversation = {
          id,
          title: 'Nowa rozmowa',
          createdAt: now,
          lastActive: now,
          messages: [],
        };
        set((s) => {
          let convs = [conv, ...s.conversations];
          if (convs.length > MAX_CONVERSATIONS) {
            convs = convs
              .sort((a, b) => b.lastActive.localeCompare(a.lastActive))
              .slice(0, MAX_CONVERSATIONS);
          }
          return { conversations: convs, activeConversationId: id };
        });
        return id;
      },

      deleteConversation: (id) =>
        set((s) => ({
          conversations: s.conversations.filter((c) => c.id !== id),
          activeConversationId: s.activeConversationId === id ? null : s.activeConversationId,
        })),

      renameConversation: (id, title) =>
        set((s) => ({
          conversations: updateConversation(s.conversations, id, (c) => ({ ...c, title })),
        })),

      setActiveConversation: (id) => set({ activeConversationId: id }),

      addUserMessage: (convId, content) => {
        const msgId = crypto.randomUUID();
        const now = new Date().toISOString();
        const msg: ChatMessage = {
          id: msgId,
          role: 'user',
          content,
          timestamp: now,
        };
        set((s) => ({
          conversations: updateConversation(s.conversations, convId, (c) => {
            const isFirstMessage = c.messages.length === 0;
            return {
              ...c,
              title: isFirstMessage
                ? content.length > 60
                  ? content.slice(0, 60) + '...'
                  : content
                : c.title,
              lastActive: now,
              messages: [...c.messages, msg],
            };
          }),
        }));
        return msgId;
      },

      addAssistantMessage: (convId, content, sources, meta) => {
        const now = new Date().toISOString();
        const msg: ChatMessage = {
          id: crypto.randomUUID(),
          role: 'assistant',
          content,
          sources,
          meta,
          timestamp: now,
        };
        set((s) => ({
          conversations: updateConversation(s.conversations, convId, (c) => ({
            ...c,
            lastActive: now,
            messages: [...c.messages, msg],
          })),
        }));
      },

      updateAssistantMessage: (convId, msgId, content, sources, meta) =>
        set((s) => ({
          conversations: updateConversation(s.conversations, convId, (c) => ({
            ...c,
            messages: updateMessage(c.messages, msgId, (m) => ({
              ...m,
              content,
              sources,
              meta,
              isLoading: false,
            })),
          })),
        })),

      setMessageLoading: (convId, msgId, loading) =>
        set((s) => ({
          conversations: updateConversation(s.conversations, convId, (c) => ({
            ...c,
            messages: updateMessage(c.messages, msgId, (m) => ({
              ...m,
              isLoading: loading,
            })),
          })),
        })),

      setMessageError: (convId, msgId, error) =>
        set((s) => ({
          conversations: updateConversation(s.conversations, convId, (c) => ({
            ...c,
            messages: updateMessage(c.messages, msgId, (m) => ({
              ...m,
              error,
            })),
          })),
        })),
    }),
    { name: 'gilbertus-chat' },
  ),
);

/** Selector: conversations sorted by lastActive DESC */
export const selectSortedConversations = (s: { conversations: Conversation[] }) =>
  [...s.conversations].sort((a, b) => b.lastActive.localeCompare(a.lastActive));

/** Selector: active conversation */
export const selectActiveConversation = (s: {
  conversations: Conversation[];
  activeConversationId: string | null;
}) => s.conversations.find((c) => c.id === s.activeConversationId) ?? null;
