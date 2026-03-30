'use client';

import { useState, type ReactNode } from 'react';
import { TrendingUp, TrendingDown, Minus, ChevronRight } from 'lucide-react';
import { cn } from '../../lib/utils';

interface KpiCardProps {
  label: string;
  value: number | string;
  icon?: ReactNode;
  trend?: 'up' | 'down' | 'flat';
  trendValue?: string;
  color?: 'default' | 'success' | 'warning' | 'danger';
  isLoading?: boolean;
  onClick?: () => void;
}

const VALUE_COLOR_MAP = {
  default: 'text-[var(--text)]',
  success: 'text-emerald-400',
  warning: 'text-amber-400',
  danger: 'text-red-400',
} as const;

const TREND_CONFIG = {
  up: { Icon: TrendingUp, className: 'text-emerald-400' },
  down: { Icon: TrendingDown, className: 'text-red-400' },
  flat: { Icon: Minus, className: 'text-[var(--text-muted)]' },
} as const;

export function KpiCard({
  label,
  value,
  icon,
  trend,
  trendValue,
  color = 'default',
  isLoading = false,
  onClick,
}: KpiCardProps) {
  const [hovered, setHovered] = useState(false);
  if (isLoading) {
    return (
      <div className="rounded-lg bg-[var(--surface)] border border-[var(--border)] p-4">
        <div className="flex items-start justify-between">
          <div className="h-5 w-5 animate-pulse rounded bg-[var(--bg-hover)]" />
        </div>
        <div className="mt-3 h-7 w-16 animate-pulse rounded bg-[var(--bg-hover)]" />
        <div className="mt-1 h-4 w-24 animate-pulse rounded bg-[var(--bg-hover)]" />
        <div className="mt-2 h-4 w-12 animate-pulse rounded bg-[var(--bg-hover)]" />
      </div>
    );
  }

  const trendConfig = trend ? TREND_CONFIG[trend] : null;

  return (
    <div
      className={cn(
        'rounded-lg bg-[var(--surface)] border border-[var(--border)] p-4 flex flex-col justify-between relative transition-all',
        onClick && 'cursor-pointer hover:ring-1 hover:ring-[var(--accent)] hover:border-[var(--accent)]',
      )}
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {icon && (
        <div className="text-[var(--text-muted)] mb-2 [&>svg]:h-5 [&>svg]:w-5">
          {icon}
        </div>
      )}
      <div>
        <p className={cn('text-2xl font-bold', VALUE_COLOR_MAP[color])}>
          {value}
        </p>
        <p className="text-sm text-[var(--text-secondary)]">{label}</p>
      </div>
      {trendConfig && (
        <div className={cn('flex items-center gap-1 mt-2 text-xs', trendConfig.className)}>
          <trendConfig.Icon className="h-3.5 w-3.5" />
          {trendValue && <span>{trendValue}</span>}
        </div>
      )}
      {onClick && hovered && (
        <ChevronRight className="absolute bottom-2 right-2 h-3 w-3 text-[var(--accent)]" />
      )}
    </div>
  );
}
