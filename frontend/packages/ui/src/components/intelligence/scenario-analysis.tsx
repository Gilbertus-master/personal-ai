'use client';

import { DollarSign, Users, Settings, Star, TrendingDown } from 'lucide-react';
import { cn } from '../../lib/utils';
import type { ScenarioAnalysis, ScenarioOutcome } from '@gilbertus/api-client';

interface ScenarioAnalysisViewProps {
  analysis?: ScenarioAnalysis;
  isLoading?: boolean;
}

const DIMENSION_CONFIG: Record<
  ScenarioOutcome['dimension'],
  { label: string; Icon: typeof DollarSign; className: string }
> = {
  revenue: { label: 'Przychody', Icon: DollarSign, className: 'bg-emerald-400/10 text-emerald-400' },
  costs: { label: 'Koszty', Icon: TrendingDown, className: 'bg-red-400/10 text-red-400' },
  people: { label: 'Ludzie', Icon: Users, className: 'bg-blue-400/10 text-blue-400' },
  operations: { label: 'Operacje', Icon: Settings, className: 'bg-amber-400/10 text-amber-400' },
  reputation: { label: 'Reputacja', Icon: Star, className: 'bg-purple-400/10 text-purple-400' },
};

const HORIZON_LABEL: Record<ScenarioOutcome['time_horizon'], string> = {
  '1m': '1 miesiąc',
  '3m': '3 miesiące',
  '6m': '6 miesięcy',
  '1y': '1 rok',
  '3y': '3 lata',
};

function formatPln(value: number): string {
  const prefix = value >= 0 ? '+' : '';
  return prefix + new Intl.NumberFormat('pl-PL', { maximumFractionDigits: 0 }).format(value) + ' zł';
}

export function ScenarioAnalysisView({ analysis, isLoading }: ScenarioAnalysisViewProps) {
  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-16 rounded-lg bg-[var(--bg-hover)] animate-pulse" />
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-32 rounded-lg bg-[var(--bg-hover)] animate-pulse" />
        ))}
      </div>
    );
  }

  if (!analysis) return null;

  return (
    <div className="space-y-4">
      {/* Header: title + total impact */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-[var(--text)]">{analysis.title}</h3>
        <span
          className={cn(
            'text-xl font-bold',
            analysis.total_impact_pln < 0 ? 'text-red-400' : 'text-emerald-400',
          )}
        >
          {formatPln(analysis.total_impact_pln)}
        </span>
      </div>

      {/* Outcome cards */}
      <div className="space-y-3">
        {analysis.outcomes.map((outcome, i) => {
          const dim = DIMENSION_CONFIG[outcome.dimension];
          return (
            <div
              key={i}
              className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 space-y-3"
            >
              {/* Dimension badge + impact value */}
              <div className="flex items-center justify-between">
                <span className={cn('inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium', dim.className)}>
                  <dim.Icon className="h-3.5 w-3.5" />
                  {dim.label}
                </span>
                <span
                  className={cn(
                    'text-sm font-semibold',
                    outcome.impact_value_pln < 0 ? 'text-red-400' : 'text-emerald-400',
                  )}
                >
                  {formatPln(outcome.impact_value_pln)}
                </span>
              </div>

              {/* Description */}
              <p className="text-sm text-[var(--text)]">{outcome.impact_description}</p>

              {/* Probability bar */}
              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-[var(--text-secondary)]">Prawdopodobieństwo</span>
                  <span className="text-[var(--text)] font-medium">{Math.round(outcome.probability * 100)}%</span>
                </div>
                <div className="h-1.5 w-full rounded-full bg-[var(--bg-hover)]">
                  <div
                    className={cn(
                      'h-full rounded-full transition-all',
                      outcome.probability > 0.7
                        ? 'bg-red-400'
                        : outcome.probability > 0.4
                          ? 'bg-amber-400'
                          : 'bg-emerald-400',
                    )}
                    style={{ width: `${outcome.probability * 100}%` }}
                  />
                </div>
              </div>

              {/* Time horizon */}
              <span className="inline-block rounded-full bg-[var(--surface-hover)] px-2 py-0.5 text-xs text-[var(--text-secondary)]">
                {HORIZON_LABEL[outcome.time_horizon]}
              </span>

              {/* Mitigation */}
              {outcome.mitigation && (
                <div className="rounded-md bg-[var(--bg)] p-3 text-xs text-[var(--text-secondary)]">
                  <span className="font-medium text-[var(--text)]">Mitygacja: </span>
                  {outcome.mitigation}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Latency footer */}
      <p className="text-xs text-[var(--text-muted)]">
        Czas analizy: {analysis.latency_ms.toFixed(0)} ms
      </p>
    </div>
  );
}
