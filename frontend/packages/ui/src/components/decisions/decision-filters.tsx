'use client';

import { useRef, useEffect, useCallback } from 'react';
import { Search } from 'lucide-react';

export interface DecisionFiltersProps {
  areaFilter: string | null;
  onAreaChange: (area: string | null) => void;
  searchQuery: string;
  onSearchChange: (q: string) => void;
}

const AREAS = [
  { value: null, label: 'Wszystkie' },
  { value: 'business', label: 'Biznes' },
  { value: 'trading', label: 'Trading' },
  { value: 'relationships', label: 'Relacje' },
  { value: 'wellbeing', label: 'Wellbeing' },
  { value: 'general', label: 'Ogólne' },
] as const;

export function DecisionFilters({
  areaFilter,
  onAreaChange,
  searchQuery,
  onSearchChange,
}: DecisionFiltersProps) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSearch = useCallback(
    (val: string) => {
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => onSearchChange(val), 300);
    },
    [onSearchChange],
  );

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  return (
    <div className="flex flex-wrap items-center gap-3">
      {/* Area select */}
      <select
        value={areaFilter ?? ''}
        onChange={(e) => onAreaChange(e.target.value || null)}
        className="rounded-md border px-3 py-1.5 text-sm"
        style={{
          backgroundColor: 'var(--surface)',
          borderColor: 'var(--border)',
          color: 'var(--text)',
        }}
      >
        {AREAS.map((a) => (
          <option key={a.value ?? 'all'} value={a.value ?? ''}>
            {a.label}
          </option>
        ))}
      </select>

      {/* Search */}
      <div className="relative flex-1" style={{ minWidth: 200 }}>
        <Search
          size={14}
          className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2"
          style={{ color: 'var(--text-secondary)' }}
        />
        <input
          ref={inputRef}
          type="text"
          defaultValue={searchQuery}
          onChange={(e) => handleSearch(e.target.value)}
          placeholder="Szukaj decyzji..."
          className="block w-full rounded-md border py-1.5 pl-8 pr-3 text-sm"
          style={{
            backgroundColor: 'var(--surface)',
            borderColor: 'var(--border)',
            color: 'var(--text)',
          }}
        />
      </div>
    </div>
  );
}
