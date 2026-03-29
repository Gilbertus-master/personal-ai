'use client';

import type { CalendarEvent, CalendarConflict } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';
import { EventBlock } from './event-block';

export interface DayColumnProps {
  date: string;
  events: CalendarEvent[];
  conflicts: CalendarConflict[];
  onEventClick?: (id: string) => void;
}

const DAY_NAMES = ['Ndz', 'Pon', 'Wt', 'Śr', 'Czw', 'Pt', 'Sob'];
const START_HOUR = 7;
const END_HOUR = 21;
const TOTAL_MINUTES = (END_HOUR - START_HOUR) * 60;

function isToday(dateStr: string): boolean {
  const d = new Date(dateStr + 'T00:00:00');
  const now = new Date();
  return (
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  );
}

function formatDate(dateStr: string): { dayName: string; dayMonth: string } {
  const d = new Date(dateStr + 'T00:00:00');
  return {
    dayName: DAY_NAMES[d.getDay()],
    dayMonth: `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}`,
  };
}

function getEventPosition(event: CalendarEvent): { top: number; height: number } {
  const start = new Date(event.start);
  const end = new Date(event.end);
  const startMin =
    (start.getHours() - START_HOUR) * 60 + start.getMinutes();
  const endMin = (end.getHours() - START_HOUR) * 60 + end.getMinutes();

  const top = Math.max(0, (startMin / TOTAL_MINUTES) * 100);
  const height = Math.max(2, ((endMin - startMin) / TOTAL_MINUTES) * 100);

  return { top, height };
}

function hasConflict(event: CalendarEvent, conflicts: CalendarConflict[]): boolean {
  return conflicts.some(
    (c) => c.event_a.id === event.id || c.event_b.id === event.id,
  );
}

/** Group overlapping events into columns for side-by-side rendering. */
function layoutEvents(
  events: CalendarEvent[],
): { event: CalendarEvent; col: number; totalCols: number }[] {
  if (events.length === 0) return [];

  const sorted = [...events].sort(
    (a, b) => new Date(a.start).getTime() - new Date(b.start).getTime(),
  );

  const groups: CalendarEvent[][] = [];
  let currentGroup: CalendarEvent[] = [];
  let groupEnd = -Infinity;

  for (const ev of sorted) {
    const evStart = new Date(ev.start).getTime();
    const evEnd = new Date(ev.end).getTime();
    if (evStart < groupEnd) {
      currentGroup.push(ev);
      groupEnd = Math.max(groupEnd, evEnd);
    } else {
      if (currentGroup.length > 0) groups.push(currentGroup);
      currentGroup = [ev];
      groupEnd = evEnd;
    }
  }
  if (currentGroup.length > 0) groups.push(currentGroup);

  const result: { event: CalendarEvent; col: number; totalCols: number }[] = [];
  for (const group of groups) {
    group.forEach((ev, idx) => {
      result.push({ event: ev, col: idx, totalCols: group.length });
    });
  }
  return result;
}

export function DayColumn({ date, events, conflicts, onEventClick }: DayColumnProps) {
  const { dayName, dayMonth } = formatDate(date);
  const today = isToday(date);
  const laid = layoutEvents(events);

  return (
    <div className="flex flex-col min-w-0 flex-1">
      {/* Header */}
      <div
        className={cn(
          'text-center py-2 text-xs font-medium border-b',
          today && 'border-b-2',
        )}
        style={{
          borderColor: today ? 'var(--accent)' : 'var(--border)',
          color: today ? 'var(--accent)' : 'var(--text)',
          backgroundColor: 'var(--surface)',
        }}
      >
        <div>{dayName}</div>
        <div style={{ color: today ? 'var(--accent)' : 'var(--text-secondary)' }}>
          {dayMonth}
        </div>
      </div>

      {/* Events area */}
      <div className="relative flex-1" style={{ minHeight: 0 }}>
        {laid.map(({ event, col, totalCols }) => {
          const pos = getEventPosition(event);
          const widthPct = 100 / totalCols;
          const leftPct = col * widthPct;

          return (
            <div
              key={event.id}
              className="absolute px-0.5"
              style={{
                top: `${pos.top}%`,
                height: `${pos.height}%`,
                left: `${leftPct}%`,
                width: `${widthPct}%`,
              }}
            >
              <EventBlock
                event={event}
                hasConflict={hasConflict(event, conflicts)}
                onClick={onEventClick}
                compact={totalCols > 1}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}
