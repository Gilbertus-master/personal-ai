'use client';

import type { Competitor } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';

interface CompetitorTableProps {
  competitors: Competitor[];
  onRowClick?: (id: number) => void;
}

const WATCH_LEVEL_CONFIG: Record<Competitor['watch_level'], { label: string; color: string }> = {
  active: { label: 'Aktywny', color: 'bg-green-500/20 text-green-400' },
  passive: { label: 'Pasywny', color: 'bg-amber-500/20 text-amber-400' },
  archived: { label: 'Archiwalny', color: 'bg-gray-500/20 text-gray-400' },
};

function formatDate(dateStr?: string): string {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleDateString('pl-PL', { day: 'numeric', month: 'short', year: 'numeric' });
}

export function CompetitorTable({ competitors, onRowClick }: CompetitorTableProps) {
  if (competitors.length === 0) {
    return (
      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 text-center text-sm text-[var(--text-secondary)]">
        Brak konkurentów
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-[var(--border)] bg-[var(--surface)]">
            <th className="px-4 py-2.5 text-xs font-semibold uppercase text-[var(--text-secondary)]">Nazwa</th>
            <th className="px-4 py-2.5 text-xs font-semibold uppercase text-[var(--text-secondary)]">KRS</th>
            <th className="px-4 py-2.5 text-xs font-semibold uppercase text-[var(--text-secondary)]">Branża</th>
            <th className="px-4 py-2.5 text-xs font-semibold uppercase text-[var(--text-secondary)]">Monitoring</th>
            <th className="px-4 py-2.5 text-xs font-semibold uppercase text-[var(--text-secondary)]">Sygnały (30d)</th>
            <th className="px-4 py-2.5 text-xs font-semibold uppercase text-[var(--text-secondary)]">Krytyczne</th>
            <th className="px-4 py-2.5 text-xs font-semibold uppercase text-[var(--text-secondary)]">Ostatnia analiza</th>
          </tr>
        </thead>
        <tbody>
          {competitors.map((comp) => {
            const watchConfig = WATCH_LEVEL_CONFIG[comp.watch_level];

            return (
              <tr
                key={comp.id}
                onClick={() => onRowClick?.(comp.id)}
                className={cn(
                  'border-b border-[var(--border)] last:border-b-0 transition-colors hover:bg-[var(--surface-hover)]',
                  onRowClick && 'cursor-pointer',
                )}
              >
                <td className="px-4 py-2.5 font-medium text-[var(--text)]">{comp.name}</td>
                <td className="px-4 py-2.5 font-mono text-xs text-[var(--text-secondary)]">{comp.krs || '—'}</td>
                <td className="px-4 py-2.5 text-xs text-[var(--text-secondary)]">{comp.industry}</td>
                <td className="px-4 py-2.5">
                  <span className={cn('rounded-full px-2 py-0.5 text-[10px] font-semibold', watchConfig.color)}>
                    {watchConfig.label}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-center text-xs text-[var(--text)]">
                  {comp.recent_signals_30d}
                </td>
                <td className="px-4 py-2.5 text-center">
                  <span
                    className={cn(
                      'text-xs font-medium',
                      comp.high_severity > 0 ? 'text-red-400' : 'text-[var(--text-secondary)]',
                    )}
                  >
                    {comp.high_severity}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-xs text-[var(--text-secondary)]">
                  {formatDate(comp.analysis_date)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
