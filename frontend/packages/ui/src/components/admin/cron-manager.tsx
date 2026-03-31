'use client';

import { useMemo, useState } from 'react';
import { Clock, Filter, RotateCcw, ChevronDown, ChevronUp } from 'lucide-react';
import type { CronJob, CronSummary } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';

// ── Props ──────────────────────────────────────────────────────────────────

interface CronManagerProps {
  jobs: CronJob[];
  summary: CronSummary | undefined;
  isLoading: boolean;
  filters: { category: string | null; user: string | null; enabled: boolean | null };
  onFilterChange: (filters: Partial<CronManagerProps['filters']>) => void;
  onToggle: (jobName: string, enable: boolean) => void;
  isToggling: boolean;
}

// ── Cron schedule parser ───────────────────────────────────────────────────

function humanCron(expr: string): string | null {
  const parts = expr.trim().split(/\s+/);
  if (parts.length !== 5) return null;
  const [min, hour, dom, mon, dow] = parts;

  // Every N minutes
  if (min.startsWith('*/') && hour === '*' && dom === '*' && mon === '*' && dow === '*') {
    return `Co ${min.slice(2)} min`;
  }
  // Every N hours
  if (min === '0' && hour.startsWith('*/') && dom === '*' && mon === '*' && dow === '*') {
    return `Co ${hour.slice(2)}h`;
  }
  // Specific time daily
  if (/^\d+$/.test(min) && /^\d+$/.test(hour) && dom === '*' && mon === '*' && dow === '*') {
    return `Codziennie ${hour.padStart(2, '0')}:${min.padStart(2, '0')}`;
  }
  // Specific time on weekdays
  if (/^\d+$/.test(min) && /^\d+$/.test(hour) && dom === '*' && mon === '*') {
    const dayMap: Record<string, string> = { '0': 'Nd', '1': 'Pn', '2': 'Wt', '3': 'Śr', '4': 'Cz', '5': 'Pt', '6': 'Sb', '7': 'Nd' };
    if (dow === '1-5') return `Pn-Pt ${hour.padStart(2, '0')}:${min.padStart(2, '0')}`;
    if (dow === '0' || dow === '7') return `Nd ${hour.padStart(2, '0')}:${min.padStart(2, '0')}`;
    const dayLabel = dayMap[dow] ?? dow;
    return `${dayLabel} ${hour.padStart(2, '0')}:${min.padStart(2, '0')}`;
  }
  // Range hours (e.g. */15 8-20 * * *)
  if (min.startsWith('*/') && /^\d+-\d+$/.test(hour) && dom === '*' && mon === '*') {
    const suffix = dow === '1-5' ? ' Pn-Pt' : '';
    return `Co ${min.slice(2)} min (${hour})${suffix}`;
  }
  // Monthly (1st of month)
  if (/^\d+$/.test(min) && /^\d+$/.test(hour) && /^\d+$/.test(dom) && mon === '*' && dow === '*') {
    return `${dom}. dnia miesiąca ${hour.padStart(2, '0')}:${min.padStart(2, '0')}`;
  }
  return null;
}

// ── Category colors ────────────────────────────────────────────────────────

const CATEGORY_COLORS: Record<string, string> = {
  ingestion: 'bg-blue-500/15 text-blue-400',
  extraction: 'bg-purple-500/15 text-purple-400',
  intelligence: 'bg-amber-500/15 text-amber-400',
  delivery: 'bg-green-500/15 text-green-400',
  maintenance: 'bg-gray-500/15 text-gray-400',
  compliance: 'bg-red-500/15 text-red-400',
  monitoring: 'bg-cyan-500/15 text-cyan-400',
};

function categoryColor(cat: string): string {
  return CATEGORY_COLORS[cat.toLowerCase()] ?? 'bg-[var(--accent)]/10 text-[var(--accent)]';
}

// ── Component ──────────────────────────────────────────────────────────────

