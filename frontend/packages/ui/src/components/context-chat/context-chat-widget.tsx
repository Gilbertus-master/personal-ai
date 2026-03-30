'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import {
  MessageSquare,
  X,
  Send,
  Loader2,
  Sparkles,
} from 'lucide-react';
import { cn } from '../../lib/utils';
import { MarkdownRenderer } from '../chat/markdown-renderer';
import { askGilbertus } from '@gilbertus/api-client';

export type ChatContext =
  | 'general'
  | 'brief'
  | 'compliance'
  | 'market'
  | 'finance'
  | 'intelligence'
  | 'people'
  | 'process'
  | 'decisions'
  | 'calendar'
  | 'documents'
  | 'voice'
  | 'admin';

interface ContextMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

const CONTEXT_CONFIG: Record<ChatContext, {
  label: string;
  prefix: string;
  suggestions: string[];
}> = {
  general: {
    label: 'Gilbertus',
    prefix: '',
    suggestions: [
      'Co powinienem dziś zrobić?',
      'Jakie mam otwarte zobowiązania?',
      'Pokaż najważniejsze alerty',
    ],
  },
  brief: {
    label: 'Brief',
    prefix: 'W kontekście porannego briefu: ',
    suggestions: [
      'Podsumuj najważniejsze punkty briefu',
      'Jakie zadania są najpilniejsze?',
      'Jakie ryzyka wynikają z briefu?',
    ],
  },
  compliance: {
    label: 'Compliance',
    prefix: 'W kontekście compliance i regulacji: ',
    suggestions: [
      'Jakie obowiązki są zaległe?',
      'Pokaż status obszarów compliance',
      'Jakie ryzyka regulacyjne są najwyższe?',
    ],
  },
  market: {
    label: 'Rynek',
    prefix: 'W kontekście rynku energetycznego i konkurencji: ',
    suggestions: [
      'Jakie sygnały rynkowe są najważniejsze?',
      'Co robi konkurencja?',
      'Jakie alerty rynkowe są aktywne?',
    ],
  },
  finance: {
    label: 'Finanse',
    prefix: 'W kontekście finansów REH/REF: ',
    suggestions: [
      'Jaki jest status budżetu?',
      'Pokaż koszty API',
      'Jakie cele finansowe są zagrożone?',
    ],
  },
  intelligence: {
    label: 'Wywiad',
    prefix: 'W kontekście wywiadu biznesowego: ',
    suggestions: [
      'Jakie szanse biznesowe są dostępne?',
      'Pokaż predykcje',
      'Jakie nieefektywności wykryto?',
    ],
  },
  people: {
    label: 'Ludzie',
    prefix: 'W kontekście ludzi i relacji w organizacji: ',
    suggestions: [
      'Kto wymaga uwagi?',
      'Jakie zobowiązania są otwarte?',
      'Pokaż luki komunikacyjne',
    ],
  },
  process: {
    label: 'Procesy',
    prefix: 'W kontekście procesów biznesowych i technologii: ',
    suggestions: [
      'Jakie procesy można zoptymalizować?',
      'Pokaż tech radar',
      'Jakie aplikacje mają najwyższy koszt?',
    ],
  },
  decisions: {
    label: 'Decyzje',
    prefix: 'W kontekście dziennika decyzji: ',
    suggestions: [
      'Jakie decyzje czekają na follow-up?',
      'Pokaż wzorce decyzyjne',
      'Jakie outcomes trzeba ocenić?',
    ],
  },
  calendar: {
    label: 'Kalendarz',
    prefix: 'W kontekście kalendarza i spotkań: ',
    suggestions: [
      'Jakie spotkania mam dziś?',
      'Które spotkania mają niski ROI?',
      'Przygotuj briefing na następne spotkanie',
    ],
  },
  documents: {
    label: 'Dokumenty',
    prefix: 'W kontekście dokumentów i źródeł danych: ',
    suggestions: [
      'Pokaż ostatnio zaimportowane dokumenty',
      'Wyszukaj dokumenty o...',
      'Jaki jest status ingestion?',
    ],
  },
  voice: {
    label: 'Głos',
    prefix: 'W kontekście nagrań głosowych i transkrypcji: ',
    suggestions: [
      'Jakie nagrania zostały przetworzone?',
      'Podsumuj ostatnią rozmowę',
      'Jaki jest status Plaud?',
    ],
  },
  admin: {
    label: 'Admin',
    prefix: 'W kontekście administracji systemu Gilbertus: ',
    suggestions: [
      'Jaki jest status systemu?',
      'Pokaż błędy z ostatnich 24h',
      'Jakie crony działają?',
    ],
  },
};

interface ContextChatWidgetProps {
  context?: ChatContext;
}

