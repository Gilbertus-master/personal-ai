'use client';

import { Fragment, useState, useMemo } from 'react';
import { CheckCircle, ChevronDown, ChevronRight } from 'lucide-react';
import type { CodeFinding } from '@gilbertus/api-client';

interface CodeReviewQueueProps {
  findings: CodeFinding[];
  isLoading: boolean;
  severityFilter: string | null;
  categoryFilter: string | null;
  onSeverityFilterChange: (v: string | null) => void;
  onCategoryFilterChange: (v: string | null) => void;
}

const severityConfig: Record<string, { label: string; className: string }> = {
  critical: { label: 'Critical', className: 'bg-red-600/20 text-red-400' },
  high: { label: 'High', className: 'bg-orange-600/20 text-orange-400' },
  medium: { label: 'Medium', className: 'bg-yellow-600/20 text-yellow-400' },
  low: { label: 'Low', className: 'bg-blue-600/20 text-blue-400' },
};

export function CodeReviewQueue({
  findings,
  isLoading,
  severityFilter,
  categoryFilter,
  onSeverityFilterChange,
  onCategoryFilterChange,
}: CodeReviewQueueProps) {
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const categories = useMemo(
    () => [...new Set(findings.map((f) => f.category))].sort(),
    [findings],
  );

  const filtered = useMemo(() => {
    let result = findings;
    if (severityFilter) result = result.filter((f) => f.severity === severityFilter);
    if (categoryFilter) result = result.filter((f) => f.category === categoryFilter);
    return result;
  }, [findings, severityFilter, categoryFilter]);

  const counts = useMemo(() => {
    const c = { critical: 0, high: 0, medium: 0, low: 0 };
    for (const f of findings) c[f.severity]++;
    return c;
  }, [findings]);

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
      {/* Stats bar */}
      <div className="flex flex-wrap gap-2">
        {(['critical', 'high', 'medium', 'low'] as const).map((sev) => (
          <span
            key={sev}
            className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${severityConfig[sev].className}`}
          >
            {severityConfig[sev].label}: {counts[sev]}
          </span>
        ))}
      </div>

      {/* Filters */}
      <div className="flex gap-3">
        <select
          value={severityFilter ?? ''}
          onChange={(e) => onSeverityFilterChange(e.target.value || null)}
          className="rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-sm text-[var(--text)]"
        >
          <option value="">Wszystkie poziomy</option>
          {(['critical', 'high', 'medium', 'low'] as const).map((sev) => (
            <option key={sev} value={sev}>
              {severityConfig[sev].label}
            </option>
          ))}
        </select>
        <select
          value={categoryFilter ?? ''}
          onChange={(e) => onCategoryFilterChange(e.target.value || null)}
          className="rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-sm text-[var(--text)]"
        >
          <option value="">Wszystkie kategorie</option>
          {categories.map((cat) => (
            <option key={cat} value={cat}>
              {cat}
            </option>
          ))}
        </select>
      </div>

      {/* Table */}
      {filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-[var(--border)] py-16 text-[var(--text-secondary)]">
          <CheckCircle className="h-8 w-8 text-green-500" />
          <p className="text-sm">Brak znalezisk do przeglądu</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] bg-[var(--surface)]">
                <th className="w-8 px-3 py-2.5" />
                <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase text-[var(--text-secondary)]">
                  Poziom
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase text-[var(--text-secondary)]">
                  Plik
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase text-[var(--text-secondary)]">
                  Tytuł
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase text-[var(--text-secondary)]">
                  Kategoria
                </th>
                <th className="px-4 py-2.5 text-right text-xs font-semibold uppercase text-[var(--text-secondary)]">
                  Próby
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase text-[var(--text-secondary)]">
                  Ostatnia próba
                </th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((f) => {
                const expanded = expandedId === f.id;
                return (
                  <Fragment key={f.id}>
                    <tr
                      className="cursor-pointer border-b border-[var(--border)] hover:bg-[var(--bg-hover)]"
                      onClick={() => setExpandedId(expanded ? null : f.id)}
                    >
                      <td className="px-3 py-2.5 text-[var(--text-secondary)]">
                        {expanded ? (
                          <ChevronDown className="h-4 w-4" />
                        ) : (
                          <ChevronRight className="h-4 w-4" />
                        )}
                      </td>
                      <td className="px-4 py-2.5">
                        <span
                          className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${severityConfig[f.severity].className}`}
                        >
                          {severityConfig[f.severity].label}
                        </span>
                      </td>
                      <td className="max-w-[200px] truncate px-4 py-2.5 font-mono text-xs text-[var(--text)]">
                        {f.file.split('/').pop()}
                      </td>
                      <td className="px-4 py-2.5 text-[var(--text)]">{f.title}</td>
                      <td className="px-4 py-2.5 text-[var(--text-secondary)]">{f.category}</td>
                      <td className="px-4 py-2.5 text-right text-[var(--text-secondary)]">
                        {f.attempts}
                      </td>
                      <td className="px-4 py-2.5 text-[var(--text-secondary)]">
                        {f.last_attempt
                          ? new Date(f.last_attempt).toLocaleDateString('pl-PL')
                          : '\u2014'}
                      </td>
                    </tr>
                    {expanded && (
                      <tr className="border-b border-[var(--border)] bg-[var(--surface)]">
                        <td colSpan={7} className="px-8 py-4">
                          <p className="mb-1 font-mono text-xs text-[var(--text-secondary)]">
                            {f.file}
                          </p>
                          <p className="whitespace-pre-wrap text-sm text-[var(--text)]">
                            {f.description}
                          </p>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
