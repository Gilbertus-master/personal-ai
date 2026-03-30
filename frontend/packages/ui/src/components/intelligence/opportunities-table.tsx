'use client';

import { useState, useMemo } from 'react';
import { ArrowUpDown, Calendar, Clock, AlertTriangle, Search as SearchIcon, Loader2 } from 'lucide-react';
import { cn } from '../../lib/utils';
import type { Opportunity } from '@gilbertus/api-client';
import { ActionableItem } from '../shared/actionable-item';

interface OpportunitiesTableProps {
  opportunities: Opportunity[];
  isLoading?: boolean;
  onScan?: () => void;
  isScanning?: boolean;
  statusFilter: string | null;
  onStatusFilterChange: (status: string | null) => void;
}

type SortKey = 'value_pln' | 'roi';

const STATUS_BADGE: Record<string, string> = {
  new: 'bg-blue-400/10 text-blue-400',
  analyzed: 'bg-purple-400/10 text-purple-400',
  accepted: 'bg-emerald-400/10 text-emerald-400',
  rejected: 'bg-red-400/10 text-red-400',
};

const TYPE_BADGE: Record<string, string> = {
  revenue: 'bg-emerald-400/10 text-emerald-400',
  cost_saving: 'bg-amber-400/10 text-amber-400',
  efficiency: 'bg-blue-400/10 text-blue-400',
  partnership: 'bg-purple-400/10 text-purple-400',
};

const STATUS_FILTERS = [
  { value: null, label: 'Wszystkie' },
  { value: 'new', label: 'Nowe' },
  { value: 'analyzed', label: 'Przeanalizowane' },
  { value: 'accepted', label: 'Zaakceptowane' },
] as const;

function formatPln(value: number): string {
  return new Intl.NumberFormat('pl-PL', { maximumFractionDigits: 0 }).format(value);
}


const URGENCY_CONFIG: Record<string, { label: string; color: string }> = {
  immediate: { label: 'Dziś!', color: 'text-red-400 bg-red-500/10' },
  this_week: { label: 'Ten tydzień', color: 'text-amber-400 bg-amber-500/10' },
  this_month: { label: 'Ten miesiąc', color: 'text-blue-400 bg-blue-500/10' },
  normal: { label: '—', color: 'text-[var(--text-secondary)]' },
};

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  return d.toLocaleDateString('pl-PL', { day: 'numeric', month: 'short', year: 'numeric' });
}

function deadlineColor(dateStr: string | null | undefined): string {
  if (!dateStr) return '';
  const days = Math.ceil((new Date(dateStr).getTime() - Date.now()) / 86_400_000);
  if (days <= 0) return 'text-red-400 font-bold';
  if (days <= 3) return 'text-red-400';
  if (days <= 7) return 'text-amber-400';
  return 'text-[var(--text-secondary)]';
}

