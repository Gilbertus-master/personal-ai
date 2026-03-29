'use client';

import { useMemo } from 'react';
import { ClipboardCheck, CheckCircle } from 'lucide-react';
import type { ComplianceObligation } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';
import { ComplianceBadge } from './compliance-badge';
import { AreaFilter } from './area-filter';

export interface ObligationsTableProps {
  obligations: ComplianceObligation[];
  overdueObligations?: ComplianceObligation[];
  isLoading?: boolean;
  showOverdueOnly: boolean;
  areaFilter: string | null;
  statusFilter: string | null;
  onAreaChange: (v: string | null) => void;
  onStatusChange: (v: string | null) => void;
  onOverdueToggle: (v: boolean) => void;
  onFulfill?: (id: number, title: string) => void;
  canFulfill?: boolean;
}

const COLUMNS = ['Tytuł', 'Obszar', 'Typ', 'Częstotliwość', 'Termin', 'Status', 'Kara', ''] as const;

const STATUS_FILTERS = [
  { value: null, label: 'Wszystkie' },
  { value: 'compliant', label: 'Zgodny' },
  { value: 'partially_compliant', label: 'Częściowo' },
  { value: 'non_compliant', label: 'Niezgodny' },
  { value: 'unknown', label: 'Nieznany' },
  { value: 'not_applicable', label: 'N/D' },
] as const;

const FREQUENCY_LABELS: Record<string, string> = {
  one_time: 'Jednorazowo',
  daily: 'Dziennie',
  weekly: 'Tygodniowo',
  monthly: 'Miesięcznie',
  quarterly: 'Kwartalnie',
  semi_annual: 'Półrocznie',
  annual: 'Rocznie',
  biennial: 'Co 2 lata',
  on_change: 'Przy zmianie',
  on_demand: 'Na żądanie',
};

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '\u2014';
  try {
    return new Intl.DateTimeFormat('pl-PL', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    }).format(new Date(dateStr));
  } catch {
    return '\u2014';
  }
}

function getDeadlineColor(dateStr: string | null | undefined): string {
  if (!dateStr) return 'var(--text-secondary)';
  try {
    const date = new Date(dateStr);
    const now = new Date();
    const diffDays = Math.floor((date.getTime() - now.getTime()) / 86_400_000);
    if (diffDays < 0) return '#ef4444';
    if (diffDays <= 7) return '#eab308';
    return 'var(--text)';
  } catch {
    return 'var(--text-secondary)';
  }
}

function formatPln(amount: number | null | undefined): string {
  if (amount == null) return '\u2014';
  return new Intl.NumberFormat('pl-PL', {
    style: 'currency',
    currency: 'PLN',
    maximumFractionDigits: 0,
  }).format(amount);
}

function SkeletonRows() {
  return (
    <>
      {Array.from({ length: 6 }).map((_, i) => (
        <tr key={i} className="border-b border-[var(--border)]">
          {Array.from({ length: COLUMNS.length }).map((_, j) => (
            <td key={j} className="px-4 py-3">
              <div
                className="h-4 rounded bg-[var(--surface)] animate-pulse"
                style={{ width: `${50 + j * 7}%` }}
              />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}

export function ObligationsTable({
  obligations,
  overdueObligations,
  isLoading,
  showOverdueOnly,
  areaFilter,
  statusFilter,
  onAreaChange,
  onStatusChange,
  onOverdueToggle,
  onFulfill,
  canFulfill = false,
}: ObligationsTableProps) {
  const data = useMemo(
    () => (showOverdueOnly ? (overdueObligations ?? []) : (obligations ?? [])),
    [obligations, overdueObligations, showOverdueOnly],
  );

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Status chips */}
        <div className="flex items-center gap-1.5">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f.label}
              onClick={() => onStatusChange(f.value)}
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

        {/* Area select */}
        <AreaFilter value={areaFilter} onChange={onAreaChange} className="w-48" />

        {/* Overdue toggle */}
        <button
          onClick={() => onOverdueToggle(!showOverdueOnly)}
          className={cn(
            'rounded-full px-3 py-1 text-xs font-medium transition-colors',
            showOverdueOnly
              ? 'bg-red-500/20 text-red-400'
              : 'bg-[var(--surface)] text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]',
          )}
        >
          Tylko zaległe
        </button>
      </div>

      {/* Table */}
      <div className="border border-[var(--border)] rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] bg-[var(--surface)]">
              {COLUMNS.map((col) => (
                <th
                  key={col}
                  className="px-4 py-3 text-left text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <SkeletonRows />
            ) : data.length === 0 ? (
              <tr>
                <td colSpan={COLUMNS.length} className="px-4 py-16 text-center">
                  <div className="flex flex-col items-center gap-2 text-[var(--text-secondary)]">
                    <ClipboardCheck className="h-10 w-10 opacity-40" />
                    <span className="text-sm">Brak obowiązków do wyświetlenia</span>
                  </div>
                </td>
              </tr>
            ) : (
              data.map((ob) => (
                <tr
                  key={ob.id}
                  className="border-b border-[var(--border)] hover:bg-[var(--surface-hover)] transition-colors"
                >
                  <td className="px-4 py-3 font-medium text-[var(--text)] max-w-[260px] truncate">
                    {ob.title}
                  </td>
                  <td className="px-4 py-3">
                    <ComplianceBadge type="area" value={ob.area_code} />
                  </td>
                  <td className="px-4 py-3">
                    <ComplianceBadge type="obligation_type" value={ob.obligation_type} />
                  </td>
                  <td className="px-4 py-3 text-[var(--text-secondary)]">
                    {FREQUENCY_LABELS[ob.frequency] ?? ob.frequency}
                  </td>
                  <td className="px-4 py-3" style={{ color: getDeadlineColor(ob.next_deadline) }}>
                    {formatDate(ob.next_deadline)}
                  </td>
                  <td className="px-4 py-3">
                    <ComplianceBadge type="compliance" value={ob.compliance_status} />
                  </td>
                  <td className="px-4 py-3 text-[var(--text-secondary)]">
                    {formatPln(ob.penalty_max_pln)}
                  </td>
                  <td className="px-4 py-3">
                    {canFulfill && onFulfill && (
                      <button
                        onClick={() => onFulfill(ob.id, ob.title)}
                        className="flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-colors hover:bg-[var(--surface-hover)]"
                        style={{ color: 'var(--accent)' }}
                        title="Realizuj obowiązek"
                      >
                        <CheckCircle size={14} />
                        Realizuj
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
