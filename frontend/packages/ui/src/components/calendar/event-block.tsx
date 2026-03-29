'use client';

import { Video, AlertTriangle } from 'lucide-react';
import type { CalendarEvent } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';

export interface EventBlockProps {
  event: CalendarEvent;
  hasConflict?: boolean;
  onClick?: (id: string) => void;
  compact?: boolean;
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString('pl-PL', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Europe/Warsaw',
  });
}

export function EventBlock({
  event,
  hasConflict = false,
  onClick,
  compact = false,
}: EventBlockProps) {
  const startTime = formatTime(event.start);
  const endTime = formatTime(event.end);

  return (
    <button
      type="button"
      onClick={() => onClick?.(event.id)}
      className={cn(
        'w-full rounded-md px-2 py-1 text-left text-xs transition-colors',
        'hover:brightness-110 cursor-pointer',
        hasConflict && 'ring-2 ring-[var(--danger)]',
      )}
      style={{
        backgroundColor: hasConflict
          ? 'color-mix(in srgb, var(--danger) 15%, var(--surface))'
          : 'color-mix(in srgb, var(--accent) 20%, var(--surface))',
        borderLeft: `3px solid ${hasConflict ? 'var(--danger)' : 'var(--accent)'}`,
        color: 'var(--text)',
      }}
    >
      <div className="flex items-center gap-1">
        <span
          className={cn('font-medium truncate', compact ? 'text-[10px]' : 'text-xs')}
        >
          {event.subject}
        </span>
        {event.is_online && (
          <Video
            size={compact ? 10 : 12}
            style={{ color: 'var(--accent)', flexShrink: 0 }}
          />
        )}
        {hasConflict && (
          <AlertTriangle
            size={compact ? 10 : 12}
            style={{ color: 'var(--danger)', flexShrink: 0 }}
          />
        )}
      </div>
      {!compact && (
        <span className="text-[10px]" style={{ color: 'var(--text-secondary)' }}>
          {startTime} – {endTime}
        </span>
      )}
    </button>
  );
}
