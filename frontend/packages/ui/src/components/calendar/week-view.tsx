'use client';

import { useMemo } from 'react';
import type { CalendarEvent, CalendarConflict } from '@gilbertus/api-client';
import { DayColumn } from './day-column';

export interface WeekViewProps {
  events: CalendarEvent[];
  conflicts: CalendarConflict[];
  weekOffset: number;
  onEventClick?: (id: string) => void;
  isLoading?: boolean;
}

const START_HOUR = 7;
const END_HOUR = 21;
const HOURS = Array.from({ length: END_HOUR - START_HOUR }, (_, i) => START_HOUR + i);

/** Get Monday-based week dates for a given weekOffset (0 = current week). */
function getWeekDates(weekOffset: number): string[] {
  const now = new Date();
  const day = now.getDay();
  const monday = new Date(now);
  monday.setDate(now.getDate() - ((day + 6) % 7) + weekOffset * 7);
  monday.setHours(0, 0, 0, 0);

  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    return d.toISOString().slice(0, 10);
  });
}

function SkeletonGrid() {
  return (
    <div className="flex flex-1 gap-px animate-pulse" style={{ minHeight: 500 }}>
      <div className="w-14 shrink-0" />
      {Array.from({ length: 7 }, (_, i) => (
        <div
          key={i}
          className="flex-1 rounded"
          style={{ backgroundColor: 'var(--surface)' }}
        />
      ))}
    </div>
  );
}

export function WeekView({
  events,
  conflicts,
  weekOffset,
  onEventClick,
  isLoading = false,
}: WeekViewProps) {
  const weekDates = useMemo(() => getWeekDates(weekOffset), [weekOffset]);

  const eventsByDay = useMemo(() => {
    const map: Record<string, CalendarEvent[]> = {};
    for (const date of weekDates) map[date] = [];
    for (const ev of events) {
      const date = ev.start.slice(0, 10);
      if (map[date]) map[date].push(ev);
    }
    return map;
  }, [events, weekDates]);

  if (isLoading) return <SkeletonGrid />;

  return (
    <div className="flex flex-1 overflow-hidden rounded-lg border" style={{ borderColor: 'var(--border)', minHeight: 500 }}>
      {/* Time gutter */}
      <div className="w-14 shrink-0 pt-[52px]" style={{ borderRight: '1px solid var(--border)' }}>
        <div className="relative h-full">
          {HOURS.map((hour) => {
            const pct =
              ((hour - START_HOUR) / (END_HOUR - START_HOUR)) * 100;
            return (
              <div
                key={hour}
                className="absolute right-2 text-[10px] -translate-y-1/2"
                style={{ top: `${pct}%`, color: 'var(--text-secondary)' }}
              >
                {String(hour).padStart(2, '0')}:00
              </div>
            );
          })}
        </div>
      </div>

      {/* Day columns */}
      <div className="flex flex-1 relative">
        {/* Hour grid lines */}
        <div className="absolute inset-0 top-[52px] pointer-events-none">
          {HOURS.map((hour) => {
            const pct =
              ((hour - START_HOUR) / (END_HOUR - START_HOUR)) * 100;
            return (
              <div
                key={hour}
                className="absolute w-full"
                style={{
                  top: `${pct}%`,
                  borderTop: '1px solid var(--border)',
                  opacity: 0.5,
                }}
              />
            );
          })}
        </div>

        {weekDates.map((date) => (
          <DayColumn
            key={date}
            date={date}
            events={eventsByDay[date] ?? []}
            conflicts={conflicts}
            onEventClick={onEventClick}
          />
        ))}
      </div>
    </div>
  );
}
