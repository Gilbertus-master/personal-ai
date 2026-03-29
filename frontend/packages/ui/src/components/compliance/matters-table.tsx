'use client';

import { useMemo } from 'react';
import Link from 'next/link';
import { Scale } from 'lucide-react';
import type { ComplianceMatter } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';
import { ComplianceBadge } from './compliance-badge';
import { AreaFilter } from './area-filter';

export interface MattersTableProps {
  matters: ComplianceMatter[];
  isLoading?: boolean;
  // Filters
  statusFilter: string | null;
  areaFilter: string | null;
  priorityFilter: string | null;
  onStatusChange: (v: string | null) => void;
  onAreaChange: (v: string | null) => void;
  onPriorityChange: (v: string | null) => void;
}

const COLUMNS = ['Tytuł', 'Typ', 'Obszar', 'Priorytet', 'Status', 'Faza', 'Zaktualizowano'] as const;

const STATUS_FILTERS = [
  { value: null, label: 'Wszystkie' },
  { value: 'open', label: 'Otwarte' },
  { value: 'researching', label: 'Badanie' },
  { value: 'in_progress', label: 'W toku' },
  { value: 'completed', label: 'Zakończone' },
  { value: 'closed', label: 'Zamknięte' },
] as const;

const PRIORITY_FILTERS = [
  { value: null, label: 'Wszystkie' },
  { value: 'critical', label: 'Krytyczny' },
  { value: 'high', label: 'Wysoki' },
  { value: 'medium', label: 'Średni' },
  { value: 'low', label: 'Niski' },
] as const;

function formatRelativeDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '\u2014';
  try {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMin = Math.floor(diffMs / 60_000);
    const diffH = Math.floor(diffMs / 3_600_000);
    const diffD = Math.floor(diffMs / 86_400_000);

    if (diffMin < 1) return 'przed chwilą';
    if (diffMin < 60) return `${diffMin} min temu`;
    if (diffH < 24) return `${diffH}h temu`;
    if (diffD < 7) return `${diffD}d temu`;
    return new Intl.DateTimeFormat('pl-PL', { day: 'numeric', month: 'short' }).format(date);
  } catch {
    return '\u2014';
  }
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
                style={{ width: `${50 + j * 8}%` }}
              />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}

export function MattersTable({
  matters,
  isLoading,
  statusFilter,
  areaFilter,
  priorityFilter,
  onStatusChange,
  onAreaChange,
  onPriorityChange,
}: MattersTableProps) {
  const filtered = useMemo(() => matters ?? [], [matters]);

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

        {/* Priority chips */}
        <div className="flex items-center gap-1.5">
          {PRIORITY_FILTERS.map((f) => (
            <button
              key={f.label}
              onClick={() => onPriorityChange(f.value)}
              className={cn(
                'rounded-full px-3 py-1 text-xs font-medium transition-colors',
                priorityFilter === f.value
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
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan={COLUMNS.length} className="px-4 py-16 text-center">
                  <div className="flex flex-col items-center gap-2 text-[var(--text-secondary)]">
                    <Scale className="h-10 w-10 opacity-40" />
                    <span className="text-sm">Nie znaleziono spraw compliance</span>
                  </div>
                </td>
              </tr>
            ) : (
              filtered.map((matter) => (
                <Link
                  key={matter.id}
                  href={`/compliance/matters/${matter.id}`}
                  className="contents"
                >
                  <tr className="border-b border-[var(--border)] cursor-pointer hover:bg-[var(--surface-hover)] transition-colors">
                    <td className="px-4 py-3 font-medium text-[var(--text)] max-w-[260px] truncate">
                      {matter.title}
                    </td>
                    <td className="px-4 py-3">
                      <ComplianceBadge type="matter_type" value={matter.matter_type} />
                    </td>
                    <td className="px-4 py-3">
                      <ComplianceBadge type="area" value={matter.area_code} />
                    </td>
                    <td className="px-4 py-3">
                      <ComplianceBadge type="priority" value={matter.priority} />
                    </td>
                    <td className="px-4 py-3">
                      <ComplianceBadge type="status" value={matter.status} />
                    </td>
                    <td className="px-4 py-3">
                      <ComplianceBadge type="phase" value={matter.phase} />
                    </td>
                    <td className="px-4 py-3 text-[var(--text-secondary)]">
                      {formatRelativeDate(matter.updated_at)}
                    </td>
                  </tr>
                </Link>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
