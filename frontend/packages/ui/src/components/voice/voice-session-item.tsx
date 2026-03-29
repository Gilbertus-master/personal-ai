'use client';

import { Trash2, MessageSquare } from 'lucide-react';
import { cn } from '../../lib/utils';

export interface VoiceSessionItemProps {
  id: string;
  title: string;
  startedAt: string;
  messageCount: number;
  isActive: boolean;
  onSelect: () => void;
  onDelete: () => void;
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString('pl-PL', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return '';
  }
}

export function VoiceSessionItem({
  title,
  startedAt,
  messageCount,
  isActive,
  onSelect,
  onDelete,
}: VoiceSessionItemProps) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        'group flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors',
        isActive
          ? 'bg-[var(--accent)]/10'
          : 'hover:bg-[var(--surface-hover)]',
      )}
    >
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-[var(--text)]">{title}</p>
        <p className="text-xs text-[var(--text-muted)]">{formatDate(startedAt)}</p>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        <span className="flex items-center gap-1 text-xs text-[var(--text-muted)]">
          <MessageSquare size={12} />
          {messageCount}
        </span>

        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          className="flex h-6 w-6 items-center justify-center rounded text-[var(--text-muted)] opacity-0 transition-opacity hover:text-[var(--danger)] group-hover:opacity-100"
          aria-label="Usuń sesję"
        >
          <Trash2 size={14} />
        </button>
      </div>
    </button>
  );
}
