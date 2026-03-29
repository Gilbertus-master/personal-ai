'use client';

import { useMemo } from 'react';
import Link from 'next/link';
import { GraduationCap } from 'lucide-react';
import type { ComplianceTraining } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';
import { ComplianceBadge } from './compliance-badge';
import { AreaFilter } from './area-filter';

export interface TrainingsTableProps {
  trainings: ComplianceTraining[];
  isLoading?: boolean;
  areaFilter: string | null;
  statusFilter: string | null;
  onAreaChange: (v: string | null) => void;
  onStatusChange: (v: string | null) => void;
}

const COLUMNS = ['Tytuł', 'Obszar', 'Typ szkolenia', 'Odbiorcy', 'Termin', 'Status'] as const;

const STATUS_FILTERS = [
  { value: null, label: 'Wszystkie' },
  { value: 'planned', label: 'Planowane' },
  { value: 'material_ready', label: 'Materiały' },
  { value: 'scheduled', label: 'Zaplanowane' },
  { value: 'in_progress', label: 'W toku' },
  { value: 'completed', label: 'Ukończone' },
  { value: 'cancelled', label: 'Anulowane' },
] as const;

const TRAINING_TYPE_COLORS: Record<string, string> = {
  mandatory: 'bg-red-500/15 text-red-400',
  awareness: 'bg-blue-500/15 text-blue-400',
  certification: 'bg-purple-500/15 text-purple-400',
  refresher: 'bg-yellow-500/15 text-yellow-400',
  onboarding: 'bg-green-500/15 text-green-400',
};

const TRAINING_TYPE_LABELS: Record<string, string> = {
  mandatory: 'Obowiązkowe',
  awareness: 'Świadomość',
  certification: 'Certyfikacja',
  refresher: 'Odświeżenie',
  onboarding: 'Onboarding',
};

function formatDeadline(dateStr: string | null | undefined): { text: string; overdue: boolean } {
  if (!dateStr) return { text: '\u2014', overdue: false };
  try {
    const date = new Date(dateStr);
    const now = new Date();
    const overdue = date < now;
    const text = new Intl.DateTimeFormat('pl-PL', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    }).format(date);
    return { text, overdue };
  } catch {
    return { text: '\u2014', overdue: false };
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

function AudienceChips({ audience }: { audience: string[] }) {
  const visible = audience.slice(0, 3);
  const remaining = audience.length - 3;

  return (
    <div className="flex flex-wrap items-center gap-1">
      {visible.map((a) => (
        <span
          key={a}
          className="inline-flex rounded-full px-2 py-0.5 text-xs bg-[var(--surface)] text-[var(--text-secondary)]"
        >
          {a}
        </span>
      ))}
      {remaining > 0 && (
        <span className="text-xs text-[var(--text-muted)]">+{remaining}</span>
      )}
    </div>
  );
}

export function TrainingsTable({
  trainings,
  isLoading,
  areaFilter,
  statusFilter,
  onAreaChange,
  onStatusChange,
}: TrainingsTableProps) {
  const filtered = useMemo(() => trainings ?? [], [trainings]);

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
                    <GraduationCap className="h-10 w-10 opacity-40" />
                    <span className="text-sm">Nie znaleziono szkoleń compliance</span>
                  </div>
                </td>
              </tr>
            ) : (
              filtered.map((training) => {
                const deadline = formatDeadline(training.deadline);
                return (
                  <Link
                    key={training.id}
                    href={`/compliance/trainings/${training.id}`}
                    className="contents"
                  >
                    <tr className="border-b border-[var(--border)] cursor-pointer hover:bg-[var(--surface-hover)] transition-colors">
                      <td className="px-4 py-3 font-medium text-[var(--text)] max-w-[260px] truncate">
                        {training.title}
                      </td>
                      <td className="px-4 py-3">
                        <ComplianceBadge type="area" value={training.area_code} />
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={cn(
                            'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
                            TRAINING_TYPE_COLORS[training.training_type] ?? 'bg-gray-500/10 text-gray-400',
                          )}
                        >
                          {TRAINING_TYPE_LABELS[training.training_type] ?? training.training_type}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <AudienceChips audience={training.target_audience ?? []} />
                      </td>
                      <td
                        className={cn(
                          'px-4 py-3',
                          deadline.overdue ? 'text-red-400 font-medium' : 'text-[var(--text-secondary)]',
                        )}
                      >
                        {deadline.text}
                      </td>
                      <td className="px-4 py-3">
                        <ComplianceBadge type="training" value={training.status} />
                      </td>
                    </tr>
                  </Link>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
