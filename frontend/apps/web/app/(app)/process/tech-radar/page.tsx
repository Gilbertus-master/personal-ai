'use client';

import {
  RbacGate,
  TechRadarChart,
  TechSolutionCard,
  RoadmapTimeline,
} from '@gilbertus/ui';
import {
  useTechRadar,
  useTechRoadmap,
  useTechAlignment,
  useDiscoverTech,
  useUpdateTechStatus,
} from '@/lib/hooks/use-process-intel';
import { useProcessStore } from '@/lib/stores/process-store';
import type { TechSolution } from '@gilbertus/api-client';
import {
  Radar,
  Cpu,
  Banknote,
  Trophy,
  RefreshCw,
  Search,
  Target,
} from 'lucide-react';

const TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: 'build', label: 'Budowa' },
  { value: 'buy', label: 'Zakup' },
  { value: 'extend', label: 'Rozszerzenie' },
];

const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: 'proposed', label: 'Propozycja' },
  { value: 'approved', label: 'Zatwierdzony' },
  { value: 'in_development', label: 'W realizacji' },
  { value: 'deployed', label: 'Wdrożony' },
  { value: 'rejected', label: 'Odrzucony' },
];

function KpiCard({
  label,
  value,
  icon: Icon,
  suffix,
}: {
  label: string;
  value: number | string;
  icon: typeof Radar;
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
        {suffix && (
          <span className="ml-1 text-sm font-normal text-[var(--text-secondary)]">
            {suffix}
          </span>
        )}
      </p>
    </div>
  );
}

