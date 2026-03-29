'use client';

import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { cn } from '../../lib/utils';

interface MetricCardProps {
  label: string;
  value: number | string;
  currency?: string;
  period?: string;
  source?: string;
  trend?: 'up' | 'down' | 'stable';
}

const TREND_CONFIG = {
  up: { Icon: TrendingUp, className: 'text-emerald-400' },
  down: { Icon: TrendingDown, className: 'text-red-400' },
  stable: { Icon: Minus, className: 'text-[var(--text-muted)]' },
} as const;

export function MetricCard({
  label,
  value,
  currency,
  period,
  source,
  trend,
}: MetricCardProps) {
  const trendConfig = trend ? TREND_CONFIG[trend] : null;

  return (
    <div className="rounded-lg bg-[var(--surface)] border border-[var(--border)] p-4 flex flex-col justify-between">
      <p className="text-sm text-[var(--text-secondary)]">{label}</p>
      <div className="mt-2 flex items-baseline gap-1.5">
        <span className="text-2xl font-bold text-[var(--text)]">
          {typeof value === 'number'
            ? value.toLocaleString('pl-PL')
            : value}
        </span>
        {currency && (
          <span className="text-sm text-[var(--text-secondary)]">{currency}</span>
        )}
        {trendConfig && (
          <trendConfig.Icon className={cn('ml-1 h-4 w-4', trendConfig.className)} />
        )}
      </div>
      {(period || source) && (
        <p className="mt-1.5 text-xs text-[var(--text-muted)]">
          {[period, source].filter(Boolean).join(' · ')}
        </p>
      )}
    </div>
  );
}