export function CronManager({
  jobs,
  summary,
  isLoading,
  filters,
  onFilterChange,
  onToggle,
  isToggling,
}: CronManagerProps) {
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  // Client-side filtering
  const filteredJobs = useMemo(() => {
    return jobs.filter((j) => {
      if (filters.category && j.category !== filters.category) return false;
      if (filters.user && j.username !== filters.user) return false;
      if (filters.enabled !== null && j.enabled !== filters.enabled) return false;
      return true;
    });
  }, [jobs, filters]);

  const categories = summary?.categories?.map((c) => c.category) ?? [];
  const users = summary?.by_user?.map((u) => u.username) ?? [];
  const hasFilters = filters.category !== null || filters.user !== null || filters.enabled !== null;

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-20 animate-pulse rounded-lg bg-[var(--surface)]" />
          ))}
        </div>
        <div className="h-10 animate-pulse rounded-lg bg-[var(--surface)]" />
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="h-12 animate-pulse rounded-lg bg-[var(--surface)]" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Summary bar */}
      {summary && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
            <div className="flex items-center gap-2 text-[var(--text-secondary)]">
              <Clock className="h-4 w-4" />
              <span className="text-xs font-medium uppercase tracking-wider">Łącznie</span>
            </div>
            <p className="mt-1 text-2xl font-semibold text-[var(--text)]">{summary.total}</p>
          </div>

          <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
            <div className="text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">
              Kategorie
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {(summary.categories ?? []).map((c) => (
                <span key={c.category} className={cn('rounded-full px-2 py-0.5 text-xs font-medium', categoryColor(c.category))}>
                  {c.category} ({c.jobs})
                </span>
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
            <div className="text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">
              Użytkownicy
            </div>
            <div className="mt-2 space-y-1">
              {(summary.by_user ?? []).map((u) => (
                <div key={u.username} className="flex items-center justify-between text-sm">
                  <span className="font-mono text-[var(--text)]">{u.username}</span>
                  <span className="text-[var(--text-secondary)]">
                    {u.enabled} aktywnych, {u.disabled} wył.
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Filters row */}
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-3">
        <Filter className="h-4 w-4 text-[var(--text-secondary)]" />

        <select
          value={filters.category ?? ''}
          onChange={(e) => onFilterChange({ category: e.target.value || null })}
          className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-1.5 text-sm text-[var(--text)]"
        >
          <option value="">Wszystkie kategorie</option>
          {categories.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>

        <select
          value={filters.user ?? ''}
          onChange={(e) => onFilterChange({ user: e.target.value || null })}
          className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-1.5 text-sm text-[var(--text)]"
        >
          <option value="">Wszyscy użytkownicy</option>
          {users.map((u) => (
            <option key={u} value={u}>{u}</option>
          ))}
        </select>

        <select
          value={filters.enabled === null ? '' : filters.enabled ? 'true' : 'false'}
          onChange={(e) => {
            const v = e.target.value;
            onFilterChange({ enabled: v === '' ? null : v === 'true' });
          }}
          className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-1.5 text-sm text-[var(--text)]"
        >
          <option value="">Wszystkie</option>
          <option value="true">Aktywne</option>
          <option value="false">Wyłączone</option>
        </select>

        {hasFilters && (
          <button
            onClick={() => onFilterChange({ category: null, user: null, enabled: null })}
            className="ml-auto flex items-center gap-1 rounded-md px-2 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text)]"
          >
            <RotateCcw className="h-3 w-3" />
            Reset
          </button>
        )}
      </div>

      {/* Table */}
      {filteredJobs.length === 0 ? (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-8 text-center text-sm text-[var(--text-secondary)]">
          Brak cronów pasujących do filtrów
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] bg-[var(--surface)]">
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">Nazwa</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">Harmonogram</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">Kategoria</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">Użytkownik</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">Opis</th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {filteredJobs.map((job) => {
                const isExpanded = expandedRow === job.job_name;
                const humanSchedule = humanCron(job.schedule);
                return (
                  <tr key={job.job_name} className="bg-[var(--bg)] hover:bg-[var(--surface-hover)] transition-colors">
                    <td className="px-4 py-3 font-mono text-xs text-[var(--text)]">{job.job_name}</td>
                    <td className="px-4 py-3">
                      <span className="font-mono text-xs text-[var(--text)]" title={job.schedule}>
                        {humanSchedule ?? job.schedule}
                      </span>
                      {humanSchedule && (
                        <span className="ml-1 text-xs text-[var(--text-secondary)]" title={job.schedule}>
                          ({job.schedule})
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className={cn('rounded-full px-2 py-0.5 text-xs font-medium', categoryColor(job.category))}>
                        {job.category}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-[var(--text-secondary)]">{job.username}</td>
                    <td className="px-4 py-3">
                      {job.description ? (
                        <button
                          onClick={() => setExpandedRow(isExpanded ? null : job.job_name)}
                          className="flex items-center gap-1 text-left text-xs text-[var(--text-secondary)] hover:text-[var(--text)]"
                        >
                          <span className={isExpanded ? '' : 'max-w-[200px] truncate'}>
                            {job.description}
                          </span>
                          {isExpanded ? <ChevronUp className="h-3 w-3 shrink-0" /> : <ChevronDown className="h-3 w-3 shrink-0" />}
                        </button>
                      ) : (
                        <span className="text-xs text-[var(--text-secondary)]">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => onToggle(job.job_name, !job.enabled)}
                        disabled={isToggling}
                        className={cn(
                          'relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full transition-colors disabled:cursor-not-allowed disabled:opacity-50',
                          job.enabled ? 'bg-green-500' : 'bg-[var(--border)]',
                        )}
                        title={job.enabled ? 'Wyłącz' : 'Włącz'}
                      >
                        <span
                          className={cn(
                            'inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform',
                            job.enabled ? 'translate-x-[18px]' : 'translate-x-[3px]',
                          )}
                        />
                      </button>
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
