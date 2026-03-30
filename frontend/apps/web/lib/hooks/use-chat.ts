'use client';

import { useCallback, useRef } from 'react';
import { useChatStore } from '@/lib/stores/chat-store';
import { useRole } from '@gilbertus/rbac';
import {
  askGilbertus,
  getBriefToday,
  getAlerts,
  getCommitments,
  getMeetingPrep,
  postTimeline,
} from '@gilbertus/api-client';
import type { AskResponse } from '@gilbertus/api-client';
import type { SourceItem, AskResponseMeta } from '@/lib/stores/chat-store';

const QUICK_ACTION_LABELS: Record<string, string> = {
  brief: '/brief — Poranny brief',
  timeline: '/timeline — Ostatnie wydarzenia',
  'meeting-prep': '/meeting-prep — Przygotowanie na spotkanie',
  alerts: '/alerts — Aktywne alerty',
  commitments: '/commitments — Zobowiązania',
};

/**
 * After calling addAssistantMessage (sync Zustand update),
 * retrieve the ID of the last message in the conversation.
 */
function getLastMessageId(convId: string): string | undefined {
  const conv = useChatStore
    .getState()
    .conversations.find((c) => c.id === convId);
  const msgs = conv?.messages;
  return msgs?.[msgs.length - 1]?.id;
}

function mapSources(response: AskResponse): SourceItem[] | undefined {
  return response.sources?.map((s) => ({
    source_type: s.source_type,
    source_name: s.source_name,
    content: s.title,
    date: s.created_at,
  }));
}

function mapMeta(response: AskResponse): AskResponseMeta {
  return {
    run_id: response.run_id ? String(response.run_id) : undefined,
    latency_ms: response.meta.latency_ms,
    cached: response.meta.cache_hit,
  };
}

function formatQuickActionResponse(res: unknown): string {
  if (typeof res === 'string') return res;
  if (res && typeof res === 'object') {
    // Extract the main content field if present
    const obj = res as Record<string, unknown>;
    if ('brief' in obj && typeof obj.brief === 'string') return obj.brief;
    if ('prep' in obj && typeof obj.prep === 'string') return obj.prep;
    return JSON.stringify(res, null, 2);
  }
  return String(res);
}


// ── Model routing — wybierz najtańszy model który poradzi z pytaniem ──────
function classifyQuery(text: string): 'cheap' | 'balanced' | 'best' {
  const t = text.toLowerCase().trim();

  // Proste wyszukiwanie / lookup → najtańszy model
  const simplePatterns = [
    /^(kto|co|kiedy|gdzie|ile|czy|jaki|jaka|jakie)\s/,
    /^(who|what|when|where|how many|is there)/,
    /\?$/, // pytanie kończące się znakiem zapytania (krótkie)
    /^(pokaż|pokaż mi|lista|wymień|ile mam|czy mam)/,
  ];
  const isSimple = t.length < 80 && simplePatterns.some((p) => p.test(t));
  if (isSimple) return 'cheap';

  // Złożona analiza / raport / strategia → najlepszy model
  const complexPatterns = [
    /analiz|strategia|plan|rekomendacja|ocen|zrób raport|porównaj|zbadaj/,
    /analyze|strategy|recommend|compare|evaluate|deep.?dive/,
    /co powinienem|jak powinienem|jakie są opcje|jakie mam możliwości/,
  ];
  const isComplex = t.length > 200 || complexPatterns.some((p) => p.test(t));
  if (isComplex) return 'best';

  return 'balanced';
}

const MODEL_LABELS: Record<string, string> = {
  cheap: '⚡ Haiku (szybki)',
  balanced: '🎯 Sonnet (zbalansowany)',
  best: '🧠 Opus (najlepszy)',
};

export function useChat() {
  const store = useChatStore();
  const { roleLevel } = useRole();
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    async (text: string, conversationId?: string) => {
      // 1. Resolve or create conversation
      const convId =
        conversationId ?? store.activeConversationId ?? store.createConversation();
      store.setActiveConversation(convId);

      // 2. Add user message
      store.addUserMessage(convId, text);

      // 3. Add placeholder assistant message in loading state
      store.addAssistantMessage(convId, '');
      const assistantMsgId = getLastMessageId(convId);
      if (!assistantMsgId) return;
      store.setMessageLoading(convId, assistantMsgId, true);

      // 4. Abort any in-flight request
      abortRef.current?.abort();
      abortRef.current = new AbortController();

      // 5. Call /ask
      try {
        const modelPref = classifyQuery(text);
        const response = await askGilbertus(
          {
            query: text,
            top_k: 8,
            answer_length: roleLevel >= 60 ? 'long' : 'medium',
            channel: 'web',
            session_id: convId,
            debug: true,
            include_sources: true,
            model_preference: modelPref,
          },
          abortRef.current.signal,
        );

        // 6. Update assistant message with mapped response
        store.updateAssistantMessage(
          convId,
          assistantMsgId,
          response.answer,
          mapSources(response),
          mapMeta(response),
        );
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        const message =
          err instanceof Error ? err.message : 'Błąd połączenia';
        store.setMessageError(convId, assistantMsgId, message);
        store.setMessageLoading(convId, assistantMsgId, false);
      }
    },
    [store, roleLevel],
  );

  const handleQuickAction = useCallback(
    async (rawActionId: string, conversationId?: string) => {
      const actionId = rawActionId.replace(/^\//, ''); // strip leading slash
      const convId =
        conversationId ?? store.activeConversationId ?? store.createConversation();
      store.setActiveConversation(convId);

      // Add user message with action label
      store.addUserMessage(convId, QUICK_ACTION_LABELS[actionId] ?? `/${actionId}`);

      // Add loading assistant message
      store.addAssistantMessage(convId, '');
      const assistantMsgId = getLastMessageId(convId);
      if (!assistantMsgId) return;
      store.setMessageLoading(convId, assistantMsgId, true);

      // Abort any in-flight request
      abortRef.current?.abort();
      abortRef.current = new AbortController();

      try {
        const signal = abortRef.current.signal;
        let answer: string;

        switch (actionId) {
          case 'brief': {
            const res = await getBriefToday(signal);
            answer = formatQuickActionResponse(res);
            break;
          }
          case 'alerts': {
            const res = await getAlerts(signal);
            answer = formatQuickActionResponse(res);
            break;
          }
          case 'commitments': {
            const res = await getCommitments(signal);
            answer = formatQuickActionResponse(res);
            break;
          }
          case 'meeting-prep': {
            const res = await getMeetingPrep(signal);
            answer = formatQuickActionResponse(res);
            break;
          }
          case 'timeline': {
            const res = await postTimeline({}, signal);
            answer = formatQuickActionResponse(res);
            break;
          }
          default:
            answer = `Nieznana akcja: ${actionId}`;
        }

        store.updateAssistantMessage(convId, assistantMsgId, answer);
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        const message = err instanceof Error ? err.message : 'Błąd';
        store.setMessageError(convId, assistantMsgId, message);
        store.setMessageLoading(convId, assistantMsgId, false);
      }
    },
    [store],
  );

  const abort = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  return {
    ...store,
    sendMessage,
    handleQuickAction,
    abort,
  } as const;
}
