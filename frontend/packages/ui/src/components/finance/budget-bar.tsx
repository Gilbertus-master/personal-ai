'use client';

import { cn } from '../../lib/utils';

interface BudgetBarProps {
  category: string;
  planned: number;
  actual: number;
  pct: number;
  currency?: string;
}

function getBarColor(pct: number): string {
  if (pct > 80) return 'bg-red-500';
  if (pct > 60) return 'bg-amber-500';
  return 'bg-emerald-500';
}

function getBadgeColor(pct: number): string {
  if (pct > 80) return 'bg-red-500/20 text-red-400';
  if (pct > 60) return 'bg-amber-500/20 text-amber-400';
  return 'bg-emerald-500/20 text-emerald-400';
}

function formatAmount(value: number, currency: string): string {
  return `${value.toLocaleString('pl-PL', { maximumFractionDigits: 0 })} ${currency}`;
}

export function BudgetBar({
  category,
  planned,
  actual,
  pct,
  currency = 'PLN',
}: BudgetBarProps) {
  const fillWidth = Math.min(pct, 100);

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-[var(--text)]">{category}</span>
        <div className="flex items-center gap-2">
          <span className="text-[var(--text-secondary)]">
            {formatAmount(actual, currency)} / {formatAmount(planned, currency)}
          </span>
          <span
            className={cn(
              'rounded-full px-2 py-0.5 text-xs font-medium',
              getBadgeColor(pct),
            )}
          >
            {pct.toFixed(0)}%
          </span>
        </div>
      </div>
      <div className="h-2.5 w-full rounded-full bg-[var(--surface)]">
        <div
          className={cn('h-full rounded-full transition-all', getBarColor(pct))}
          style={{ width: `${fillWidth}%` }}
        />
      </div>
    </div>
  );
}