export function ContextChatWidget({ context = 'general' }: ContextChatWidgetProps) {
  const [mounted, setMounted] = useState(false);
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => { setMounted(true); }, []);
  const [messages, setMessages] = useState<ContextMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const config = CONTEXT_CONFIG[context];

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
      inputRef.current?.focus();
    }
  }, [isOpen, messages.length, scrollToBottom]);

  const handleSend = async (text?: string) => {
    const msg = (text ?? input).trim();
    if (!msg || isLoading) return;

    const userMessage: ContextMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: msg,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    abortRef.current = new AbortController();

    try {
      const fullQuery = config.prefix + msg;
      const response = await askGilbertus(
        {
          query: fullQuery,
          channel: `context-chat-${context}`,
          answer_length: 'medium',
          answer_style: 'auto',
        },
        abortRef.current.signal,
      );

      const assistantMessage: ContextMessage = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: response.answer,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== 'AbortError') {
        const errorMessage: ContextMessage = {
          id: `error-${Date.now()}`,
          role: 'assistant',
          content: `Błąd: ${err.message}`,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, errorMessage]);
      }
    } finally {
      setIsLoading(false);
      abortRef.current = null;
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (!mounted) return null;

  return (
    <>
      {/* Floating toggle button */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="fixed bottom-6 right-6 z-50 flex h-12 w-12 items-center justify-center rounded-full bg-[var(--accent)] text-white shadow-lg hover:bg-[var(--accent-hover)] transition-all hover:scale-105"
          aria-label="Otwórz chat z Gilbertusem"
        >
          <MessageSquare className="h-5 w-5" />
        </button>
      )}

      {/* Chat panel */}
      {isOpen && (
        <div className="fixed bottom-6 right-6 z-50 flex h-[520px] w-[400px] flex-col rounded-xl border border-[var(--border)] bg-[var(--surface)] shadow-2xl">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-[var(--accent)]" />
              <span className="text-sm font-semibold text-[var(--text)]">
                Gilbertus
              </span>
              {context !== 'general' && (
                <span className="rounded-full bg-[var(--accent)]/10 px-2 py-0.5 text-[10px] font-medium text-[var(--accent)]">
                  {config.label}
                </span>
              )}
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="rounded-md p-1 text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.length === 0 ? (
              <div className="space-y-3">
                <p className="text-xs text-[var(--text-secondary)]">
                  Zadaj pytanie Gilbertusowi{context !== 'general' ? ` w kontekście: ${config.label}` : ''}.
                </p>
                <div className="space-y-2">
                  {config.suggestions.map((suggestion) => (
                    <button
                      key={suggestion}
                      onClick={() => handleSend(suggestion)}
                      className="block w-full rounded-lg border border-[var(--border)] px-3 py-2 text-left text-xs text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text)] transition-colors"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((msg) => (
                <div
                  key={msg.id}
                  className={cn(
                    'flex',
                    msg.role === 'user' ? 'justify-end' : 'justify-start',
                  )}
                >
                  <div
                    className={cn(
                      'max-w-[85%] rounded-lg px-3 py-2',
                      msg.role === 'user'
                        ? 'bg-[var(--accent)] text-white'
                        : 'bg-[var(--bg)] text-[var(--text)] border border-[var(--border)]',
                    )}
                  >
                    {msg.role === 'assistant' ? (
                      <div className="text-xs [&_p]:mb-1 [&_ul]:ml-3 [&_ol]:ml-3 [&_li]:text-xs [&_h1]:text-sm [&_h2]:text-xs [&_h3]:text-xs [&_pre]:text-[10px]">
                        <MarkdownRenderer content={msg.content} />
                      </div>
                    ) : (
                      <p className="text-xs">{msg.content}</p>
                    )}
                  </div>
                </div>
              ))
            )}

            {isLoading && (
              <div className="flex justify-start">
                <div className="flex items-center gap-2 rounded-lg bg-[var(--bg)] border border-[var(--border)] px-3 py-2">
                  <Loader2 className="h-3 w-3 animate-spin text-[var(--accent)]" />
                  <span className="text-xs text-[var(--text-secondary)]">Myślę...</span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="border-t border-[var(--border)] p-3">
            <div className="flex items-end gap-2">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Zadaj pytanie..."
                rows={1}
                className="flex-1 resize-none rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-xs text-[var(--text)] placeholder:text-[var(--text-secondary)] focus:border-[var(--accent)] focus:outline-none"
              />
              <button
                onClick={() => handleSend()}
                disabled={!input.trim() || isLoading}
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--accent)] text-white disabled:opacity-50 hover:bg-[var(--accent-hover)] transition-colors"
              >
                <Send className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
