'use client';

import type { StrategicGoal } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';

interface GoalCardProps {
  goal: StrategicGoal;
  onClick?: () => void;
}

const STATUS_BADGE: Record<StrategicGoal['status'], { label: string; className: string }> = {
  on_track: { label: 'Na dobrej drodze', className: 'bg-emerald-500/20 text-emerald-400' },
  at_risk: { label: 'Zagrożony', className: 'bg-amber-500/20 text-amber-400' },
  behind: { label: 'Opóźniony', className: 'bg-red-500/20 text-red-400' },
  achieved: { label: 'Osiągnięty', className: 'bg-blue-500/20 text-blue-400' },
  cancelled: { label: 'Anulowany', className: 'bg-zinc-500/20 text-zinc-400' },
};

const AREA_BADGE: Record<StrategicGoal['area'], { label: string; className: string }> = {
  business: { label: 'Biznes', className: 'bg-indigo-500/20 text-indigo-400' },
  trading: { label: 'Trading', className: 'bg-cyan-500/20 text-cyan-400' },
  operations: { label: 'Operacje', className: 'bg-orange-500/20 text-orange-400' },
  people: { label: 'Ludzie', className: 'bg-pink-500/20 text-pink-400' },
  technology: { label: 'Technologia', className: 'bg-violet-500/20 text-violet-400' },
  wellbeing: { label: 'Wellbeing', className: 'bg-teal-500/20 text-teal-400' },
};

function daysRemaining(deadline: string): number {
  const diff = new Date(deadline).getTime() - Date.now();
  return Math.ceil(diff / (1000 * 60 * 60 * 24));
}

export function GoalCard({ goal, onClick }: GoalCardProps) {
  const status = STATUS_BADGE[goal.status];
  const area = AREA_BADGE[goal.area];
  const days = daysRemaining(goal.deadline);
  const pct = Math.min(goal.pct_complete, 100);

  return (
    <div
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onClick={onClick}
      onKeyDown={(e) => {
        if (onClick && (e.key === 'Enter' || e.key === ' ')) {
          e.preventDefault();
          onClick();
        }
      }}
      className={cn(
        'rounded-lg bg-[var(--surface)] border border-[var(--border)] p-4 space-y-3',
        onClick && 'cursor-pointer hover:bg-[var(--surface-hover)] transition-colors',
      )}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-medium text-[var(--text)] leading-tight">{goal.title}</h3>
        <span className={cn('shrink-0 rounded-full px-2 py-0.5 text-xs font-medium', status.className)}>
          {status.label}
        </span>
      </div>

      {/* Badges */}
      <div className="flex flex-wrap gap-1.5">
        <span className={cn('rounded px-1.5 py-0.5 text-xs font-medium', area.className)}>
          {area.label}
        </span>
        <span className="rounded bg-[var(--bg)] px-1.5 py-0.5 text-xs text-[var(--text-secondary)]">
          {goal.company}
        </span>
      </div>

      {/* Progress */}
      <div className="space-y-1">
        <div className="flex justify-between text-xs text-[var(--text-secondary)]">
          <span>
            {goal.current_value} / {goal.target_value} {goal.unit}
          </span>
          <span>{pct.toFixed(0)}%</span>
        </div>
        <div className="h-2 w-full rounded-full bg-[var(--bg)]">
          <div
            className="h-full rounded-full bg-[var(--accent)] transition-all"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {/* Deadline */}
      <p className="text-xs text-[var(--text-muted)]">
        Termin: {goal.deadline}
        {days > 0 ? ` (${days} dni)` : days === 0 ? ' (dziś!)' : ` (${Math.abs(days)} dni temu)`}
      </p>
    </div>
  );
}
