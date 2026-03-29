'use client';

import type { AppInventoryItem } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';

export interface AppTableProps {
  apps: AppInventoryItem[];
  onRowClick?: (name: string) => void;
}

const STATUS_CONFIG: Record<AppInventoryItem['status'], { label: string; color: string }> = {
  not_planned: { label: 'Nie planowana', color: 'bg-gray-500/20 text-gray-400' },
  planned: { label: 'Planowana', color: 'bg-blue-500/20 text-blue-400' },
  partial: { label: 'Częściowa', color: 'bg-amber-500/20 text-amber-400' },
  replaced: { label: 'Zastąpiona', color: 'bg-green-500/20 text-green-400' },
  not_replaceable: { label: 'Niezastępowalna', color: 'bg-red-500/20 text-red-400' },
};

export function AppTable({ apps, onRowClick }: AppTableProps) {
  if (apps.length === 0) {
    return (
      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 text-center text-sm text-[var(--text-secondary)]">
        Brak aplikacji
      </div>
    );
  }

  const maxMentions = Math.max(...apps.map((a) => a.mentions), 1);

  return (
    <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-[var(--border)] bg-[var(--surface)]">
            <th className="px-4 py-2.5 text-xs font-semibold uppercase text-[var(--text-secondary)]">Aplikacja</th>
            <th className="px-4 py-2.5 text-xs font-semibold uppercase text-[var(--text-secondary)]">Kategoria</th>
            <th className="px-4 py-2.5 text-xs font-semibold uppercase text-[var(--text-secondary)]">Wzmianki</th>
            <th className="px-4 py-2.5 text-xs font-semibold uppercase text-[var(--text-secondary)]">Zamiennik</th>
            <th className="px-4 py-2.5 text-xs font-semibold uppercase text-[var(--text-secondary)]">Status</th>
          </tr>
        </thead>
        <tbody>
          {apps.map((app) => {
            const status = STATUS_CONFIG[app.status];
            const mentionPct = Math.round((app.mentions / maxMentions) * 100);

            return (
              <tr
                key={app.name}
                onClick={() => onRowClick?.(app.name)}
                className={cn(
                  'border-b border-[var(--border)] last:border-b-0 transition-colors hover:bg-[var(--surface-hover)]',
                  onRowClick && 'cursor-pointer',
                )}
              >
                <td className="px-4 py-2.5 font-medium text-[var(--text)]">{app.name}</td>
                <td className="px-4 py-2.5 text-xs text-[var(--text-secondary)]">{app.category}</td>
                <td className="px-4 py-2.5">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium text-[var(--text)]">{app.mentions}</span>
                    <div className="h-1.5 w-16 rounded-full bg-[var(--border)]">
                      <div
                        className="h-full rounded-full bg-[var(--accent)] transition-all"
                        style={{ width: `${mentionPct}%` }}
                      />
                    </div>
                  </div>
                </td>
                <td className="px-4 py-2.5 text-xs text-[var(--text-secondary)]">{app.replacement || '—'}</td>
                <td className="px-4 py-2.5">
                  <span className={cn('rounded-full px-2 py-0.5 text-[10px] font-semibold', status.color)}>
                    {status.label}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
