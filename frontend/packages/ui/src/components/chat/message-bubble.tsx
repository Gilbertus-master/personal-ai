'use client';

import { useState, useEffect } from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';
import { MarkdownRenderer } from './markdown-renderer';
import { SourcePanel } from './source-panel';
import type { SourceItem } from './source-card';

interface MessageMeta {
  latency_ms?: number;
  cached?: boolean;
}

export interface MessageBubbleMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: SourceItem[];
  meta?: MessageMeta;
  timestamp: string;
  isLoading?: boolean;
  error?: string;
}

interface MessageBubbleProps {
  message: MessageBubbleMessage;
  onRetry?: () => void;
}

function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString('pl-PL', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function LoadingSkeleton() {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setElapsed((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-2">
      <div className="flex flex-col gap-2">
        <div className="h-3 w-3/4 rounded bg-[var(--border)] animate-pulse" />
        <div className="h-3 w-1/2 rounded bg-[var(--border)] animate-pulse" />
        <div className="h-3 w-2/3 rounded bg-[var(--border)] animate-pulse" />
      </div>
      <p className="text-xs text-[var(--text-secondary)] mt-2">
        Myślę... {elapsed}s
      </p>
    </div>
  );
}

export function MessageBubble({ message, onRetry }: MessageBubbleProps) {
  const isUser = message.role === 'user';

  if (isUser) {
    return (
      <div className="flex justify-end group">
        <div
          className="max-w-[70%] rounded-2xl rounded-br-sm px-4 py-2.5 bg-[var(--accent)] text-white"
          title={formatTimestamp(message.timestamp)}
        >
          <p className="text-sm whitespace-pre-wrap break-words">{message.content}</p>
        </div>
      </div>
    );
  }

  // Assistant message
  const hasError = Boolean(message.error);

  return (
    <div className="flex justify-start group">
      <div
        className={`w-full rounded-2xl rounded-bl-sm px-4 py-3 bg-[var(--surface)] ${
          hasError ? 'border border-[var(--danger)]' : ''
        }`}
        title={formatTimestamp(message.timestamp)}
      >
        {message.isLoading && !message.content ? (
          <LoadingSkeleton />
        ) : (
          <>
            <div className="text-sm text-[var(--text)]">
              <MarkdownRenderer content={message.content} />
            </div>

            {message.sources && message.sources.length > 0 && (
              <SourcePanel sources={message.sources} />
            )}
          </>
        )}

        {hasError && (
          <div className="flex items-center gap-2 mt-2 text-[var(--danger)]">
            <AlertCircle size={14} />
            <span className="text-xs">{message.error}</span>
            {onRetry && (
              <button
                onClick={onRetry}
                className="ml-auto flex items-center gap-1 text-xs text-[var(--accent)] hover:text-[var(--accent-hover)] transition-colors"
              >
                <RefreshCw size={12} />
                Spróbuj ponownie
              </button>
            )}
          </div>
        )}

        {message.meta && !message.isLoading && (
          <div className="flex items-center gap-2 mt-1.5 text-[10px] text-[var(--text-secondary)]">
            {message.meta.latency_ms != null && (
              <span>{(message.meta.latency_ms / 1000).toFixed(1)}s</span>
            )}
            {message.meta.cached && (
              <span className="px-1 py-0.5 rounded bg-[var(--surface-hover)] text-[var(--text-secondary)]">
                cache
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
