'use client';

import { cn } from '../../lib/utils';

export interface AreaFilterProps {
  value: string | null;
  onChange: (code: string | null) => void;
  className?: string;
}

const AREAS = [
  { code: 'URE', label: 'URE — Urząd Regulacji Energetyki', dot: 'bg-blue-400' },
  { code: 'RODO', label: 'RODO — Ochrona danych osobowych', dot: 'bg-purple-400' },
  { code: 'AML', label: 'AML — Przeciwdziałanie praniu pieniędzy', dot: 'bg-red-400' },
  { code: 'KSH', label: 'KSH — Prawo spółek handlowych', dot: 'bg-cyan-400' },
  { code: 'ESG', label: 'ESG — Zrównoważony rozwój', dot: 'bg-green-400' },
  { code: 'LABOR', label: 'Prawo pracy', dot: 'bg-amber-400' },
  { code: 'TAX', label: 'Prawo podatkowe', dot: 'bg-indigo-400' },
  { code: 'CONTRACT', label: 'Umowy i kontrakty', dot: 'bg-teal-400' },
  { code: 'INTERNAL_AUDIT', label: 'Audyt wewnętrzny', dot: 'bg-gray-400' },
] as const;

export function AreaFilter({ value, onChange, className }: AreaFilterProps) {
  return (
    <div className={cn('relative', className)}>
      <select
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value || null)}
        className={cn(
          'w-full appearance-none rounded-lg border border-[var(--border)] bg-[var(--surface)]',
          'px-3 py-2 pr-8 text-sm text-[var(--text)]',
          'focus:border-[var(--accent)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]',
        )}
      >
        <option value="">Wszystkie obszary</option>
        {AREAS.map((area) => (
          <option key={area.code} value={area.code}>
            {area.label}
          </option>
        ))}
      </select>
      <svg
        className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--text-secondary)]"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
      </svg>
    </div>
  );
}
