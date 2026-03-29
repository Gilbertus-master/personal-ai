'use client';

import type { AppRankingItem } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';

export interface AppRankingTableProps {
  ranking: AppRankingItem[];
}

const PRIORITY_CONFIG: Record<string, { label: string; color: string }> = {
  high: { label: 'Wysoki', color: 'bg-red-500/20 text-red-400' },
  medium: { label: 'Średni', color: 'bg-amber-500/20 text-amber-400' },
  low: { label: 'Niski', color: 'bg-green-500/20 text-green-400' },
};

function formatPLN(amount: number): string {
  return new Intl.NumberFormat('pl-PL', { style: 'currency', currency: 'PLN', maximumFractionDigits: 0 }).format(amount);
}

function feasibilityColor(pct: number): string {
  if (pct >= 70) return 'bg-green-500';
  if (pct >= 40) return 'bg-amber-500';
  return 'bg-red-500';
}

export function AppRankingTable({ ranking }: AppRankingTableProps) {
  if (ranking.length === 0) {
    return (
      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 text-center text-sm text-[var(--text-secondary)]">
        Brak danych rankingu
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-[var(--border)] bg-[var(--surface)]">
            <th className="px-4 py-2.5 text-xs font-semibold uppercase text-[var(--text-secondary)]">#</th>
            <th className="px-4 py-2.5 text-xs font-semibold uppercase text-[var(--text-secondary)]">Aplikacja</th>
            <th className="px-4 py-2.5 text-xs font-semibold uppercase text-[var(--text-secondary)]">Priorytet zamiany</th>
            <th className="px-4 py-2.5 text-xs font-semibold uppercase text-[var(--text-secondary)]">Roczne oszczędności</th>
            <th className="px-4 py-2.5 text-xs font-semibold uppercase text-[var(--text-secondary)]">Wykonalność</th>
          </tr>
        </thead>
        <tbody>
          {ranking.map((item) => {
            const priority = PRIORITY_CONFIG[item.replacement_priority] ?? {
              label: item.replacement_priority,
              color: 'bg-gray-500/20 text-gray-400',
            };

            return (
              <tr
                key={item.rank}
                className="border-b border-[var(--border)] last:border-b-0 transition-colors hover:bg-[var(--surface-hover)]"
              >
                <td className="px-4 py-2.5">
                  <span className={cn('text-sm', item.rank <= 3 ? 'font-bold text-[var(--text)]' : 'text-[var(--text-secondary)]')}>
                    {item.rank}
                  </span>
                </td>
                <td className="px-4 py-2.5 font-medium text-[var(--text)]">{item.app_name}</td>
                <td className="px-4 py-2.5">
                  <span className={cn('rounded-full px-2 py-0.5 text-[10px] font-semibold', priority.color)}>
                    {priority.label}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-xs font-medium text-[var(--text)]">
                  {formatPLN(item.annual_savings)}
                </td>
                <td className="px-4 py-2.5">
                  <div className="flex items-center gap-2">
                    <div className="h-1.5 w-16 rounded-full bg-[var(--border)]">
                      <div
                        className={cn('h-full rounded-full transition-all', feasibilityColor(item.feasibility))}
                        style={{ width: `${item.feasibility}%` }}
                      />
                    </div>
                    <span className="text-[10px] font-medium text-[var(--text-secondary)]">{item.feasibility}%</span>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
