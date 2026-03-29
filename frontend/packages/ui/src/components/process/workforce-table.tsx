'use client';

import { cn } from '../../lib/utils';

export interface WorkforceCandidate {
  person_name: string;
  automatable_pct: number;
  replaceability_score: number;
  person_role?: string;
  [key: string]: unknown;
}

export interface WorkforceTableProps {
  candidates: WorkforceCandidate[];
  onRowClick?: (slug: string) => void;
}

function automationColor(pct: number): string {
  if (pct >= 70) return 'bg-green-500';
  if (pct >= 40) return 'bg-amber-500';
  return 'bg-red-500';
}

function replaceabilityColor(score: number): string {
  if (score >= 0.7) return 'bg-red-500';
  if (score >= 0.4) return 'bg-amber-500';
  return 'bg-green-500';
}

function nameToSlug(name: string): string {
  return name
    .toLowerCase()
    .replace(/\s+/g, '-')
    .replace(/[^a-z0-9-]/g, '');
}

export function WorkforceTable({ candidates, onRowClick }: WorkforceTableProps) {
  if (candidates.length === 0) {
    return (
      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 text-center text-sm text-[var(--text-secondary)]">
        Brak danych o pracownikach
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-[var(--border)] bg-[var(--surface)]">
            <th className="px-4 py-2.5 text-xs font-semibold uppercase text-[var(--text-secondary)]">Osoba</th>
            <th className="px-4 py-2.5 text-xs font-semibold uppercase text-[var(--text-secondary)]">Automatyzacja %</th>
            <th className="px-4 py-2.5 text-xs font-semibold uppercase text-[var(--text-secondary)]">Zastępowalność</th>
            <th className="px-4 py-2.5 text-xs font-semibold uppercase text-[var(--text-secondary)]">Rola</th>
          </tr>
        </thead>
        <tbody>
          {candidates.map((c) => {
            const pct = Math.round(c.automatable_pct);
            const score = c.replaceability_score;
            const slug = nameToSlug(c.person_name);

            return (
              <tr
                key={c.person_name}
                onClick={() => onRowClick?.(slug)}
                className={cn(
                  'border-b border-[var(--border)] last:border-b-0 transition-colors hover:bg-[var(--surface-hover)]',
                  onRowClick && 'cursor-pointer',
                )}
              >
                <td className="px-4 py-2.5 font-medium text-[var(--text)]">{c.person_name}</td>
                <td className="px-4 py-2.5">
                  <div className="flex items-center gap-2">
                    <div className="h-1.5 w-16 rounded-full bg-[var(--border)]">
                      <div
                        className={cn('h-full rounded-full transition-all', automationColor(pct))}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="text-[10px] font-medium text-[var(--text-secondary)]">{pct}%</span>
                  </div>
                </td>
                <td className="px-4 py-2.5">
                  <div className="flex items-center gap-2">
                    <span
                      className={cn('inline-block h-2.5 w-2.5 rounded-full', replaceabilityColor(score))}
                    />
                    <span className="text-xs text-[var(--text-secondary)]">
                      {(score * 100).toFixed(0)}%
                    </span>
                  </div>
                </td>
                <td className="px-4 py-2.5 text-xs text-[var(--text-secondary)]">
                  {c.person_role ?? '—'}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
