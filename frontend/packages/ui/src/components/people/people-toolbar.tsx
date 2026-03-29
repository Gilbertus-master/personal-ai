'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { Search, X, ArrowUpDown } from 'lucide-react';
import { cn } from '../../lib/utils';

const RELATIONSHIP_TYPES = ['employee', 'partner', 'client', 'contractor', 'other'] as const;
const STATUS_OPTIONS = ['all', 'active', 'inactive'] as const;
const SORT_OPTIONS = [
  { value: 'name', label: 'Imię' },
  { value: 'last_contact', label: 'Ostatni kontakt' },
  { value: 'status', label: 'Status' },
] as const;

interface PeopleToolbarProps {
  searchQuery: string;
  onSearchChange: (q: string) => void;
  filterType: string | null;
  onFilterTypeChange: (type: string | null) => void;
  filterStatus: string | null;
  onFilterStatusChange: (status: string | null) => void;
  sortBy: 'name' | 'last_contact' | 'status';
  onSortChange: (sort: 'name' | 'last_contact' | 'status') => void;
  sortOrder: 'asc' | 'desc';
  onSortOrderToggle: () => void;
  onResetFilters: () => void;
}

export function PeopleToolbar({
  searchQuery,
  onSearchChange,
  filterType,
  onFilterTypeChange,
  filterStatus,
  onFilterStatusChange,
  sortBy,
  onSortChange,
  sortOrder,
  onSortOrderToggle,
  onResetFilters,
}: PeopleToolbarProps) {
  const [localQuery, setLocalQuery] = useState(searchQuery);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const handleSearch = useCallback(
    (value: string) => {
      setLocalQuery(value);
      clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => onSearchChange(value), 300);
    },
    [onSearchChange],
  );

  useEffect(() => {
    return () => clearTimeout(debounceRef.current);
  }, []);

  // Sync external changes (e.g. reset)
  useEffect(() => {
    setLocalQuery(searchQuery);
  }, [searchQuery]);

  const hasActiveFilters = searchQuery !== '' || filterType !== null || filterStatus !== null;

  return (
    <div className="flex flex-wrap items-center gap-3 mb-4">
      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--text-secondary)]" />
        <input
          type="text"
          value={localQuery}
          onChange={(e) => handleSearch(e.target.value)}
          placeholder="Szukaj osoby..."
          className="bg-[var(--bg)] border border-[var(--border)] rounded-lg pl-9 pr-3 py-2 text-sm w-64 text-[var(--text)] placeholder:text-[var(--text-secondary)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
        />
      </div>

      {/* Relationship type chips */}
      <div className="flex items-center gap-1.5">
        {RELATIONSHIP_TYPES.map((type) => (
          <button
            key={type}
            onClick={() => onFilterTypeChange(filterType === type ? null : type)}
            className={cn(
              'rounded-full px-3 py-1 text-xs font-medium transition-colors',
              filterType === type
                ? 'bg-[var(--accent)] text-white'
                : 'bg-[var(--surface)] text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]',
            )}
          >
            {type}
          </button>
        ))}
      </div>

      {/* Status toggle */}
      <div className="flex items-center gap-1 rounded-lg border border-[var(--border)] p-0.5">
        {STATUS_OPTIONS.map((status) => (
          <button
            key={status}
            onClick={() => onFilterStatusChange(status === 'all' ? null : status)}
            className={cn(
              'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
              (status === 'all' && filterStatus === null) || filterStatus === status
                ? 'bg-[var(--accent)] text-white'
                : 'text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]',
            )}
          >
            {status === 'all' ? 'Wszyscy' : status === 'active' ? 'Aktywni' : 'Nieaktywni'}
          </button>
        ))}
      </div>

      {/* Sort */}
      <div className="flex items-center gap-1.5 ml-auto">
        <select
          value={sortBy}
          onChange={(e) => onSortChange(e.target.value as 'name' | 'last_contact' | 'status')}
          className="bg-[var(--bg)] border border-[var(--border)] rounded-lg px-2.5 py-1.5 text-xs text-[var(--text)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
        >
          {SORT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <button
          onClick={onSortOrderToggle}
          className="p-1.5 rounded-lg border border-[var(--border)] hover:bg-[var(--surface-hover)] transition-colors"
          title={sortOrder === 'asc' ? 'Rosnąco' : 'Malejąco'}
        >
          <ArrowUpDown className={cn('h-3.5 w-3.5 text-[var(--text-secondary)]', sortOrder === 'desc' && 'rotate-180')} />
        </button>
      </div>

      {/* Reset */}
      {hasActiveFilters && (
        <button
          onClick={onResetFilters}
          className="flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] transition-colors"
        >
          <X className="h-3 w-3" />
          Wyczyść filtry
        </button>
      )}
    </div>
  );
}
