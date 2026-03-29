'use client';

import { useMemo } from 'react';
import type { ComplianceRisk, RiskHeatmapArea } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';

export interface RiskHeatmapProps {
  risks: ComplianceRisk[];
  heatmapAreas: RiskHeatmapArea[];
  totalRisks: number;
  overallAvg: number;
  isLoading?: boolean;
  onCellClick?: (likelihood: string, impact: string) => void;
}

const LIKELIHOODS = ['very_high', 'high', 'medium', 'low', 'very_low'] as const;
const IMPACTS = ['negligible', 'minor', 'moderate', 'major', 'catastrophic'] as const;

const LIKELIHOOD_LABELS: Record<string, string> = {
  very_high: 'Bardzo wysokie',
  high: 'Wysokie',
  medium: 'Średnie',
  low: 'Niskie',
  very_low: 'Bardzo niskie',
};

const IMPACT_LABELS: Record<string, string> = {
  negligible: 'Pomijalny',
  minor: 'Niewielki',
  moderate: 'Umiarkowany',
  major: 'Poważny',
  catastrophic: 'Katastrofalny',
};

// Score = likelihood_index * impact_index (1-based)
const LIKELIHOOD_SCORE: Record<string, number> = {
  very_low: 1,
  low: 2,
  medium: 3,
  high: 4,
  very_high: 5,
};

const IMPACT_SCORE: Record<string, number> = {
  negligible: 1,
  minor: 2,
  moderate: 3,
  major: 4,
  catastrophic: 5,
};

function cellZoneColor(likelihood: string, impact: string): string {
  const score = (LIKELIHOOD_SCORE[likelihood] ?? 1) * (IMPACT_SCORE[impact] ?? 1);
  if (score >= 17) return 'bg-red-500/25 hover:bg-red-500/35 border-red-500/30';
  if (score >= 10) return 'bg-orange-500/20 hover:bg-orange-500/30 border-orange-500/25';
  if (score >= 5) return 'bg-yellow-500/15 hover:bg-yellow-500/25 border-yellow-500/20';
  return 'bg-green-500/10 hover:bg-green-500/20 border-green-500/15';
}

function cellTextColor(likelihood: string, impact: string): string {
  const score = (LIKELIHOOD_SCORE[likelihood] ?? 1) * (IMPACT_SCORE[impact] ?? 1);
  if (score >= 17) return 'text-red-300';
  if (score >= 10) return 'text-orange-300';
  if (score >= 5) return 'text-yellow-300';
  return 'text-green-300';
}

const AREA_DOT_COLORS: Record<string, string> = {
  green: 'bg-green-400',
  yellow: 'bg-yellow-400',
  orange: 'bg-orange-400',
  red: 'bg-red-400',
  critical: 'bg-red-500',
};

export function RiskHeatmap({
  risks,
  heatmapAreas,
  totalRisks,
  overallAvg,
  isLoading,
  onCellClick,
}: RiskHeatmapProps) {
  // Build count map: likelihood_impact -> count
  const countMap = useMemo(() => {
    const map: Record<string, number> = {};
    for (const risk of risks ?? []) {
      const key = `${risk.likelihood}_${risk.impact}`;
      map[key] = (map[key] ?? 0) + 1;
    }
    return map;
  }, [risks]);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="h-[400px] rounded-lg bg-[var(--surface)] animate-pulse" />
        <div className="grid grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-24 rounded-lg bg-[var(--surface)] animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Heatmap Grid */}
      <div className="overflow-x-auto">
        <div className="min-w-[600px]">
          {/* Header: Impact labels */}
          <div className="grid grid-cols-[120px_repeat(5,1fr)] gap-1 mb-1">
            <div className="text-xs text-[var(--text-secondary)] text-center self-end pb-1">
              Prawdopod. / Wpływ
            </div>
            {IMPACTS.map((impact) => (
              <div
                key={impact}
                className="text-xs text-[var(--text-secondary)] text-center pb-1 font-medium"
              >
                {IMPACT_LABELS[impact]}
              </div>
            ))}
          </div>

          {/* Rows: one per likelihood (top = very_high) */}
          {LIKELIHOODS.map((likelihood) => (
            <div key={likelihood} className="grid grid-cols-[120px_repeat(5,1fr)] gap-1 mb-1">
              {/* Row label */}
              <div className="flex items-center text-xs font-medium text-[var(--text-secondary)] pr-2 justify-end">
                {LIKELIHOOD_LABELS[likelihood]}
              </div>

              {/* Cells */}
              {IMPACTS.map((impact) => {
                const count = countMap[`${likelihood}_${impact}`] ?? 0;
                return (
                  <button
                    key={`${likelihood}_${impact}`}
                    onClick={() => onCellClick?.(likelihood, impact)}
                    className={cn(
                      'aspect-square rounded-md border flex items-center justify-center transition-colors cursor-pointer min-h-[56px]',
                      cellZoneColor(likelihood, impact),
                    )}
                  >
                    {count > 0 && (
                      <span className={cn('text-lg font-bold', cellTextColor(likelihood, impact))}>
                        {count}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-4 text-xs text-[var(--text-secondary)]">
        <span className="font-medium">Strefy ryzyka:</span>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded bg-green-500/20 border border-green-500/30" />
          <span>1-4 (niskie)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded bg-yellow-500/20 border border-yellow-500/30" />
          <span>5-9 (średnie)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded bg-orange-500/20 border border-orange-500/30" />
          <span>10-16 (wysokie)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded bg-red-500/25 border border-red-500/35" />
          <span>17-25 (krytyczne)</span>
        </div>
      </div>

      {/* Area Summary Cards */}
      <div>
        <h3 className="text-sm font-semibold text-[var(--text)] mb-3">Podsumowanie obszarów</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {(heatmapAreas ?? []).map((area) => (
            <div
              key={area.code}
              className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4"
            >
              <div className="flex items-center gap-2 mb-2">
                <div
                  className={cn('w-2.5 h-2.5 rounded-full', AREA_DOT_COLORS[area.color] ?? 'bg-gray-400')}
                />
                <span className="text-sm font-medium text-[var(--text)]">{area.name}</span>
              </div>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                <span className="text-[var(--text-secondary)]">Ryzyka:</span>
                <span className="text-[var(--text)] font-medium">{area.risk_count}</span>
                <span className="text-[var(--text-secondary)]">Śr. wynik:</span>
                <span className="text-[var(--text)] font-medium">{area.avg_score.toFixed(1)}</span>
                <span className="text-[var(--text-secondary)]">Maks. wynik:</span>
                <span className="text-[var(--text)] font-medium">{area.max_score}</span>
                <span className="text-[var(--text-secondary)]">Krytyczne:</span>
                <span
                  className={cn(
                    'font-medium',
                    area.critical_count > 0 ? 'text-red-400' : 'text-[var(--text)]',
                  )}
                >
                  {area.critical_count}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Overall Stats */}
      <div className="flex items-center gap-6 text-sm text-[var(--text-secondary)]">
        <span>
          Razem ryzyk: <strong className="text-[var(--text)]">{totalRisks}</strong>
        </span>
        <span>
          Średni wynik: <strong className="text-[var(--text)]">{overallAvg.toFixed(1)}</strong>
        </span>
      </div>
    </div>
  );
}
