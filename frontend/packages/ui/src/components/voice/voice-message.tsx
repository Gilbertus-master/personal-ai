'use client';

import { Mic, Bot, Play } from 'lucide-react';
import { cn } from '../../lib/utils';

export interface VoiceMessageProps {
  role: 'user' | 'assistant';
  text: string;
  timestamp: string;
  audioUrl?: string;
  onPlayAudio?: (url: string) => void;
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}

export function VoiceMessage({ role, text, timestamp, audioUrl, onPlayAudio }: VoiceMessageProps) {
  const isUser = role === 'user';

  return (
    <div className={cn('group flex gap-3', isUser ? 'flex-row-reverse' : 'flex-row')}>
      {/* Avatar */}
      <div
        className={cn(
          'flex h-8 w-8 shrink-0 items-center justify-center rounded-full',
          isUser
            ? 'bg-[var(--accent)]/20 text-[var(--accent)]'
            : 'bg-[var(--surface)] text-[var(--text-secondary)]',
        )}
      >
        {isUser ? <Mic size={16} /> : <Bot size={16} />}
      </div>

      {/* Bubble */}
      <div
        className={cn(
          'max-w-[75%] rounded-xl px-4 py-2.5 transition-colors',
          isUser
            ? 'bg-[var(--accent)]/10 border-l-2 border-[var(--accent)]'
            : 'bg-[var(--surface)]',
          'group-hover:brightness-95',
        )}
      >
        <p className="whitespace-pre-wrap text-sm text-[var(--text)]">{text}</p>

        <div className="mt-1.5 flex items-center gap-2">
          <span className="text-xs text-[var(--text-muted)] opacity-0 transition-opacity group-hover:opacity-100">
            {formatTime(timestamp)}
          </span>

          {audioUrl && onPlayAudio && (
            <button
              type="button"
              onClick={() => onPlayAudio(audioUrl)}
              className="flex h-6 w-6 items-center justify-center rounded-full bg-[var(--accent)]/10 text-[var(--accent)] hover:bg-[var(--accent)]/20 transition-colors"
              aria-label="Odtwórz nagranie"
            >
              <Play size={12} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
