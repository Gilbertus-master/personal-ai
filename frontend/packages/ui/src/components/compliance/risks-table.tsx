'use client';

import { useMemo } from 'react';
import Link from 'next/link';
import { ShieldAlert } from 'lucide-react';
import type { ComplianceRisk } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';
import { ComplianceBadge } from './compliance-badge';
import { AreaFilter } from './area-filter';

export interface RisksTableProps {
  risks: ComplianceRisk[];
  isLoading?: boolean;
  areaFilter: string | null;
  statusFilter: string | null;
  onAreaChange: (v: string | null) => void;
  onStatusChange: (v: string | null) => void;
}

const COLUMNS = [
  'Ryzyko',
  'Obszar',
  'Prawdopodobieństwo',
  'Wpływ',
  'Wynik',
  'Status',
  'Kontrole',
  'Mitygacja',
  'Sprawa',
] as const;

const STATUS_FILTERS = [
  { value: null, label: 'Wszystkie' },
  { value: 'open', label: 'Otwarte' },
  { value: 'mitigated', label: 'Zmitygowane' },
  { value: 'accepted', label: 'Zaakceptowane' },
  { value: 'closed', label: 'Zamknięte' },
] as const;

const LIKELIHOOD_LABELS: Record<string, string> = {
  very_high: 'Bardzo wysokie',
  high: 'Wysokie',
  medium: 'Średnie',
  low: 'Niskie',
  very_low: 'Bardzo niskie',
};

const LIKELIHOOD_COLORS: Record<string, string> = {
  very_high: 'text-red-400',
  high: 'text-orange-400',
  medium: 'text-yellow-400',
  low: 'text-green-400',
  very_low: 'text-green-400',
};

const IMPACT_LABELS: Record<string, string> = {
  catastrophic: 'Katastrofalny',
  major: 'Poważny',
  moderate: 'Umiarkowany',
  minor: 'Niewielki',
  negligible: 'Pomijalny',
};

const IMPACT_COLORS: Record<string, string> = {
  catastrophic: 'text-red-400',
  major: 'text-orange-400',
  moderate: 'text-yellow-400',
  minor: 'text-green-400',
  negligible: 'text-green-400',
};

function scoreColor(score: number): string {
  if (score > 16) return 'text-red-400';
  if (score >= 10) return 'text-orange-400';
  if (score >= 4) return 'text-yellow-400';
  return 'text-green-400';
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
                style={{ width: `${50 + j * 5}%` }}
              />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}

export function RisksTable({
  risks,
  isLoading,
  areaFilter,
  statusFilter,
  onAreaChange,
  onStatusChange,
}: RisksTableProps) {
  const filtered = useMemo(() => risks ?? [], [risks]);

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3">
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
        <AreaFilter value={areaFilter} onChange={onAreaChange} className="w-48" />
      </div>

      {/* Table */}
      <div className="border border-[var(--border)] rounded-lg overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] bg-[var(--surface)]">
              {COLUMNS.map((col) => (
                <th
                  key={col}
                  className="px-4 py-3 text-left text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider whitespace-nowrap"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <SkeletonRows />
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan={COLUMNS.length} className="px-4 py-16 text-center">
                  <div className="flex flex-col items-center gap-2 text-[var(--text-secondary)]">
                    <ShieldAlert className="h-10 w-10 opacity-40" />
                    <span className="text-sm">Nie znaleziono ryzyk</span>
                  </div>
                </td>
              </tr>
            ) : (
              filtered.map((risk) => (
                <tr
                  key={risk.id}
                  className="border-b border-[var(--border)] hover:bg-[var(--surface-hover)] transition-colors"
                >
                  <td className="px-4 py-3 font-medium text-[var(--text)] max-w-[200px] truncate">
                    {risk.risk_title}
                  </td>
                  <td className="px-4 py-3">
                    <ComplianceBadge type="area" value={risk.area_code} />
                  </td>
                  <td className="px-4 py-3">
                    <span className={cn('text-sm font-medium', LIKELIHOOD_COLORS[risk.likelihood])}>
                      {LIKELIHOOD_LABELS[risk.likelihood] ?? risk.likelihood}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={cn('text-sm font-medium', IMPACT_COLORS[risk.impact])}>
                      {IMPACT_LABELS[risk.impact] ?? risk.impact}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={cn('text-sm font-bold', scoreColor(risk.risk_score))}>
                      {risk.risk_score}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <ComplianceBadge type="risk" value={risk.status} />
                  </td>
                  <td className="px-4 py-3 text-[var(--text-secondary)] max-w-[160px] truncate">
                    {risk.current_controls ?? '\u2014'}
                  </td>
                  <td className="px-4 py-3 text-[var(--text-secondary)] max-w-[160px] truncate">
                    {risk.mitigation_plan ?? '\u2014'}
                  </td>
                  <td className="px-4 py-3">
                    {risk.matter_id ? (
                      <Link
                        href={`/compliance/matters/${risk.matter_id}`}
                        className="text-sm text-blue-400 hover:underline truncate block max-w-[140px]"
                      >
                        {risk.matter_title ?? `#${risk.matter_id}`}
                      </Link>
                    ) : (
                      <span className="text-[var(--text-secondary)]">{'\u2014'}</span>
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