export default function TechRadarPage() {
  const store = useProcessStore();
  const { data: radar, isLoading: radarLoading, error: radarError } = useTechRadar();
  const { data: roadmap } = useTechRoadmap();
  const { data: alignment } = useTechAlignment();

  const discoverMut = useDiscoverTech();
  const statusMut = useUpdateTechStatus();

  // Flatten all solutions from by_type or by_status
  const allSolutions: TechSolution[] = radar
    ? Object.values(radar.by_type ?? {}).flat()
    : [];

  // Apply filters
  const filtered = allSolutions.filter((s) => {
    if (store.techTypeFilter && s.solution_type !== store.techTypeFilter) return false;
    if (store.techStatusFilter && s.status !== store.techStatusFilter) return false;
    return true;
  });

  // Top ROI solution
  const topRoi = radar?.top_10_by_roi?.[0];

  // Roadmap data for timeline
  const roadmapData = roadmap?.roadmap?.map((q) => ({
    quarter: q.quarter,
    items: q.solutions.map((s) => ({ name: s.name, status: s.status, ROI: `${s.roi_ratio.toFixed(1)}x` })),
  })) ?? [];

  return (
    <RbacGate
      roles={['board', 'ceo']}
      permission="config:write:system"
      fallback={
        <div className="flex items-center justify-center h-64 text-[var(--text-secondary)]">
          Brak dostepu do Radaru technologicznego
        </div>
      }
    >
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-[var(--text)]">Radar technologiczny</h1>
          <button
            type="button"
            onClick={() => discoverMut.mutate()}
            disabled={discoverMut.isPending}
            className="flex items-center gap-2 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            <RefreshCw size={14} className={discoverMut.isPending ? 'animate-spin' : ''} />
            {discoverMut.isPending ? 'Odkrywanie...' : 'Odkryj technologie'}
          </button>
        </div>

        {/* Success / error toasts */}
        {discoverMut.isSuccess && (
          <div className="rounded-lg border border-green-500/30 bg-green-500/10 px-4 py-2.5 text-sm text-green-400">
            Odkrywanie technologii zakonczone pomyslnie
          </div>
        )}
        {statusMut.isSuccess && (
          <div className="rounded-lg border border-green-500/30 bg-green-500/10 px-4 py-2.5 text-sm text-green-400">
            Status rozwiazania zaktualizowany
          </div>
        )}
        {(discoverMut.error ?? statusMut.error) && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
            Blad: {((discoverMut.error ?? statusMut.error) as Error).message}
          </div>
        )}

        {/* Loading skeleton */}
        {radarLoading && (
          <div className="space-y-4">
            <div className="grid grid-cols-3 gap-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-20 animate-pulse rounded-lg bg-[var(--surface)]" />
              ))}
            </div>
            <div className="h-[400px] animate-pulse rounded-lg bg-[var(--surface)]" />
          </div>
        )}

        {/* Error */}
        {radarError && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
            Blad ladowania danych: {(radarError as Error).message}
          </div>
        )}

        {radar && (
          <>
            {/* KPI row */}
            <div className="grid grid-cols-3 gap-4">
              <KpiCard
                label="Rozwiazania"
                value={radar.total_solutions}
                icon={Cpu}
              />
              <KpiCard
                label="Laczne oszczednosci"
                value={new Intl.NumberFormat('pl-PL', {
                  style: 'currency',
                  currency: 'PLN',
                  maximumFractionDigits: 0,
                }).format(radar.total_estimated_savings_pln)}
                icon={Banknote}
              />
              <KpiCard
                label="Top ROI"
                value={topRoi?.name ?? '—'}
                icon={Trophy}
                suffix={topRoi ? `${topRoi.roi_ratio.toFixed(1)}x` : undefined}
              />
            </div>

            {/* Radar chart */}
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6">
              <div className="flex items-center gap-2 mb-4">
                <Radar size={16} className="text-[var(--accent)]" />
                <h2 className="text-sm font-semibold text-[var(--text)]">Radar</h2>
              </div>
              {allSolutions.length === 0 ? (
                <div className="text-center text-sm text-[var(--text-secondary)] py-12">
                  Brak rozwiazań — kliknij &quot;Odkryj technologie&quot;
                </div>
              ) : (
                <div className="flex justify-center">
                  <TechRadarChart solutions={allSolutions} />
                </div>
              )}
            </div>

            {/* Filters */}
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Search size={14} className="text-[var(--text-secondary)]" />
                <select
                  value={store.techTypeFilter ?? ''}
                  onChange={(e) => store.setTechTypeFilter(e.target.value || null)}
                  className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-2.5 py-1.5 text-xs text-[var(--text)]"
                >
                  <option value="">Wszystkie typy</option>
                  {TYPE_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>
              <select
                value={store.techStatusFilter ?? ''}
                onChange={(e) => store.setTechStatusFilter(e.target.value || null)}
                className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-2.5 py-1.5 text-xs text-[var(--text)]"
              >
                <option value="">Wszystkie statusy</option>
                {STATUS_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>

            {/* Solutions list */}
            <div>
              <h2 className="mb-3 text-sm font-semibold text-[var(--text)]">
                Rozwiazania ({filtered.length})
              </h2>
              {filtered.length === 0 ? (
                <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 text-center text-sm text-[var(--text-secondary)]">
                  Brak rozwiazań pasujacych do filtrów
                </div>
              ) : (
                <div className="space-y-3">
                  {filtered.map((sol) => (
                    <TechSolutionCard
                      key={sol.id}
                      solution={sol}
                      onStatusChange={(id, status) =>
                        statusMut.mutate({ solutionId: id, status })
                      }
                    />
                  ))}
                </div>
              )}
            </div>

            {/* Roadmap */}
            {roadmapData.length > 0 && (
              <div>
                <h2 className="mb-3 text-sm font-semibold text-[var(--text)]">
                  Roadmapa technologiczna
                </h2>
                <RoadmapTimeline roadmap={roadmapData} labelKey="name" />
              </div>
            )}

            {/* Strategic alignment */}
            {alignment && alignment.strategic_goals.length > 0 && (
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <Target size={14} className="text-[var(--accent)]" />
                  <h2 className="text-sm font-semibold text-[var(--text)]">
                    Dopasowanie strategiczne ({(alignment.total_alignment_coverage * 100).toFixed(0)}%)
                  </h2>
                </div>
                <div className="space-y-3">
                  {alignment.strategic_goals.map((goal) => (
                    <div
                      key={goal.goal_id}
                      className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4"
                    >
                      <h3 className="text-sm font-medium text-[var(--text)]">{goal.goal_name}</h3>
                      {goal.supporting_solutions.length > 0 ? (
                        <div className="mt-2 flex flex-wrap gap-2">
                          {goal.supporting_solutions.map((s) => (
                            <span
                              key={s.id}
                              className="rounded-full bg-[var(--accent)]/10 px-2.5 py-0.5 text-[10px] font-medium text-[var(--accent)]"
                            >
                              {s.name}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <p className="mt-1 text-xs text-[var(--text-secondary)]">
                          Brak przypisanych rozwiazań
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </RbacGate>
  );
}
