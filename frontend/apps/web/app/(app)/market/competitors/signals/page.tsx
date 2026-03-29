'use client';

import { useState } from 'react';
import { useCompetitors, useCompetitorSignals } from '@/lib/hooks/use-market';
import { useMarketStore } from '@/lib/stores/market-store';
import { RbacGate, SignalTimeline } from '@gilbertus/ui';

const SIGNAL_TYPES: { value: string; label: string }[] = [
  { value: '', label: 'Wszystkie typy' },
  { value: 'krs_change', label: 'KRS' },
  { value: 'hiring', label: 'Rekrutacja' },
  { value: 'media', label: 'Media' },
  { value: 'tender', label: 'Przetarg' },
  { value: 'financial', label: 'Finanse' },
];

const DAYS_OPTIONS = [7, 14, 30, 60, 90];

function SignalsContent() {
  const store = useMarketStore();
  const competitors = useCompetitors();
  const [competitorFilter, setCompetitorFilter] = useState<number | undefined>(undefined);

  const signals = useCompetitorSignals({
    competitor_id: competitorFilter,
    signal_type: store.signalTypeFilter || undefined,
    days: store.signalDays,
  });

  const competitorList = competitors.data?.competitors ?? [];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-[var(--text)]">Sygnały konkurencji</h1>

      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={competitorFilter ?? ''}
          onChange={(e) => setCompetitorFilter(e.target.value ? Number(e.target.value) : undefined)}
          className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-xs text-[var(--text)] focus:border-[var(--accent)] focus:outline-none"
        >
          <option value="">Wszyscy konkurenci</option>
          {competitorList.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>

        <select
          value={store.signalTypeFilter ?? ''}
          onChange={(e) => store.setSignalTypeFilter(e.target.value || null)}
          className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-xs text-[var(--text)] focus:border-[var(--accent)] focus:outline-none"
        >
          {SIGNAL_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>

        <select
          value={store.signalDays}
          onChange={(e) => store.setSignalDays(Number(e.target.value))}
          className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-xs text-[var(--text)] focus:border-[var(--accent)] focus:outline-none"
        >
          {DAYS_OPTIONS.map((d) => (
            <option key={d} value={d}>Ostatnie {d} dni</option>
          ))}
        </select>
      </div>

      {/* Timeline */}
      {signals.isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-20 animate-pulse rounded-lg bg-[var(--surface)]" />
          ))}
        </div>
      ) : (
        <SignalTimeline signals={signals.data ?? []} showCompetitorName />
      )}
    </div>
  );
}

export default function CompetitorSignalsPage() {
  return (
    <RbacGate
      roles={['board', 'ceo', 'gilbertus_admin']}
      permission="data:read:all"
      fallback={
        <div className="flex items-center justify-center h-full">
          <p className="text-[var(--text-secondary)]">Brak dostępu do danych konkurencji</p>
        </div>
      }
    >
      <SignalsContent />
    </RbacGate>
  );
}
