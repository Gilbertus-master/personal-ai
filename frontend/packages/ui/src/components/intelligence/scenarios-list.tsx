'use client';

import { useState } from 'react';
import { Layers, FlaskConical, Plus } from 'lucide-react';
import { cn } from '../../lib/utils';
import type { Scenario } from '@gilbertus/api-client';

interface ScenariosListProps {
  scenarios: Scenario[];
  isLoading?: boolean;
  statusFilter: string | null;
  onStatusFilterChange: (status: string | null) => void;
  onCreateNew: () => void;
  onAnalyze: (scenarioId: number) => void;
  onCompare: (ids: number[]) => void;
  isAnalyzing?: boolean;
  isCeo?: boolean;
}

const STATUS_FILTERS: Array<{ value: string | null; label: string }> = [
  { value: null, label: 'Wszystkie' },
  { value: 'draft', label: 'Szkic' },
  { value: 'analyzed', label: 'Przeanalizowane' },
  { value: 'archived', label: 'Zarchiwizowane' },
];

const TYPE_BADGE: Record<Scenario['type'], string> = {
  risk: 'bg-red-400/10 text-red-400',
  opportunity: 'bg-emerald-400/10 text-emerald-400',
  strategic: 'bg-blue-400/10 text-blue-400',
};

const TYPE_LABEL: Record<Scenario['type'], string> = {
  risk: 'Ryzyko',
  opportunity: 'Szansa',
  strategic: 'Strategiczny',
};

const STATUS_BADGE: Record<Scenario['status'], string> = {
  draft: 'bg-[var(--surface-hover)] text-[var(--text-secondary)]',
  analyzed: 'bg-emerald-400/10 text-emerald-400',
  archived: 'bg-[var(--surface-hover)] text-[var(--text-muted)]',
};

const STATUS_LABEL: Record<Scenario['status'], string> = {
  draft: 'Szkic',
  analyzed: 'Przeanalizowany',
  archived: 'Zarchiwizowany',
};

function formatPln(value: number): string {
  const prefix = value >= 0 ? '+' : '';
  return prefix + new Intl.NumberFormat('pl-PL', { maximumFractionDigits: 0 }).format(value) + ' zł';
}

export function ScenariosList({
  scenarios,
  isLoading,
  statusFilter,
  onStatusFilterChange,
  onCreateNew,
  onAnalyze,
  onCompare,
  isAnalyzing,
  isCeo,
}: ScenariosListProps) {
  const [compareIds, setCompareIds] = useState<Set<number>>(new Set());

  function toggleCompare(id: number) {
    setCompareIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-10 w-full rounded-lg bg-[var(--bg-hover)] animate-pulse" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-40 rounded-lg bg-[var(--bg-hover)] animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-lg font-semibold text-[var(--text)]">Scenariusze</h2>

        {/* Status filter chips */}
        <div className="flex gap-1.5">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f.value ?? 'all'}
              onClick={() => onStatusFilterChange(f.value)}
              className={cn(
                'rounded-full px-3 py-1 text-xs font-medium transition-colors',
                statusFilter === f.value
                  ? 'bg-[var(--accent)] text-white'
                  : 'bg-[var(--surface)] text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]',
              )}
            >
              {f.label}
            </button>
          ))}
        </div>

        {isCeo && (
          <button
            onClick={onCreateNew}
            className="ml-auto flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-white hover:bg-[var(--accent-hover)] transition-colors"
          >
            <Plus className="h-4 w-4" />
            Nowy scenariusz
          </button>
        )}
      </div>

      {/* Scenario cards */}
      {scenarios.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-[var(--text-muted)]">
          <Layers className="h-10 w-10 mb-3" />
          <p className="text-sm">Brak scenariuszy</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {scenarios.map((s) => (
            <div
              key={s.id}
              className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 space-y-3"
            >
              {/* Title + type */}
              <div className="flex items-start justify-between gap-2">
                <h3 className="text-sm font-semibold text-[var(--text)] line-clamp-1">{s.title}</h3>
                <span className={cn('shrink-0 rounded-full px-2 py-0.5 text-xs font-medium', TYPE_BADGE[s.type])}>
                  {TYPE_LABEL[s.type]}
                </span>
              </div>

              {/* Description */}
              <p className="text-xs text-[var(--text-secondary)] line-clamp-2">{s.description}</p>

              {/* Impact */}
              <p className={cn('text-sm font-semibold', s.total_impact_pln < 0 ? 'text-red-400' : 'text-emerald-400')}>
                {formatPln(s.total_impact_pln)}
              </p>

              {/* Status + outcome count */}
              <div className="flex items-center gap-2">
                <span className={cn('rounded-full px-2 py-0.5 text-xs font-medium', STATUS_BADGE[s.status])}>
                  {STATUS_LABEL[s.status]}
                </span>
                {s.outcome_count > 0 && (
                  <span className="text-xs text-[var(--text-muted)]">
                    {s.outcome_count} {s.outcome_count === 1 ? 'wynik' : 'wyników'}
                  </span>
                )}
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2 pt-1 border-t border-[var(--border)]">
                {s.status === 'draft' && (
                  <button
                    onClick={() => onAnalyze(s.id)}
                    disabled={isAnalyzing}
                    className={cn(
                      'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                      'bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)]',
                      'disabled:opacity-50 disabled:cursor-not-allowed',
                    )}
                  >
                    <FlaskConical className="h-3.5 w-3.5" />
                    {isAnalyzing ? 'Analizuję...' : 'Analizuj'}
                  </button>
                )}
                <label className="ml-auto flex items-center gap-1.5 text-xs text-[var(--text-secondary)] cursor-pointer">
                  <input
                    type="checkbox"
                    checked={compareIds.has(s.id)}
                    onChange={() => toggleCompare(s.id)}
                    className="rounded border-[var(--border)]"
                  />
                  Porównaj
                </label>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Compare bar */}
      {compareIds.size >= 2 && (
        <div className="sticky bottom-4 flex items-center justify-center">
          <button
            onClick={() => onCompare(Array.from(compareIds))}
            className="flex items-center gap-2 rounded-full bg-[var(--accent)] px-5 py-2.5 text-sm font-medium text-white shadow-lg hover:bg-[var(--accent-hover)] transition-colors"
          >
            Porównaj {compareIds.size} scenariuszy
          </button>
        </div>
      )}
    </div>
  );
}
