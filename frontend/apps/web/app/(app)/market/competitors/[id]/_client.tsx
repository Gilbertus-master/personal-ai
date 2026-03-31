'use client';

import { use } from 'react';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowLeft, Building2 } from 'lucide-react';
import { useCompetitorAnalysis, useCompetitorSignals } from '@/lib/hooks/use-market';
import { RbacGate, SwotCard, SignalTimeline, cn } from '@gilbertus/ui';
import type { CompetitorSignal } from '@gilbertus/api-client';

const SIGNAL_TYPES: { value: string; label: string }[] = [
  { value: '', label: 'Wszystkie typy' },
  { value: 'krs_change', label: 'KRS' },
  { value: 'hiring', label: 'Rekrutacja' },
  { value: 'media', label: 'Media' },
  { value: 'tender', label: 'Przetarg' },
  { value: 'financial', label: 'Finanse' },
];

const SEVERITY_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'Wszystkie' },
  { value: 'low', label: 'Niski' },
  { value: 'medium', label: 'Średni' },
  { value: 'high', label: 'Wysoki' },
];

const WATCH_BADGE: Record<string, { label: string; color: string }> = {
  active: { label: 'Aktywny', color: 'bg-green-500/20 text-green-400' },
  passive: { label: 'Pasywny', color: 'bg-amber-500/20 text-amber-400' },
  archived: { label: 'Archiwalny', color: 'bg-gray-500/20 text-gray-400' },
};

function CompetitorDetailContent({ id }: { id: number }) {
  const router = useRouter();
  const analysis = useCompetitorAnalysis(id);
  const signals = useCompetitorSignals({ competitor_id: id });

  const [typeFilter, setTypeFilter] = useState('');
  const [severityFilter, setSeverityFilter] = useState('');

  const filteredSignals = (signals.data ?? []).filter((s: CompetitorSignal) => {
    if (typeFilter && s.type !== typeFilter) return false;
    if (severityFilter && s.severity !== severityFilter) return false;
    return true;
  });

  const competitor = analysis.data?.competitor;
  const swot = analysis.data;

  return (
    <div className="space-y-6">
      {/* Back + Header */}
      <div>
        <button
          onClick={() => router.push('/market/competitors')}
          className="mb-3 inline-flex items-center gap-1 text-sm text-[var(--text-secondary)] hover:text-[var(--text)] transition-colors"
        >
          <ArrowLeft size={14} />
          Powrót do listy
        </button>

        {analysis.isLoading ? (
          <div className="space-y-2">
            <div className="h-8 w-64 animate-pulse rounded bg-[var(--surface)]" />
            <div className="h-4 w-48 animate-pulse rounded bg-[var(--surface)]" />
          </div>
        ) : competitor ? (
          <div className="flex items-start gap-3">
            <div className="mt-1 flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--surface)] border border-[var(--border)]">
              <Building2 size={20} className="text-[var(--text-secondary)]" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-[var(--text)]">{competitor}</h1>
              <div className="mt-1 flex items-center gap-2 text-xs text-[var(--text-secondary)]">
                {swot && (
                  <span>{swot.signals_count} sygnałów</span>
                )}
              </div>
            </div>
          </div>
        ) : (
          <h1 className="text-2xl font-bold text-[var(--text)]">Konkurent #{id}</h1>
        )}
      </div>

      {/* SWOT Analysis */}
      <div>
        <h2 className="mb-3 text-sm font-semibold uppercase text-[var(--text-secondary)]">Analiza SWOT</h2>
        {analysis.isLoading ? (
          <div className="grid grid-cols-2 gap-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-32 animate-pulse rounded-lg bg-[var(--surface)]" />
            ))}
          </div>
        ) : swot?.swot ? (
          <SwotCard analysis={swot} />
        ) : (
          <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 text-center text-sm text-[var(--text-secondary)]">
            Brak analizy — uruchom skanowanie aby wygenerować
          </div>
        )}
      </div>

      {/* Signals */}
      <div>
        <h2 className="mb-3 text-sm font-semibold uppercase text-[var(--text-secondary)]">Sygnały</h2>

        {/* Filter bar */}
        <div className="mb-4 flex items-center gap-2">
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-xs text-[var(--text)] focus:border-[var(--accent)] focus:outline-none"
          >
            {SIGNAL_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-xs text-[var(--text)] focus:border-[var(--accent)] focus:outline-none"
          >
            {SEVERITY_OPTIONS.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
        </div>

        {signals.isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-20 animate-pulse rounded-lg bg-[var(--surface)]" />
            ))}
          </div>
        ) : (
          <SignalTimeline signals={filteredSignals} />
        )}
      </div>
    </div>
  );
}

export function PageClient({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const competitorId = Number(id);

  return (
    <RbacGate
      roles={['owner', 'board', 'ceo', 'gilbertus_admin']}
      permission="data:read:all"
      fallback={
        <div className="flex items-center justify-center h-full">
          <p className="text-[var(--text-secondary)]">Brak dostępu do danych konkurencji</p>
        </div>
      }
    >
      <CompetitorDetailContent id={competitorId} />
    </RbacGate>
  );
}

export default PageClient;
