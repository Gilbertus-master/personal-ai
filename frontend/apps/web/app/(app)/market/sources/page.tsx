'use client';

import { useState } from 'react';
import { RbacGate, SourceTable } from '@gilbertus/ui';
import { useMarketDashboard, useAddMarketSource } from '@/lib/hooks/use-market';
import { Plus } from 'lucide-react';

const SOURCE_TYPES = [
  { value: 'rss', label: 'RSS' },
  { value: 'api', label: 'API' },
  { value: 'web', label: 'Web' },
] as const;

export default function MarketSourcesPage() {
  const { data: dashboard, isLoading, error } = useMarketDashboard();
  const addMutation = useAddMarketSource();

  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [sourceType, setSourceType] = useState<string>('rss');

  const handleAdd = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !url.trim()) return;
    addMutation.mutate(
      { name: name.trim(), url: url.trim(), source_type: sourceType },
      {
        onSuccess: () => {
          setName('');
          setUrl('');
          setSourceType('rss');
        },
      },
    );
  };

  return (
    <RbacGate
      roles={['director', 'board', 'ceo']}
      permission="data:read:department"
      fallback={
        <div className="flex items-center justify-center h-64 text-[var(--text-secondary)]">
          Brak dostępu do źródeł danych
        </div>
      }
    >
      <div className="space-y-6">
        {/* Header */}
        <h1 className="text-2xl font-bold text-[var(--text)]">Źródła danych</h1>

        {/* Add source form */}
        <form onSubmit={handleAdd} className="flex flex-wrap items-end gap-3 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
          <div className="flex-1 min-w-[150px]">
            <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Nazwa</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="np. URE RSS"
              required
              className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-1.5 text-sm text-[var(--text)] placeholder:text-[var(--text-muted)]"
            />
          </div>
          <div className="flex-[2] min-w-[200px]">
            <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">URL</label>
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://..."
              required
              className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-1.5 text-sm text-[var(--text)] placeholder:text-[var(--text-muted)]"
            />
          </div>
          <div className="w-28">
            <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Typ</label>
            <select
              value={sourceType}
              onChange={(e) => setSourceType(e.target.value)}
              className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-1.5 text-sm text-[var(--text)]"
            >
              {SOURCE_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>
          <button
            type="submit"
            disabled={addMutation.isPending}
            className="flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-4 py-1.5 text-sm font-medium text-white hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            <Plus size={14} />
            {addMutation.isPending ? 'Dodawanie...' : 'Dodaj'}
          </button>
        </form>

        {/* Success toast */}
        {addMutation.isSuccess && (
          <div className="rounded-lg border border-green-500/30 bg-green-500/10 px-4 py-2.5 text-sm text-green-400">
            Źródło dodane pomyślnie
          </div>
        )}

        {/* Error on add */}
        {addMutation.isError && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-2.5 text-sm text-red-400">
            Błąd dodawania źródła: {(addMutation.error as Error).message}
          </div>
        )}

        {/* Loading skeleton */}
        {isLoading && (
          <div className="h-48 animate-pulse rounded-lg bg-[var(--bg-hover)]" />
        )}

        {/* Error state */}
        {error && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
            Błąd ładowania źródeł: {(error as Error).message}
          </div>
        )}

        {/* Sources table */}
        {dashboard && <SourceTable sources={dashboard.sources} />}
      </div>
    </RbacGate>
  );
}
