'use client';

import { useMemo } from 'react';
import { Calendar, AlertTriangle } from 'lucide-react';
import type { ComplianceDeadline } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';
import { ComplianceBadge } from './compliance-badge';
import { AreaFilter } from './area-filter';

export interface DeadlineCalendarProps {
  deadlines: ComplianceDeadline[];
  overdueDeadlines: ComplianceDeadline[];
  isLoading?: boolean;
  daysAhead: number;
  areaFilter: string | null;
  onDaysAheadChange: (v: number) => void;
  onAreaChange: (v: string | null) => void;
}

const DAYS_OPTIONS = [7, 14, 30, 60, 90] as const;

function formatDate(dateStr: string): string {
  try {
    return new Intl.DateTimeFormat('pl-PL', {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
    }).format(new Date(dateStr));
  } catch {
    return dateStr;
  }
}

function getDaysRemaining(dateStr: string): number {
  const date = new Date(dateStr);
  const now = new Date();
  return Math.floor((date.getTime() - now.getTime()) / 86_400_000);
}

function getDaysRemainingText(dateStr: string): string {
  const days = getDaysRemaining(dateStr);
  if (days < -1) return `${Math.abs(days)} dni temu`;
  if (days === -1) return 'wczoraj';
  if (days === 0) return 'dzisiaj';
  if (days === 1) return 'jutro';
  return `za ${days} dni`;
}

function getDateColor(dateStr: string): string {
  const days = getDaysRemaining(dateStr);
  if (days < 0) return '#ef4444';
  if (days <= 3) return '#f97316';
  if (days <= 7) return '#eab308';
  return 'var(--text)';
}

function getWeekGroup(dateStr: string): string {
  const now = new Date();
  const date = new Date(dateStr);
  const startOfWeek = new Date(now);
  startOfWeek.setDate(now.getDate() - now.getDay() + 1); // Monday
  startOfWeek.setHours(0, 0, 0, 0);

  const diffDays = Math.floor((date.getTime() - startOfWeek.getTime()) / 86_400_000);

  if (diffDays < 7) return 'Ten tydzień';
  if (diffDays < 14) return 'Następny tydzień';
  if (diffDays < 21) return 'Za 2 tygodnie';
  if (diffDays < 28) return 'Za 3 tygodnie';
  return 'Później';
}

function DeadlineItem({ deadline }: { deadline: ComplianceDeadline }) {
  const isOverdue = (deadline.days_overdue ?? 0) > 0 || getDaysRemaining(deadline.date) < 0;

  return (
    <div
      className="flex items-center gap-4 rounded-lg border px-4 py-3 transition-colors hover:bg-[var(--surface-hover)]"
      style={{ borderColor: 'var(--border)' }}
    >
      <div className="min-w-[100px] text-sm font-medium" style={{ color: getDateColor(deadline.date) }}>
        {formatDate(deadline.date)}
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-[var(--text)] truncate">{deadline.title}</div>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        <ComplianceBadge type="deadline" value={deadline.type} size="sm" />
        <ComplianceBadge type="status" value={deadline.status} size="sm" />
        <ComplianceBadge type="area" value={deadline.area_code} size="sm" />
      </div>
      <div
        className="min-w-[90px] text-right text-xs font-medium"
        style={{ color: isOverdue ? '#ef4444' : 'var(--text-secondary)' }}
      >
        {getDaysRemainingText(deadline.date)}
      </div>
    </div>
  );
}

function SkeletonItems() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 5 }).map((_, i) => (
        <div
          key={i}
          className="flex items-center gap-4 rounded-lg border px-4 py-3"
          style={{ borderColor: 'var(--border)' }}
        >
          <div className="h-4 w-24 rounded bg-[var(--surface)] animate-pulse" />
          <div className="h-4 flex-1 rounded bg-[var(--surface)] animate-pulse" />
          <div className="h-4 w-20 rounded bg-[var(--surface)] animate-pulse" />
        </div>
      ))}
    </div>
  );
}

export function DeadlineCalendar({
  deadlines,
  overdueDeadlines,
  isLoading,
  daysAhead,
  areaFilter,
  onDaysAheadChange,
  onAreaChange,
}: DeadlineCalendarProps) {
  const grouped = useMemo(() => {
    const items = deadlines ?? [];
    const groups: Record<string, ComplianceDeadline[]> = {};
    for (const d of items) {
      const key = getWeekGroup(d.date);
      if (!groups[key]) groups[key] = [];
      groups[key].push(d);
    }
    return groups;
  }, [deadlines]);

  const overdueList = useMemo(() => {
    const items = overdueDeadlines ?? [];
    return [...items].sort((a, b) => (b.days_overdue ?? 0) - (a.days_overdue ?? 0));
  }, [overdueDeadlines]);

  const groupOrder = ['Ten tydzień', 'Następny tydzień', 'Za 2 tygodnie', 'Za 3 tygodnie', 'Później'];

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1.5">
          {DAYS_OPTIONS.map((d) => (
            <button
              key={d}
              onClick={() => onDaysAheadChange(d)}
              className={cn(
                'rounded-full px-3 py-1 text-xs font-medium transition-colors',
                daysAhead === d
                  ? 'bg-[var(--accent)] text-white'
                  : 'bg-[var(--surface)] text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]',
              )}
            >
              {d} dni
            </button>
          ))}
        </div>
        <AreaFilter value={areaFilter} onChange={onAreaChange} className="w-48" />
      </div>

      {isLoading ? (
        <SkeletonItems />
      ) : (
        <>
          {/* Overdue section */}
          {overdueList.length > 0 && (
            <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-4">
              <div className="mb-3 flex items-center gap-2">
                <AlertTriangle size={16} className="text-red-400" />
                <h3 className="text-sm font-semibold text-red-400">
                  Zaległe ({overdueList.length})
                </h3>
              </div>
              <div className="space-y-2">
                {overdueList.map((d) => (
                  <DeadlineItem key={d.id} deadline={d} />
                ))}
              </div>
            </div>
          )}

          {/* Upcoming grouped */}
          {groupOrder.map((group) => {
            const items = grouped[group];
            if (!items || items.length === 0) return null;
            return (
              <div key={group}>
                <h3 className="mb-2 text-sm font-semibold text-[var(--text-secondary)]">
                  {group}
                </h3>
                <div className="space-y-2">
                  {items.map((d) => (
                    <DeadlineItem key={d.id} deadline={d} />
                  ))}
                </div>
              </div>
            );
          })}

          {/* Empty state */}
          {overdueList.length === 0 && Object.keys(grouped).length === 0 && (
            <div className="flex flex-col items-center gap-2 py-16 text-[var(--text-secondary)]">
              <Calendar className="h-10 w-10 opacity-40" />
              <span className="text-sm">Brak terminów do wyświetlenia</span>
            </div>
          )}
        </>
      )}
    </div>
  );
}
