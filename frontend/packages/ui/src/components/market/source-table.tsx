'use client';

import { Globe, Rss, Plug } from 'lucide-react';
import type { MarketSource } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';

interface SourceTableProps {
  sources: MarketSource[];
}

const SOURCE_TYPE_CONFIG: Record<string, { icon: typeof Rss; label: string; color: string }> = {
  rss: { icon: Rss, label: 'RSS', color: 'bg-orange-500/20 text-orange-400' },
  api: { icon: Plug, label: 'API', color: 'bg-blue-500/20 text-blue-400' },
  web: { icon: Globe, label: 'Web', color: 'bg-purple-500/20 text-purple-400' },
};

function formatRelativeTime(dateStr: string | null): string {
  if (!dateStr) return 'Nigdy';
  const now = Date.now();
  const date = new Date(dateStr).getTime();
  const diffMs = now - date;
  const diffMin = Math.floor(diffMs / 60_000);
  const diffH = Math.floor(diffMs / 3_600_000);
  const diffD = Math.floor(diffMs / 86_400_000);

  if (diffMin < 1) return 'teraz';
  if (diffMin < 60) return `${diffMin}min temu`;
  if (diffH < 24) return `${diffH}h temu`;
  if (diffD === 1) return 'wczoraj';
  if (diffD < 7) return `${diffD}d temu`;
  return new Date(dateStr).toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' });
}

export function SourceTable({ sources }: SourceTableProps) {
  if (sources.length === 0) {
    return (
      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 text-center text-sm text-[var(--text-secondary)]">
        Brak źródeł
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-[var(--border)] bg-[var(--surface)]">
            <th className="px-4 py-2.5 text-xs font-semibold uppercase text-[var(--text-secondary)]">Nazwa</th>
            <th className="px-4 py-2.5 text-xs font-semibold uppercase text-[var(--text-secondary)]">URL</th>
            <th className="px-4 py-2.5 text-xs font-semibold uppercase text-[var(--text-secondary)]">Typ</th>
            <th className="px-4 py-2.5 text-xs font-semibold uppercase text-[var(--text-secondary)]">Ostatni fetch</th>
            <th className="px-4 py-2.5 text-xs font-semibold uppercase text-[var(--text-secondary)]">Status</th>
          </tr>
        </thead>
        <tbody>
          {sources.map((source, idx) => {
            const typeConfig = SOURCE_TYPE_CONFIG[source.source_type ?? 'web'] ?? SOURCE_TYPE_CONFIG.web;
            const TypeIcon = typeConfig.icon;

            return (
              <tr
                key={source.id ?? idx}
                className="border-b border-[var(--border)] last:border-b-0 transition-colors hover:bg-[var(--surface-hover)]"
              >
                <td className="px-4 py-2.5 font-medium text-[var(--text)]">{source.name}</td>
                <td className="max-w-[200px] truncate px-4 py-2.5 text-xs text-[var(--text-secondary)]">
                  {source.url ?? '—'}
                </td>
                <td className="px-4 py-2.5">
                  <span className={cn('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold', typeConfig.color)}>
                    <TypeIcon size={10} />
                    {typeConfig.label}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-xs text-[var(--text-secondary)]">
                  {formatRelativeTime(source.last_fetched)}
                </td>
                <td className="px-4 py-2.5">
                  <span
                    className={cn(
                      'inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold',
                      source.active
                        ? 'bg-green-500/20 text-green-400'
                        : 'bg-gray-500/20 text-gray-400',
                    )}
                  >
                    {source.active ? 'Aktywne' : 'Nieaktywne'}
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
