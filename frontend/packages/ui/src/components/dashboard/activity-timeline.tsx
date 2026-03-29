'use client';

import { Clock, ChevronDown, ChevronUp } from 'lucide-react';
import type { TimelineEvent as TimelineEventType } from '@gilbertus/api-client';
import { TimelineEvent } from './timeline-event';

interface ActivityTimelineProps {
  events?: TimelineEventType[];
  isLoading?: boolean;
  error?: Error | null;
  filter?: string | null;
  onFilterChange?: (filter: string | null) => void;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
}

const EVENT_TYPE_OPTIONS = [
  { value: '', label: 'Wszystkie' },
  { value: 'meeting', label: 'Spotkania' },
  { value: 'decision', label: 'Decyzje' },
  { value: 'task', label: 'Zadania' },
  { value: 'email', label: 'Email' },
  { value: 'communication', label: 'Komunikacja' },
];

function LoadingSkeleton() {
  return (
    <div className="space-y-0">
      {Array.from({ length: 5 }).map((_, i) => (
        <div
          key={i}
          className="flex items-start gap-3 border-b border-[var(--border)] px-3 py-3 last:border-b-0"
        >
          <div className="mt-0.5 h-4 w-4 animate-pulse rounded bg-[var(--surface-hover)]" />
          <div className="flex-1 space-y-2">
            <div className="h-4 w-full animate-pulse rounded bg-[var(--surface-hover)]" />
            <div className="h-3 w-2/3 animate-pulse rounded bg-[var(--surface-hover)]" />
          </div>
          <div className="h-3 w-12 animate-pulse rounded bg-[var(--surface-hover)]" />
        </div>
      ))}
    </div>
  );
}

export function ActivityTimeline({
  events,
  isLoading,
  error,
  filter,
  onFilterChange,
  isCollapsed,
  onToggleCollapse,
}: ActivityTimelineProps) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)]">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[var(--border)] p-4">
        <div className="flex items-center gap-3">
          <h2 className="text-base font-semibold text-[var(--text)]">Oś czasu</h2>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={filter ?? ''}
            onChange={(e) =>
              onFilterChange?.(e.target.value || null)
            }
            className="rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-xs text-[var(--text)] outline-none focus:border-[var(--accent)]"
          >
            {EVENT_TYPE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          {onToggleCollapse && (
            <button
              onClick={onToggleCollapse}
              className="inline-flex items-center justify-center rounded-md p-2 text-[var(--text-secondary)] transition-colors hover:bg-[var(--surface-hover)]"
              aria-label={isCollapsed ? 'Rozwiń' : 'Zwiń'}
            >
              {isCollapsed ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      {!isCollapsed && (
        <>
          {error ? (
            <div className="flex flex-col items-center gap-2 p-8 text-red-500">
              <p className="text-sm">{error.message}</p>
            </div>
          ) : isLoading ? (
            <LoadingSkeleton />
          ) : events && events.length > 0 ? (
            <div className="max-h-[500px] overflow-y-auto">
              {events.map((event) => (
                <TimelineEvent key={event.event_id} event={event} />
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center gap-2 p-8 text-[var(--text-secondary)]">
              <Clock size={24} />
              <p className="text-sm">Brak wydarzeń w wybranym okresie</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
