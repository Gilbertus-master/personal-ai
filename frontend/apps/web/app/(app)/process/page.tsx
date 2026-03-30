'use client';

import { RbacGate, BusinessLineCard, ProcessCard } from '@gilbertus/ui';
import {
  useProcessDashboard,
  useBusinessLines,
  useProcesses,
  useDiscoverBusinessLines,
  useMineProcesses,
  useGenerateOptimizations,
} from '@/lib/hooks/use-process-intel';
import { useProcessStore } from '@/lib/stores/process-store';
import {
  Layers,
  GitBranch,
  Clock,
  Banknote,
  RefreshCw,
  Search,
  Lightbulb,
} from 'lucide-react';
import type { DiscoveredProcess } from '@gilbertus/api-client';

const PROCESS_TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: 'decision', label: 'Decyzja' },
  { value: 'approval', label: 'Zatwierdzenie' },
  { value: 'reporting', label: 'Raportowanie' },
  { value: 'trading', label: 'Trading' },
  { value: 'compliance', label: 'Compliance' },
  { value: 'communication', label: 'Komunikacja' },
  { value: 'operational', label: 'Operacyjny' },
];

function KpiCard({
  label,
  value,
  icon: Icon,
  suffix,
}: {
  label: string;
  value: number | string;
  icon: typeof Layers;
  suffix?: string;
}) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
      <div className="flex items-center gap-2 text-[var(--text-secondary)]">
        <Icon size={14} />
        <span className="text-xs font-medium uppercase">{label}</span>
      </div>
      <p className="mt-1.5 text-2xl font-bold text-[var(--text)]">
        {value}
        {suffix && <span className="ml-1 text-sm font-normal text-[var(--text-secondary)]">{suffix}</span>}
      </p>
    </div>
  );
}

function ActionButton({
  label,
  loadingLabel,
  isPending,
  onClick,
}: {
  label: string;
  loadingLabel: string;
  isPending: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={isPending}
      className="flex items-center gap-2 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white hover:opacity-90 transition-opacity disabled:opacity-50"
    >
      <RefreshCw size={14} className={isPending ? 'animate-spin' : ''} />
      {isPending ? loadingLabel : label}
    </button>
  );
}

