'use client';

import { TrendingUp, TrendingDown, Minus, RefreshCw } from 'lucide-react';
import { cn } from '../../lib/utils';
import type { OrgHealth } from '@gilbertus/api-client';
import { ActionableItem } from '../shared/actionable-item';

interface OrgHealthBannerProps {
  data?: OrgHealth;
  isLoading?: boolean;
  onAssess?: () => void;
  isAssessing?: boolean;
}

const SCORE_COLOR = (score: number) =>
  score > 70 ? 'text-emerald-400' : score > 40 ? 'text-amber-400' : 'text-red-400';

const RING_STROKE = (score: number) =>
  score > 70 ? 'stroke-emerald-400' : score > 40 ? 'stroke-amber-400' : 'stroke-red-400';

const TREND_CONFIG: Record<string, { label: string; Icon: typeof TrendingUp; className: string }> = {
  improving: { label: 'Poprawa', Icon: TrendingUp, className: 'text-emerald-400 bg-emerald-400/10' },
  declining: { label: 'Spadek', Icon: TrendingDown, className: 'text-red-400 bg-red-400/10' },
  stable: { label: 'Stabilnie', Icon: Minus, className: 'text-[var(--text-muted)] bg-[var(--surface-hover)]' },
  no_data: { label: 'Brak danych', Icon: Minus, className: 'text-[var(--text-muted)] bg-[var(--surface-hover)]' },
};
const TREND_FALLBACK = { label: 'Nieznany', Icon: Minus, className: 'text-[var(--text-muted)] bg-[var(--surface-hover)]' };

function CircularProgress({ score }: { score: number | null }) {
  const safeScore = score ?? 0;
  const radius = 40;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (safeScore / 100) * circumference;

  return (
    <svg width="100" height="100" viewBox="0 0 100 100" className="shrink-0">
      <circle
        cx="50"
        cy="50"
        r={radius}
        fill="none"
        strokeWidth="6"
        className="stroke-[var(--border)]"
      />
      <circle
        cx="50"
        cy="50"
        r={radius}
        fill="none"
        strokeWidth="6"
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        className={cn('transition-all duration-700', RING_STROKE(score))}
        transform="rotate(-90 50 50)"
      />
      <text
        x="50"
        y="50"
        textAnchor="middle"
        dominantBaseline="central"
        className={cn('text-2xl font-bold fill-current', SCORE_COLOR(score))}
      >
        {safeScore}
      </text>
    </svg>
  );
}

export function OrgHealthBanner({ data, isLoading, onAssess, isAssessing }: OrgHealthBannerProps) {
  if (isLoading) {
    return (
      <div className="rounded-xl bg-[var(--surface)] border border-[var(--border)] border-l-4 border-l-[var(--accent)] p-6">
        <div className="flex flex-wrap items-center gap-6">
          <div className="h-[100px] w-[100px] rounded-full bg-[var(--bg-hover)] animate-pulse" />
          <div className="space-y-2">
            <div className="h-6 w-24 rounded bg-[var(--bg-hover)] animate-pulse" />
            <div className="h-4 w-32 rounded bg-[var(--bg-hover)] animate-pulse" />
          </div>
          <div className="ml-auto space-y-2">
            <div className="h-4 w-40 rounded bg-[var(--bg-hover)] animate-pulse" />
            <div className="h-4 w-40 rounded bg-[var(--bg-hover)] animate-pulse" />
          </div>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const trend = TREND_CONFIG[data.trend] ?? TREND_FALLBACK;

  return (
    <ActionableItem
      itemId="org_health"
      itemType="org_health"
      itemTitle={`Zdrowie organizacji: ${data.current_score ?? 0}/100`}
      itemContent={data}
      context="intelligence"
    >
      <div className="rounded-xl bg-[var(--surface)] border border-[var(--border)] border-l-4 border-l-[var(--accent)] p-6">
        <div className="flex flex-wrap items-center gap-6">
          {/* Left: Score ring */}
          <CircularProgress score={data.current_score} />

          {/* Center: Trend */}
          <div className="space-y-1">
            <p className="text-sm text-[var(--text-secondary)]">Zdrowie organizacji</p>
            <span
              className={cn(
                'inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-medium',
                trend.className,
              )}
            >
              <trend.Icon className="h-4 w-4" />
              {trend.label}
            </span>
          </div>

          {/* Right: Best/worst + action */}
          <div className="ml-auto flex items-center gap-6">
            <div className="space-y-1 text-sm">
              <p className="text-[var(--text-secondary)]">
                Najlepszy tydz.:{' '}
                <span className="text-emerald-400 font-medium">
                  {data.best_week?.score ?? '—'} ({data.best_week?.week ?? 'brak danych'})
                </span>
              </p>
              <p className="text-[var(--text-secondary)]">
                Najgorszy tydz.:{' '}
                <span className="text-red-400 font-medium">
                  {data.worst_week?.score ?? '—'} ({data.worst_week?.week ?? 'brak danych'})
                </span>
              </p>
            </div>

            {onAssess && (
              <button
                onClick={onAssess}
                disabled={isAssessing}
                className={cn(
                  'flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors',
                  'bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)]',
                  'disabled:opacity-50 disabled:cursor-not-allowed',
                )}
              >
                <RefreshCw className={cn('h-4 w-4', isAssessing && 'animate-spin')} />
                {isAssessing ? 'Oceniam...' : 'Oce\u0144 teraz'}
              </button>
            )}
          </div>
        </div>
      </div>
    </ActionableItem>
  );
}
