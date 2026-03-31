'use client';

import {
  RbacGate,
  WorkforceTable,
  RoadmapTimeline,
} from '@gilbertus/ui';
import {
  useAutomationOverview,
  useAutomationRoadmap,
  useWorkProfile,
  useAnalyzeEmployee,
  useAnalyzeAllEmployees,
} from '@/lib/hooks/use-process-intel';
import { useProcessStore } from '@/lib/stores/process-store';
import type { WorkforceCandidate } from '@gilbertus/ui';
import {
  Users,
  UserCheck,
  Percent,
  Banknote,
  RefreshCw,
  AlertTriangle,
  UserSearch,
} from 'lucide-react';

function KpiCard({
  label,
  value,
  icon: Icon,
  suffix,
}: {
  label: string;
  value: number | string;
  icon: typeof Users;
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

function AutomationBar({ pct }: { pct: number }) {
  const rounded = Math.round(pct);
  const color = rounded >= 70 ? 'bg-green-500' : rounded >= 40 ? 'bg-amber-500' : 'bg-red-500';
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-24 rounded-full bg-[var(--border)]">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${rounded}%` }} />
      </div>
      <span className="text-xs font-medium text-[var(--text-secondary)]">{rounded}%</span>
    </div>
  );
}

export default function WorkforcePage() {
  const store = useProcessStore();
  const { data: overview, isLoading: overviewLoading, error: overviewError } = useAutomationOverview();
  const { data: roadmap } = useAutomationRoadmap();
  const { data: profile, isLoading: profileLoading } = useWorkProfile(store.selectedEmployee ?? '');

  const analyzeMut = useAnalyzeEmployee();
  const analyzeAllMut = useAnalyzeAllEmployees();

  const candidates: WorkforceCandidate[] = (overview?.top_automation_candidates ?? []) as WorkforceCandidate[];

  // Roadmap data for timeline
  const roadmapData = roadmap?.roadmap?.map((q) => ({
    quarter: q.quarter,
    items: (q.initiatives as { name?: string; [key: string]: unknown }[]).map((init) => ({
      name: String(init.name ?? init.task ?? ''),
      ...init,
    })),
  })) ?? [];

  return (
    <RbacGate
      roles={['owner', 'ceo']}
      permission="evaluations:read:all"
      fallback={
        <div className="flex items-center justify-center h-64 text-[var(--text-secondary)]">
          Brak dostepu — tylko CEO
        </div>
      }
    >
      <div className="space-y-6">
        {/* Warning banner */}
        <div className="flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-2.5 text-sm text-amber-400">
          <AlertTriangle size={16} />
          Dane poufne — tylko CEO
        </div>

        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-[var(--text)]">Analiza sily roboczej</h1>
          <button
            type="button"
            onClick={() => analyzeAllMut.mutate({})}
            disabled={analyzeAllMut.isPending}
            className="flex items-center gap-2 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            <RefreshCw size={14} className={analyzeAllMut.isPending ? 'animate-spin' : ''} />
            {analyzeAllMut.isPending ? 'Analizowanie...' : 'Analizuj wszystkich'}
          </button>
        </div>

        {/* Mutation toasts */}
        {analyzeAllMut.isSuccess && analyzeAllMut.data && (
          <div className="rounded-lg border border-green-500/30 bg-green-500/10 px-4 py-2.5 text-sm text-green-400">
            Analiza zakonczona: {analyzeAllMut.data.message}
          </div>
        )}
        {analyzeMut.isSuccess && (
          <div className="rounded-lg border border-green-500/30 bg-green-500/10 px-4 py-2.5 text-sm text-green-400">
            Analiza pracownika zakonczona
          </div>
        )}
        {(analyzeAllMut.error ?? analyzeMut.error) && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
            Blad: {((analyzeAllMut.error ?? analyzeMut.error) as Error).message}
          </div>
        )}

        {/* Loading skeleton */}
        {overviewLoading && (
          <div className="space-y-4">
            <div className="grid grid-cols-4 gap-4">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-20 animate-pulse rounded-lg bg-[var(--surface)]" />
              ))}
            </div>
            <div className="h-40 animate-pulse rounded-lg bg-[var(--surface)]" />
          </div>
        )}

        {/* Error */}
        {overviewError && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
            Blad ladowania danych: {(overviewError as Error).message}
          </div>
        )}

        {overview && (
          <>
            {/* KPI row */}
            <div className="grid grid-cols-4 gap-4">
              <KpiCard label="Pracownicy" value={overview.total_employees} icon={Users} />
              <KpiCard label="Przeanalizowani" value={overview.analyzed} icon={UserCheck} />
              <KpiCard
                label="Srednia automatyzacja"
                value={`${Math.round(overview.avg_automatable_pct)}%`}
                icon={Percent}
              />
              <KpiCard
                label="Potencjalne oszczednosci"
                value={new Intl.NumberFormat('pl-PL', {
                  style: 'currency',
                  currency: 'PLN',
                  maximumFractionDigits: 0,
                }).format(
                  candidates.reduce(
                    (sum, c) => sum + Number((c as Record<string, unknown>).potential_savings_pln ?? 0),
                    0,
                  ),
                )}
                icon={Banknote}
              />
            </div>

            {/* Workforce table */}
            <div>
              <h2 className="mb-3 text-sm font-semibold text-[var(--text)]">
                Kandydaci do automatyzacji ({candidates.length})
              </h2>
              <WorkforceTable
                candidates={candidates}
                onRowClick={(slug) => store.setSelectedEmployee(slug)}
              />
            </div>

            {/* Selected employee detail */}
            {store.selectedEmployee && (
              <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <UserSearch size={16} className="text-[var(--accent)]" />
                    <h2 className="text-sm font-semibold text-[var(--text)]">
                      Profil: {store.selectedEmployee}
                    </h2>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => analyzeMut.mutate(store.selectedEmployee!)}
                      disabled={analyzeMut.isPending}
                      className="flex items-center gap-1.5 rounded-md bg-[var(--accent)]/10 px-3 py-1.5 text-xs font-medium text-[var(--accent)] transition-colors hover:bg-[var(--accent)]/20 disabled:opacity-50"
                    >
                      <RefreshCw size={12} className={analyzeMut.isPending ? 'animate-spin' : ''} />
                      {analyzeMut.isPending ? 'Analizowanie...' : 'Analizuj'}
                    </button>
                    <button
                      type="button"
                      onClick={() => store.setSelectedEmployee(null)}
                      className="rounded-md bg-red-500/10 px-3 py-1.5 text-xs font-medium text-red-400 transition-colors hover:bg-red-500/20"
                    >
                      Zamknij
                    </button>
                  </div>
                </div>

                {profileLoading && (
                  <div className="space-y-3">
                    {[1, 2, 3].map((i) => (
                      <div key={i} className="h-8 animate-pulse rounded bg-[var(--bg)]" />
                    ))}
                  </div>
                )}

                {profile && (
                  <div className="space-y-5">
                    {/* Person info */}
                    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                      <div>
                        <span className="text-[10px] uppercase text-[var(--text-secondary)]">Osoba</span>
                        <p className="text-sm font-medium text-[var(--text)]">{profile.person_name}</p>
                      </div>
                      <div>
                        <span className="text-[10px] uppercase text-[var(--text-secondary)]">Rola</span>
                        <p className="text-sm font-medium text-[var(--text)]">{profile.person_role}</p>
                      </div>
                      <div>
                        <span className="text-[10px] uppercase text-[var(--text-secondary)]">Automatyzacja</span>
                        <AutomationBar pct={profile.automatable_pct} />
                      </div>
                      <div>
                        <span className="text-[10px] uppercase text-[var(--text-secondary)]">Zastępowalność</span>
                        <p className="text-sm font-medium text-[var(--text)]">
                          {(profile.replaceability_score * 100).toFixed(0)}%
                        </p>
                      </div>
                    </div>

                    {/* Work activities table */}
                    {profile.work_activities.length > 0 && (
                      <div>
                        <h3 className="mb-2 text-xs font-semibold uppercase text-[var(--text-secondary)]">
                          Aktywnosci
                        </h3>
                        <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
                          <table className="w-full text-left text-sm">
                            <thead>
                              <tr className="border-b border-[var(--border)] bg-[var(--bg)]">
                                <th className="px-3 py-2 text-[10px] font-semibold uppercase text-[var(--text-secondary)]">Aktywność</th>
                                <th className="px-3 py-2 text-[10px] font-semibold uppercase text-[var(--text-secondary)]">Kategoria</th>
                                <th className="px-3 py-2 text-[10px] font-semibold uppercase text-[var(--text-secondary)]">Czestotliwosc</th>
                                <th className="px-3 py-2 text-[10px] font-semibold uppercase text-[var(--text-secondary)]">h/tydzien</th>
                                <th className="px-3 py-2 text-[10px] font-semibold uppercase text-[var(--text-secondary)]">Automatyzacja</th>
                              </tr>
                            </thead>
                            <tbody>
                              {profile.work_activities.map((act, idx) => (
                                <tr
                                  key={idx}
                                  className="border-b border-[var(--border)] last:border-b-0"
                                >
                                  <td className="px-3 py-2 text-xs text-[var(--text)]">{act.activity}</td>
                                  <td className="px-3 py-2 text-xs text-[var(--text-secondary)]">{act.category}</td>
                                  <td className="px-3 py-2 text-xs text-[var(--text-secondary)]">{act.frequency}</td>
                                  <td className="px-3 py-2 text-xs text-[var(--text)]">{act.hours_per_week}</td>
                                  <td className="px-3 py-2">
                                    <AutomationBar pct={act.automation_potential} />
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {/* Automation roadmap cards */}
                    {profile.automation_roadmap.length > 0 && (
                      <div>
                        <h3 className="mb-2 text-xs font-semibold uppercase text-[var(--text-secondary)]">
                          Plan automatyzacji
                        </h3>
                        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                          {profile.automation_roadmap.map((task, idx) => (
                            <div
                              key={idx}
                              className="rounded-lg border border-[var(--border)] bg-[var(--bg)] p-3"
                            >
                              <p className="text-sm font-medium text-[var(--text)]">{task.task}</p>
                              <div className="mt-2 flex flex-wrap gap-3 text-[10px] text-[var(--text-secondary)]">
                                <span>Modul: {task.gilbertus_module}</span>
                                <span>Dev: {task.dev_hours}h</span>
                                <span>
                                  Oszczednosci:{' '}
                                  {new Intl.NumberFormat('pl-PL', {
                                    style: 'currency',
                                    currency: 'PLN',
                                    maximumFractionDigits: 0,
                                  }).format(task.savings_monthly_pln)}
                                  /mies.
                                </span>
                                <span className="rounded-full bg-[var(--accent)]/10 px-2 py-0.5 font-semibold text-[var(--accent)]">
                                  {task.priority}
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Automation roadmap timeline */}
            {roadmapData.length > 0 && (
              <div>
                <h2 className="mb-3 text-sm font-semibold text-[var(--text)]">
                  Roadmapa automatyzacji
                </h2>
                <RoadmapTimeline roadmap={roadmapData} labelKey="name" />
              </div>
            )}
          </>
        )}
      </div>
    </RbacGate>
  );
}
