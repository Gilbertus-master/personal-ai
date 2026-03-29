'use client';

import type { DelegationScore as DelegationScoreType } from '@gilbertus/api-client';

interface DelegationScoreProps {
  data?: DelegationScoreType;
  isLoading?: boolean;
}

function formatKey(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function scoreColor(score: number): string {
  if (score >= 7) return '#22c55e';
  if (score >= 4) return '#eab308';
  return '#ef4444';
}

function scoreLabel(score: number): string {
  if (score >= 8) return 'Doskonałe';
  if (score >= 6) return 'Dobre';
  if (score >= 4) return 'Przeciętne';
  return 'Wymaga poprawy';
}

export function DelegationScore({ data, isLoading = false }: DelegationScoreProps) {
  if (isLoading) {
    return (
      <div className="space-y-4">
        <div
          className="mx-auto h-20 w-20 animate-pulse rounded-full"
          style={{ backgroundColor: 'var(--surface)' }}
        />
        <div
          className="mx-auto h-4 w-32 animate-pulse rounded"
          style={{ backgroundColor: 'var(--surface)' }}
        />
      </div>
    );
  }

  if (!data) {
    return (
      <div
        className="flex items-center justify-center rounded-lg py-8 text-sm"
        style={{ color: 'var(--text-secondary)' }}
      >
        Brak danych o delegowaniu
      </div>
    );
  }

  const metrics = data.metrics ? Object.entries(data.metrics) : [];

  return (
    <div className="space-y-6">
      {/* Large score */}
      <div className="flex flex-col items-center gap-2">
        <span
          className="text-5xl font-bold"
          style={{ color: scoreColor(data.score) }}
        >
          {data.score.toFixed(1)}
        </span>
        <span
          className="text-sm font-medium"
          style={{ color: scoreColor(data.score) }}
        >
          {scoreLabel(data.score)}
        </span>
      </div>

      {/* Metrics grid */}
      {metrics.length > 0 && (
        <div className="grid grid-cols-2 gap-3">
          {metrics.map(([key, value]) => (
            <div
              key={key}
              className="rounded-lg px-3 py-2"
              style={{ backgroundColor: 'var(--surface)' }}
            >
              <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                {formatKey(key)}
              </p>
              <p className="text-lg font-semibold" style={{ color: 'var(--text)' }}>
                {typeof value === 'number' ? value.toFixed(1) : value}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Period note */}
      <p className="text-center text-xs" style={{ color: 'var(--text-muted)' }}>
        Analiza z ostatnich {data.months} miesięcy
      </p>
    </div>
  );
}