export function OpportunitiesTable({
  opportunities,
  isLoading,
  onScan,
  isScanning,
  statusFilter,
  onStatusFilterChange,
}: OpportunitiesTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('value_pln');
  const [sortAsc, setSortAsc] = useState(false);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortAsc((prev) => !prev);
    } else {
      setSortKey(key);
      setSortAsc(false);
    }
  };

  const sorted = useMemo(() => {
    const list = [...opportunities];
    list.sort((a, b) => {
      const diff = a[sortKey] - b[sortKey];
      return sortAsc ? diff : -diff;
    });
    return list;
  }, [opportunities, sortKey, sortAsc]);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-lg font-semibold text-[var(--text)]">Szanse biznesowe</h2>

        {/* Status filter chips */}
        <div className="flex items-center gap-1.5">
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

        {onScan && (
          <button
            onClick={onScan}
            disabled={isScanning}
            className={cn(
              'ml-auto flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors',
              'bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)]',
              'disabled:opacity-50 disabled:cursor-not-allowed',
            )}
          >
            {isScanning ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <SearchIcon className="h-4 w-4" />
            )}
            Skanuj
          </button>
        )}
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-14 rounded-lg bg-[var(--bg-hover)] animate-pulse" />
          ))}
        </div>
      ) : sorted.length === 0 ? (
        <p className="py-8 text-center text-sm text-[var(--text-secondary)]">
          Brak szans do wyswietlenia
        </p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] bg-[var(--surface)]">
                <th className="px-4 py-3 text-left font-medium text-[var(--text-secondary)]">Typ</th>
                <th className="px-4 py-3 text-left font-medium text-[var(--text-secondary)]">Opis</th>
                <th className="px-4 py-3 text-right font-medium text-[var(--text-secondary)]">
                  <button
                    onClick={() => handleSort('value_pln')}
                    className="inline-flex items-center gap-1 hover:text-[var(--text)]"
                  >
                    Wartosc
                    <ArrowUpDown className={cn('h-3.5 w-3.5', sortKey === 'value_pln' && 'text-[var(--accent)]')} />
                  </button>
                </th>
                <th className="px-4 py-3 text-right font-medium text-[var(--text-secondary)]">
                  <button
                    onClick={() => handleSort('roi')}
                    className="inline-flex items-center gap-1 hover:text-[var(--text)]"
                  >
                    ROI
                    <ArrowUpDown className={cn('h-3.5 w-3.5', sortKey === 'roi' && 'text-[var(--accent)]')} />
                  </button>
                </th>
                <th className="px-4 py-3 text-left font-medium text-[var(--text-secondary)]">Pewnosc</th>
                <th className="px-4 py-3 text-left font-medium text-[var(--text-secondary)]">Odkryto</th>
                <th className="px-4 py-3 text-left font-medium text-[var(--text-secondary)]">Deadline</th>
                <th className="px-4 py-3 text-left font-medium text-[var(--text-secondary)]">Pilność</th>
                <th className="px-4 py-3 text-left font-medium text-[var(--text-secondary)]">Status</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((opp) => (
                <tr
                  key={opp.id}
                  className="group/actionable relative border-b border-[var(--border)] last:border-b-0 hover:bg-[var(--surface-hover)] transition-colors"
                >
                  <td className="px-4 py-3">
                    <span
                      className={cn(
                        'rounded-full px-2 py-0.5 text-xs font-medium',
                        TYPE_BADGE[opp.type] ?? 'bg-[var(--surface-hover)] text-[var(--text-secondary)]',
                      )}
                    >
                      {opp.type}
                    </span>
                  </td>
                  <td className="px-4 py-3 max-w-xs">
                    <p className="text-[var(--text)] line-clamp-2">{opp.description}</p>
                  </td>
                  <td className="px-4 py-3 text-right font-medium text-[var(--text)] whitespace-nowrap">
                    {formatPln(opp.value_pln)} zl
                  </td>
                  <td className="px-4 py-3 text-right">
                    <span
                      className={cn(
                        'font-medium',
                        opp.roi > 5
                          ? 'text-emerald-400'
                          : opp.roi > 2
                            ? 'text-amber-400'
                            : 'text-red-400',
                      )}
                    >
                      {opp.roi.toFixed(1)}x
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="h-2 w-16 rounded-full bg-[var(--border)] overflow-hidden">
                        <div
                          className="h-full rounded-full bg-[var(--accent)] transition-all"
                          style={{ width: `${Math.round(opp.confidence * 100)}%` }}
                        />
                      </div>
                      <span className="text-xs text-[var(--text-secondary)]">
                        {Math.round(opp.confidence * 100)}%
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <span className="flex items-center gap-1 text-xs text-[var(--text-secondary)]">
                      <Calendar className="h-3 w-3" />
                      {formatDate(opp.created)}
                    </span>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    {opp.deadline ? (
                      <span className={cn('flex items-center gap-1 text-xs', deadlineColor(opp.deadline))}>
                        <Clock className="h-3 w-3" />
                        {formatDate(opp.deadline)}
                      </span>
                    ) : (
                      <span className="text-xs text-[var(--text-secondary)]">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {opp.urgency && opp.urgency !== 'normal' ? (
                      <span className={cn('rounded-full px-2 py-0.5 text-[10px] font-semibold', URGENCY_CONFIG[opp.urgency]?.color)}>
                        {URGENCY_CONFIG[opp.urgency]?.label ?? opp.urgency}
                      </span>
                    ) : (
                      <span className="text-xs text-[var(--text-secondary)]">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <ActionableItem
                      itemId={`opp_${opp.id}`}
                      itemType="opportunity"
                      itemTitle={opp.description}
                      itemContent={opp}
                      context="intelligence"
                    >
                      <span
                        className={cn(
                          'rounded-full px-2 py-0.5 text-xs font-medium',
                          STATUS_BADGE[opp.status] ?? 'bg-[var(--surface-hover)] text-[var(--text-secondary)]',
                        )}
                      >
                        {opp.status}
                      </span>
                    </ActionableItem>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
