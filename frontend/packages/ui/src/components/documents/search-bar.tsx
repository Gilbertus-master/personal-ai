'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { Search, Loader2 } from 'lucide-react';

export interface SearchBarProps {
  query: string;
  onChange: (q: string) => void;
  onSubmit?: () => void;
  placeholder?: string;
  isLoading?: boolean;
}

export function SearchBar({
  query,
  onChange,
  onSubmit,
  placeholder = 'Szukaj w dokumentach...',
  isLoading = false,
}: SearchBarProps) {
  const [local, setLocal] = useState(query);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Sync external query changes
  useEffect(() => {
    setLocal(query);
  }, [query]);

  const debouncedChange = useCallback(
    (value: string) => {
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => onChange(value), 500);
    },
    [onChange],
  );

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const handleChange = (value: string) => {
    setLocal(value);
    debouncedChange(value);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      if (timerRef.current) clearTimeout(timerRef.current);
      onChange(local);
      onSubmit?.();
    }
  };

  return (
    <div className="relative">
      <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
        {isLoading ? (
          <Loader2 size={16} className="animate-spin" style={{ color: 'var(--text-secondary)' }} />
        ) : (
          <Search size={16} style={{ color: 'var(--text-secondary)' }} />
        )}
      </div>
      <input
        type="text"
        value={local}
        onChange={(e) => handleChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        className="block w-full rounded-md border py-2 pl-9 pr-3 text-sm outline-none transition-colors focus:ring-1"
        style={{
          backgroundColor: 'var(--surface)',
          borderColor: 'var(--border)',
          color: 'var(--text)',
        }}
      />
    </div>
  );
}
