'use client';

import { RbacGate, FlowTable } from '@gilbertus/ui';
import { useFlows, useMapFlows } from '@/lib/hooks/use-process-intel';
import {
  ArrowRightLeft,
  RefreshCw,
  AlertTriangle,
  CheckCircle,
  Gauge,
} from 'lucide-react';
import type { DataFlow } from '@gilbertus/api-client';

function FlowSummary({ flows }: { flows: DataFlow[] }) {
  const bottlenecks = { high: 0, medium: 0, low: 0 };
  let automated = 0;

  for (const f of flows) {
    bottlenecks[f.bottleneck]++;
    if (f.automation === 'automated' || f.automation === 'gilbertus') automated++;
  }

  const automationPct = flows.length > 0 ? Math.round((automated / flows.length) * 100) : 0;

  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
        <div className="flex items-center gap-2 text-[var(--text-secondary)]">
          <ArrowRightLeft size={14} />
          <span className="text-xs font-medium uppercase">Przepływy</span>
        </div>
        <p className="mt-1.5 text-2xl font-bold text-[var(--text)]">{flows.length}</p>
      </div>
      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
        <div className="flex items-center gap-2 text-red-400">
          <AlertTriangle size={14} />
          <span className="text-xs font-medium uppercase">Wąskie gardła</span>
        </div>
        <p className="mt-1.5 text-2xl font-bold text-[var(--text)]">
          {bottlenecks.high}
          <span className="ml-2 text-sm font-normal text-[var(--text-secondary)]">
            wysoki / {bottlenecks.medium} średni / {bottlenecks.low} niski
          </span>
        </p>
      </div>
      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
        <div className="flex items-center gap-2 text-green-400">
          <CheckCircle size={14} />
          <span className="text-xs font-medium uppercase">Zautomatyzowane</span>
        </div>
        <p className="mt-1.5 text-2xl font-bold text-[var(--text)]">{automated}</p>
      </div>
      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
        <div className="flex items-center gap-2 text-[var(--text-secondary)]">
          <Gauge size={14} />
          <span className="text-xs font-medium uppercase">Automatyzacja</span>
        </div>
        <p className="mt-1.5 text-2xl font-bold text-[var(--text)]">{automationPct}%</p>
      </div>
    </div>
  );
}

export default function FlowsPage() {
  const { data: flows, isLoading, error } = useFlows();
  const mapMut = useMapFlows();

  return (
    <RbacGate
      roles={['owner', 'director', 'board', 'ceo']}
      permission="data:read:department"
      fallback={
        <div className="flex items-center justify-center h-64 text-[var(--text-secondary)]">
          Brak dostępu do modułu Przepływy danych
        </div>
      }
    >
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-[var(--text)]">Przepływy danych</h1>
          <button
            type="button"
            onClick={() => { if (!mapMut.isPending) mapMut.mutate(); }}
            disabled={mapMut.isPending}
            className="flex items-center gap-2 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            <RefreshCw size={14} className={mapMut.isPending ? 'animate-spin' : ''} />
            {mapMut.isPending ? 'Mapowanie...' : 'Mapuj przepływy'}
          </button>
        </div>

        {/* Map success message */}
        {mapMut.isSuccess && (
          <div className="rounded-lg border border-green-500/30 bg-green-500/10 px-4 py-2.5 text-sm text-green-400">
            Mapowanie przepływów zakończone
          </div>
        )}

        {/* Loading skeleton */}
        {isLoading && (
          <div className="space-y-4">
            <div className="grid grid-cols-4 gap-4">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-20 animate-pulse rounded-lg bg-[var(--bg-hover)]" />
              ))}
            </div>
            <div className="h-48 animate-pulse rounded-lg bg-[var(--bg-hover)]" />
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
            Błąd ładowania przepływów: {(error as Error).message}
          </div>
        )}

        {/* Content */}
        {flows && (
          <>
            {/* Summary KPIs */}
            <FlowSummary flows={flows} />

            {/* Flows table */}
            <div>
              <h2 className="mb-3 text-sm font-semibold text-[var(--text)]">
                Wszystkie przepływy ({flows.length})
              </h2>
              <FlowTable flows={flows} />
            </div>
          </>
        )}
      </div>
    </RbacGate>
  );
}