export default function ProcessPage() {
  const store = useProcessStore();
  const { data: dashboard, isLoading: dashLoading, error: dashError } = useProcessDashboard();
  const { data: businessLines } = useBusinessLines();
  const { data: processes } = useProcesses(store.processTypeFilter ?? undefined);

  const discoverMut = useDiscoverBusinessLines();
  const mineMut = useMineProcesses();
  const optimizeMut = useGenerateOptimizations();

  const filteredProcesses: DiscoveredProcess[] = processes ?? [];
  const lines = businessLines?.business_lines ?? dashboard?.business_lines?.business_lines ?? [];
  const optimizations = dashboard?.optimizations;

  return (
    <RbacGate
      roles={['director', 'board', 'ceo']}
      permission="data:read:department"
      fallback={
        <div className="flex items-center justify-center h-64 text-[var(--text-secondary)]">
          Brak dostępu do modułu Inteligencja procesowa
        </div>
      }
    >
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-[var(--text)]">Inteligencja procesowa</h1>
          <div className="flex items-center gap-2">
            <ActionButton
              label="Odkryj linie"
              loadingLabel="W toku…"
              isPending={discoverMut.isPending}
              onClick={() => discoverMut.mutate()}
            />
            <ActionButton
              label="Wydobądź procesy"
              loadingLabel="W toku…"
              isPending={mineMut.isPending}
              onClick={() => mineMut.mutate()}
            />
            <ActionButton
              label="Generuj optymalizacje"
              loadingLabel="Generowanie..."
              isPending={optimizeMut.isPending}
              onClick={() => optimizeMut.mutate()}
            />
          </div>
        </div>

        {/* Background job status messages */}
        {discoverMut.jobStatus && discoverMut.jobStatus !== 'done' && (
          <div className="rounded-lg border border-blue-500/30 bg-blue-500/10 px-4 py-2.5 text-sm text-blue-400 flex items-center gap-2">
            <span className="inline-block h-2 w-2 rounded-full bg-blue-400 animate-pulse" />
            {discoverMut.jobStatus === 'queued' && 'Odkrywanie linii biznesowych w kolejce…'}
            {discoverMut.jobStatus === 'running' && 'Gilbertus analizuje dane i odkrywa linie biznesowe… (może potrwać ~60 sek)'}
            {discoverMut.jobStatus === 'error' && '❌ Błąd podczas odkrywania linii biznesowych'}
          </div>
        )}
        {discoverMut.jobStatus === 'done' && (
          <div className="rounded-lg border border-green-500/30 bg-green-500/10 px-4 py-2.5 text-sm text-green-400">
            ✓ Odkrywanie zakończone — dane zaktualizowane
          </div>
        )}
        {mineMut.jobStatus && mineMut.jobStatus !== 'done' && (
          <div className="rounded-lg border border-blue-500/30 bg-blue-500/10 px-4 py-2.5 text-sm text-blue-400 flex items-center gap-2">
            <span className="inline-block h-2 w-2 rounded-full bg-blue-400 animate-pulse" />
            {mineMut.jobStatus === 'running' && 'Gilbertus wydobywa procesy z danych… (może potrwać ~60 sek)'}
            {mineMut.jobStatus === 'queued' && 'Wydobywanie procesów w kolejce…'}
            {mineMut.jobStatus === 'error' && '❌ Błąd podczas wydobywania procesów'}
          </div>
        )}
        {mineMut.jobStatus === 'done' && (
          <div className="rounded-lg border border-green-500/30 bg-green-500/10 px-4 py-2.5 text-sm text-green-400">
            ✓ Wydobywanie zakończone — dane zaktualizowane
          </div>
        )}
        {optimizeMut.isSuccess && (
          <div className="rounded-lg border border-green-500/30 bg-green-500/10 px-4 py-2.5 text-sm text-green-400">
            Optymalizacje wygenerowane pomyślnie
          </div>
        )}

        {/* Loading skeleton */}
        {dashLoading && (
          <div className="space-y-4">
            <div className="grid grid-cols-4 gap-4">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-20 animate-pulse rounded-lg bg-[var(--bg-hover)]" />
              ))}
            </div>
            <div className="h-40 animate-pulse rounded-lg bg-[var(--bg-hover)]" />
          </div>
        )}

        {/* Error state */}
        {dashError && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
            Błąd ładowania danych: {(dashError as Error).message}
          </div>
        )}

        {/* KPI row */}
        {dashboard && (
          <>
            <div className="grid grid-cols-4 gap-4">
              <KpiCard label="Linie biznesowe" value={lines.length} icon={Layers} />
              <KpiCard label="Procesy" value={filteredProcesses.length} icon={GitBranch} />
              <KpiCard
                label="Oszczędność czasu"
                value={optimizations?.total_time_savings_hours ?? 0}
                icon={Clock}
                suffix="h"
              />
              <KpiCard
                label="Oszczędność kosztów"
                value={new Intl.NumberFormat('pl-PL', {
                  style: 'currency',
                  currency: 'PLN',
                  maximumFractionDigits: 0,
                }).format(optimizations?.total_cost_savings_pln ?? 0)}
                icon={Banknote}
              />
            </div>

            {/* Business Lines */}
            <div>
              <h2 className="mb-3 text-sm font-semibold text-[var(--text)]">
                Linie biznesowe ({lines.length})
              </h2>
              {lines.length === 0 ? (
                <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 text-center text-sm text-[var(--text-secondary)]">
                  Brak linii biznesowych — kliknij &quot;Odkryj linie&quot;
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
                  {lines.map((line) => (
                    <BusinessLineCard key={line.id} line={line} />
                  ))}
                </div>
              )}
            </div>

            {/* Processes */}
            <div>
              <div className="mb-3 flex items-center gap-3">
                <h2 className="text-sm font-semibold text-[var(--text)]">Procesy</h2>
                <div className="flex items-center gap-2">
                  <Search size={14} className="text-[var(--text-secondary)]" />
                  <select
                    value={store.processTypeFilter ?? ''}
                    onChange={(e) => store.setProcessTypeFilter(e.target.value || null)}
                    className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-2.5 py-1.5 text-xs text-[var(--text)]"
                  >
                    <option value="">Wszystkie typy</option>
                    {PROCESS_TYPE_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              {filteredProcesses.length === 0 ? (
                <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 text-center text-sm text-[var(--text-secondary)]">
                  Brak procesów — kliknij &quot;Wydobądź procesy&quot;
                </div>
              ) : (
                <div className="space-y-3">
                  {filteredProcesses.map((proc) => (
                    <ProcessCard key={proc.id} process={proc} />
                  ))}
                </div>
              )}
            </div>

            {/* Optimizations summary */}
            {optimizations && optimizations.total_plans > 0 && (
              <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
                <div className="flex items-center gap-2 mb-3">
                  <Lightbulb size={14} className="text-amber-400" />
                  <h2 className="text-sm font-semibold text-[var(--text)]">
                    Optymalizacje ({optimizations.total_plans} planów)
                  </h2>
                </div>
                <div className="flex items-center gap-6 text-sm text-[var(--text-secondary)]">
                  <span>
                    Czas: <strong className="text-[var(--text)]">{optimizations.total_time_savings_hours}h</strong>
                  </span>
                  <span>
                    Koszty:{' '}
                    <strong className="text-[var(--text)]">
                      {new Intl.NumberFormat('pl-PL', {
                        style: 'currency',
                        currency: 'PLN',
                        maximumFractionDigits: 0,
                      }).format(optimizations.total_cost_savings_pln)}
                    </strong>
                  </span>
                </div>
                {Array.isArray(optimizations.plans) && optimizations.plans.length > 0 && (
                  <div className="mt-3 space-y-1">
                    {(optimizations.plans as Record<string, unknown>[]).slice(0, 5).map((plan, idx) => (
                      <div key={idx} className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
                        <span className="h-1.5 w-1.5 rounded-full bg-[var(--accent)]" />
                        <span>{String(plan.name ?? plan.title ?? `Plan ${idx + 1}`)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </RbacGate>
  );
}
