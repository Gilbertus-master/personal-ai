'use client';

import { useMemo, useState, useRef, useEffect } from 'react';
import type { RaciEntry, RaciRole, ComplianceAreaCode, CreateRaciRequest } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';
import { AreaFilter } from './area-filter';

export interface RaciMatrixProps {
  entries: RaciEntry[];
  isLoading?: boolean;
  areaFilter: string | null;
  onAreaChange: (v: string | null) => void;
  onUpsert: (data: CreateRaciRequest) => void;
  isUpserting?: boolean;
}

const AREA_LABELS: Record<string, string> = {
  URE: 'URE',
  RODO: 'RODO',
  AML: 'AML',
  KSH: 'KSH',
  ESG: 'ESG',
  LABOR: 'Prawo pracy',
  TAX: 'Podatki',
  CONTRACT: 'Umowy',
  INTERNAL_AUDIT: 'Audyt',
};

const ROLE_COLORS: Record<RaciRole, string> = {
  responsible: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  accountable: 'bg-red-500/20 text-red-400 border-red-500/30',
  consulted: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  informed: 'bg-green-500/20 text-green-400 border-green-500/30',
};

const ROLE_LETTERS: Record<RaciRole, string> = {
  responsible: 'R',
  accountable: 'A',
  consulted: 'C',
  informed: 'I',
};

const ALL_ROLES: RaciRole[] = ['responsible', 'accountable', 'consulted', 'informed'];

interface PopoverState {
  areaCode: ComplianceAreaCode;
  personId: number;
  currentRole: RaciRole | null;
  x: number;
  y: number;
}

export function RaciMatrix({
  entries,
  isLoading,
  areaFilter,
  onAreaChange,
  onUpsert,
  isUpserting,
}: RaciMatrixProps) {
  const [popover, setPopover] = useState<PopoverState | null>(null);
  const [notes, setNotes] = useState('');
  const popoverRef = useRef<HTMLDivElement>(null);

  // Close popover on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setPopover(null);
      }
    }
    if (popover) {
      document.addEventListener('mousedown', handleClick);
      return () => document.removeEventListener('mousedown', handleClick);
    }
  }, [popover]);

  // Build matrix: rows = areas, columns = people
  const { areas, people, matrix } = useMemo(() => {
    const peopleMap = new Map<number, string>();
    const matrixMap = new Map<string, RaciEntry>();

    for (const entry of entries ?? []) {
      if (entry.area_code) {
        peopleMap.set(entry.person_id, entry.person_name);
        matrixMap.set(`${entry.area_code}_${entry.person_id}`, entry);
      }
    }

    const peopleList = Array.from(peopleMap.entries()).map(([id, name]) => ({ id, name }));
    peopleList.sort((a, b) => a.name.localeCompare(b.name, 'pl'));

    const areaList = Object.keys(AREA_LABELS) as ComplianceAreaCode[];

    return { areas: areaList, people: peopleList, matrix: matrixMap };
  }, [entries]);

  function handleCellClick(
    areaCode: ComplianceAreaCode,
    personId: number,
    e: React.MouseEvent,
  ) {
    const rect = (e.target as HTMLElement).getBoundingClientRect();
    const existing = matrix.get(`${areaCode}_${personId}`);
    setNotes(existing?.notes ?? '');
    setPopover({
      areaCode,
      personId,
      currentRole: existing?.role ?? null,
      x: rect.left,
      y: rect.bottom + 4,
    });
  }

  function handleRoleSelect(role: RaciRole | null) {
    if (!popover) return;
    onUpsert({
      area_code: popover.areaCode,
      person_id: popover.personId,
      role: role ?? undefined,
      notes: notes || undefined,
    });
    setPopover(null);
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-10 w-48 rounded bg-[var(--surface)] animate-pulse" />
        <div className="h-[400px] rounded-lg bg-[var(--surface)] animate-pulse" />
      </div>
    );
  }

  if (people.length === 0) {
    return (
      <div className="space-y-4">
        <AreaFilter value={areaFilter} onChange={onAreaChange} className="w-48" />
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-12 text-center text-[var(--text-secondary)]">
          Brak danych RACI. Przypisz role w poszczególnych obszarach compliance.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <AreaFilter value={areaFilter} onChange={onAreaChange} className="w-48" />

      <div className="border border-[var(--border)] rounded-lg overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] bg-[var(--surface)]">
              <th className="sticky left-0 z-10 bg-[var(--surface)] px-4 py-3 text-left text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider min-w-[140px]">
                Obszar
              </th>
              {people.map((person) => (
                <th
                  key={person.id}
                  className="px-3 py-3 text-center text-xs font-medium text-[var(--text-secondary)] min-w-[80px] whitespace-nowrap"
                >
                  {person.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {areas.map((areaCode) => (
              <tr key={areaCode} className="border-b border-[var(--border)]">
                <td className="sticky left-0 z-10 bg-[var(--bg,var(--surface))] px-4 py-3 text-sm font-medium text-[var(--text)] whitespace-nowrap border-r border-[var(--border)]">
                  {AREA_LABELS[areaCode] ?? areaCode}
                </td>
                {people.map((person) => {
                  const entry = matrix.get(`${areaCode}_${person.id}`);
                  return (
                    <td
                      key={person.id}
                      className="px-3 py-3 text-center cursor-pointer hover:bg-[var(--surface-hover)] transition-colors"
                      onClick={(e) => handleCellClick(areaCode, person.id, e)}
                    >
                      {entry ? (
                        <span
                          className={cn(
                            'inline-flex items-center justify-center w-8 h-8 rounded-md border text-sm font-bold',
                            ROLE_COLORS[entry.role],
                          )}
                        >
                          {ROLE_LETTERS[entry.role]}
                        </span>
                      ) : (
                        <span className="inline-flex items-center justify-center w-8 h-8 rounded-md border border-dashed border-[var(--border)] text-[var(--text-muted)] text-xs">
                          &mdash;
                        </span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-4 text-xs text-[var(--text-secondary)]">
        {ALL_ROLES.map((role) => (
          <div key={role} className="flex items-center gap-1.5">
            <span
              className={cn(
                'inline-flex items-center justify-center w-6 h-6 rounded border text-xs font-bold',
                ROLE_COLORS[role],
              )}
            >
              {ROLE_LETTERS[role]}
            </span>
            <span className="capitalize">{role}</span>
          </div>
        ))}
      </div>

      {/* Popover */}
      {popover && (
        <div
          ref={popoverRef}
          className="fixed z-50 rounded-lg border border-[var(--border)] bg-[var(--surface)] shadow-lg p-3 space-y-2"
          style={{ left: popover.x, top: popover.y }}
        >
          <div className="flex items-center gap-1.5">
            {ALL_ROLES.map((role) => (
              <button
                key={role}
                onClick={() => handleRoleSelect(role)}
                disabled={isUpserting}
                className={cn(
                  'w-9 h-9 rounded-md border text-sm font-bold transition-colors',
                  popover.currentRole === role
                    ? ROLE_COLORS[role]
                    : 'border-[var(--border)] text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]',
                )}
              >
                {ROLE_LETTERS[role]}
              </button>
            ))}
            <button
              onClick={() => handleRoleSelect(null)}
              disabled={isUpserting}
              className="px-2 h-9 rounded-md border border-[var(--border)] text-xs text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] transition-colors"
            >
              Usuń
            </button>
          </div>
          <input
            type="text"
            placeholder="Notatki (opcjonalne)"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            className="w-full rounded border border-[var(--border)] bg-transparent px-2 py-1 text-xs text-[var(--text)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--accent)]"
          />
        </div>
      )}
    </div>
  );
}
