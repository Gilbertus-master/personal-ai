'use client';

import { useMemo } from 'react';
import { FileSearch } from 'lucide-react';
import type { AuditLogEntry } from '@gilbertus/api-client';

interface AuditLogFilters {
  user: string | null;
  action: string | null;
  result: string | null;
}

interface AuditLogProps {
  entries: AuditLogEntry[];
  isLoading: boolean;
  filters: AuditLogFilters;
  onFilterChange: (filters: Partial<AuditLogFilters>) => void;
}

const resultConfig: Record<string, { label: string; className: string }> = {
  ok: { label: 'OK', className: 'bg-green-600/20 text-green-400' },
  denied: { label: 'Denied', className: 'bg-yellow-600/20 text-yellow-400' },
  error: { label: 'Error', className: 'bg-red-600/20 text-red-400' },
  governance_violation: { label: 'Governance', className: 'bg-purple-600/20 text-purple-400' },
};

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString('pl-PL', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

export function AuditLog({ entries, isLoading, filters, onFilterChange }: AuditLogProps) {
  const actions = useMemo(
    () => [...new Set(entries.map((e) => e.action))].sort(),
    [entries],
  );

  const sorted = useMemo(
    () => [...entries].sort((a, b) => new Date(b.at).getTime() - new Date(a.at).getTime()),
    [entries],
  );

  const filtered = useMemo(() => {
    let result = sorted;
    if (filters.user) {
      const q = filters.user.toLowerCase();
      result = result.filter((e) => (e.user ?? 'system').toLowerCase().includes(q));
    }
    if (filters.action) result = result.filter((e) => e.action === filters.action);
    if (filters.result) result = result.filter((e) => e.result === filters.result);
    return result;
  }, [sorted, filters]);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 animate-pulse rounded bg-[var(--surface)]" />
        <div className="h-64 animate-pulse rounded bg-[var(--surface)]" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex gap-3">
        <input
          type="text"
          placeholder="Szukaj użytkownika..."
          value={filters.user ?? ''}
          onChange={(e) => onFilterChange({ user: e.target.value || null })}
          className="rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-sm text-[var(--text)] placeholder:text-[var(--text-muted)]"
        />
        <select
          value={filters.action ?? ''}
          onChange={(e) => onFilterChange({ action: e.target.value || null })}
          className="rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-sm text-[var(--text)]"
        >
          <option value="">Wszystkie akcje</option>
          {actions.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
        <select
          value={filters.result ?? ''}
          onChange={(e) => onFilterChange({ result: e.target.value || null })}
          className="rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-sm text-[var(--text)]"
        >
          <option value="">Wszystkie wyniki</option>
          {Object.entries(resultConfig).map(([key, cfg]) => (
            <option key={key} value={key}>
              {cfg.label}
            </option>
          ))}
        </select>
      </div>

      {/* Table */}
      {filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-[var(--border)] py-16 text-[var(--text-secondary)]">
          <FileSearch className="h-8 w-8" />
          <p className="text-sm">Brak wpisów w logu</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] bg-[var(--surface)]">
                {['Czas', 'Użytkownik', 'Akcja', 'Zasób', 'Wynik', 'IP'].map((h) => (
                  <th
                    key={h}
                    className="px-4 py-2.5 text-left text-xs font-semibold uppercase text-[var(--text-secondary)]"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((e) => {
                const cfg = resultConfig[e.result] ?? resultConfig.error;
                return (
                  <tr
                    key={e.id}
                    className="border-b border-[var(--border)] hover:bg-[var(--bg-hover)]"
                  >
                    <td className="whitespace-nowrap px-4 py-2.5 text-[var(--text-secondary)]">
                      {formatTimestamp(e.at)}
                    </td>
                    <td className="px-4 py-2.5 text-[var(--text)]">{e.user ?? 'system'}</td>
                    <td className="px-4 py-2.5 text-[var(--text)]">{e.action}</td>
                    <td className="max-w-[200px] truncate px-4 py-2.5 text-[var(--text-secondary)]">
                      {e.resource}
                    </td>
                    <td className="px-4 py-2.5">
                      <span
                        className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${cfg.className}`}
                      >
                        {cfg.label}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 font-mono text-xs text-[var(--text-secondary)]">
                      {e.ip}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
