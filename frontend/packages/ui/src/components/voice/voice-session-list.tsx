'use client';

import { Plus } from 'lucide-react';
import { VoiceSessionItem } from './voice-session-item';

export interface VoiceSession {
  id: string;
  title: string;
  startedAt: string;
  messages: Array<{ role: string }>;
}

export interface VoiceSessionListProps {
  sessions: VoiceSession[];
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onDeleteSession: (id: string) => void;
  onNewSession: () => void;
}

export function VoiceSessionList({
  sessions,
  activeSessionId,
  onSelectSession,
  onDeleteSession,
  onNewSession,
}: VoiceSessionListProps) {
  return (
    <div className="flex h-full flex-col border-r border-[var(--border)] bg-[var(--bg)]">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
        <h2 className="text-sm font-semibold text-[var(--text)]">Historia</h2>
        <button
          type="button"
          onClick={onNewSession}
          className="flex h-7 w-7 items-center justify-center rounded-md text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text)] transition-colors"
          aria-label="Nowa sesja"
        >
          <Plus size={16} />
        </button>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto p-2">
        {sessions.length === 0 ? (
          <p className="px-3 py-4 text-center text-xs text-[var(--text-muted)]">
            Brak sesji głosowych
          </p>
        ) : (
          <div className="flex flex-col gap-0.5">
            {sessions.map((session) => (
              <VoiceSessionItem
                key={session.id}
                id={session.id}
                title={session.title}
                startedAt={session.startedAt}
                messageCount={session.messages.length}
                isActive={session.id === activeSessionId}
                onSelect={() => onSelectSession(session.id)}
                onDelete={() => onDeleteSession(session.id)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
