'use client';

import { useState } from 'react';
import { RbacGate, GoalCard } from '@gilbertus/ui';
import { useGoals, useCreateGoal } from '@/lib/hooks/use-finance';
import { useFinanceStore } from '@/lib/stores/finance-store';
import type { StrategicGoal, CreateGoalRequest } from '@gilbertus/api-client';
import {
  Target,
  Plus,
  X,
  AlertTriangle,
  Clock,
  Filter,
} from 'lucide-react';
import { useRouter } from 'next/navigation';

const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: 'on_track', label: 'Na dobrej drodze' },
  { value: 'at_risk', label: 'Zagrożony' },
  { value: 'behind', label: 'Opóźniony' },
  { value: 'achieved', label: 'Osiągnięty' },
  { value: 'cancelled', label: 'Anulowany' },
];

const AREA_OPTIONS: { value: string; label: string }[] = [
  { value: 'business', label: 'Biznes' },
  { value: 'trading', label: 'Trading' },
  { value: 'operations', label: 'Operacje' },
  { value: 'people', label: 'Ludzie' },
  { value: 'technology', label: 'Technologia' },
  { value: 'wellbeing', label: 'Wellbeing' },
];

const STATUS_COLOR: Record<string, string> = {
  on_track: 'bg-emerald-500/20 text-emerald-400',
  at_risk: 'bg-amber-500/20 text-amber-400',
  behind: 'bg-red-500/20 text-red-400',
  achieved: 'bg-blue-500/20 text-blue-400',
  cancelled: 'bg-zinc-500/20 text-zinc-400',
};

function KpiCard({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
      <p className="text-xs font-medium uppercase text-[var(--text-secondary)]">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${color ?? 'text-[var(--text)]'}`}>{value}</p>
    </div>
  );
}

export default function GoalsPage() {
  const router = useRouter();
  const store = useFinanceStore();
  const { data: summary, isLoading, error } = useGoals();
  const createMutation = useCreateGoal();
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState<CreateGoalRequest>({
    title: '',
    target_value: 0,
    unit: '',
    deadline: '',
    company: '',
    area: '',
  });

  const handleCreate = () => {
    if (!form.title || !form.target_value) return;
    createMutation.mutate(form, {
      onSuccess: () => {
        setShowCreate(false);
        setForm({ title: '', target_value: 0, unit: '', deadline: '', company: '', area: '' });
      },
    });
  };

  // Group goals by area (from by_area keys)
  const goalsByArea: Record<string, StrategicGoal[]> = {};
  const allGoals = (summary as unknown as { goals?: StrategicGoal[] })?.goals ?? [];
  const filtered = allGoals.filter((g) => {
    if (store.goalsAreaFilter && g.area !== store.goalsAreaFilter) return false;
    if (store.goalsStatusFilter && g.status !== store.goalsStatusFilter) return false;
    return true;
  });
  for (const g of filtered) {
    const area = g.area ?? 'inne';
    if (!goalsByArea[area]) goalsByArea[area] = [];
    goalsByArea[area].push(g);
  }

  const statusCounts = summary?.by_status ?? {};

  return (
    <RbacGate
      roles={['owner', 'board', 'ceo']}
      permission="financials:read"
      fallback={
        <div className="flex h-64 items-center justify-center text-[var(--text-secondary)]">
          Brak dostępu do modułu Finanse
        </div>
      }
    >
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Target size={20} className="text-[var(--accent)]" />
            <h1 className="text-2xl font-bold text-[var(--text)]">Cele strategiczne</h1>
          </div>
          <button
            type="button"
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 transition-opacity"
          >
            <Plus size={14} />
            Nowy cel
          </button>
        </div>

        {/* Loading */}
        {isLoading && (
          <div className="space-y-4">
            <div className="grid grid-cols-5 gap-4">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="h-20 animate-pulse rounded-lg bg-[var(--surface)]" />
              ))}
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
            Błąd ładowania celów: {(error as Error).message}
          </div>
        )}

        {summary && (
          <>
            {/* KPI row */}
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
              <KpiCard label="Łącznie celów" value={summary.total_goals} />
              <KpiCard label="Na dobrej drodze" value={statusCounts['on_track'] ?? 0} color="text-emerald-400" />
              <KpiCard label="Zagrożone" value={statusCounts['at_risk'] ?? 0} color="text-amber-400" />
              <KpiCard label="Opóźnione" value={statusCounts['behind'] ?? 0} color="text-red-400" />
              <KpiCard label="Osiągnięte" value={statusCounts['achieved'] ?? 0} color="text-blue-400" />
            </div>

            {/* Filter bar */}
            <div className="flex flex-wrap items-center gap-3 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-3">
              <Filter size={14} className="text-[var(--text-secondary)]" />
              <select
                value={store.goalsAreaFilter ?? ''}
                onChange={(e) => store.setGoalsAreaFilter(e.target.value || null)}
                className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-2.5 py-1.5 text-xs text-[var(--text)]"
              >
                <option value="">Wszystkie obszary</option>
                {AREA_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
              <select
                value={store.goalsStatusFilter ?? ''}
                onChange={(e) => store.setGoalsStatusFilter(e.target.value || null)}
                className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-2.5 py-1.5 text-xs text-[var(--text)]"
              >
                <option value="">Wszystkie statusy</option>
                {STATUS_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>

            {/* Goals grouped by area */}
            {Object.entries(goalsByArea).map(([area, goals]) => {
              const areaLabel = AREA_OPTIONS.find((a) => a.value === area)?.label ?? area;
              return (
                <div key={area}>
                  <h2 className="mb-3 text-sm font-semibold text-[var(--text)]">{areaLabel}</h2>
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {goals.map((goal) => (
                      <GoalCard
                        key={goal.id}
                        goal={goal}
                        onClick={() => router.push(`/finance/goals/${goal.id}`)}
                      />
                    ))}
                  </div>
                </div>
              );
            })}

            {filtered.length === 0 && (
              <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 text-center text-sm text-[var(--text-secondary)]">
                Brak celów spełniających filtry
              </div>
            )}

            {/* Top risks */}
            {summary.top_risks.length > 0 && (
              <div>
                <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-[var(--text)]">
                  <AlertTriangle size={14} className="text-amber-400" />
                  Największe ryzyka
                </h2>
                <div className="space-y-2">
                  {summary.top_risks.map((risk, i) => {
                    const r = risk as { title?: string; description?: string; status?: string };
                    return (
                      <div
                        key={i}
                        className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm"
                      >
                        <span className="font-medium text-amber-400">{r.title ?? `Ryzyko ${i + 1}`}</span>
                        {r.description && (
                          <p className="mt-0.5 text-[var(--text-secondary)]">{r.description}</p>
                        )}
                        {r.status && (
                          <span className={`mt-1 inline-block rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLOR[r.status] ?? 'bg-zinc-500/20 text-zinc-400'}`}>
                            {STATUS_OPTIONS.find((s) => s.value === r.status)?.label ?? r.status}
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Upcoming deadlines */}
            {summary.upcoming_deadlines.length > 0 && (
              <div>
                <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-[var(--text)]">
                  <Clock size={14} className="text-[var(--accent)]" />
                  Zbliżające się terminy
                </h2>
                <div className="space-y-2">
                  {summary.upcoming_deadlines.map((dl, i) => {
                    const d = dl as { title?: string; deadline?: string; pct_complete?: number };
                    return (
                      <div
                        key={i}
                        className="flex items-center justify-between rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm"
                      >
                        <span className="font-medium text-[var(--text)]">{d.title ?? `Cel ${i + 1}`}</span>
                        <div className="flex items-center gap-3">
                          {d.pct_complete != null && (
                            <span className="text-xs text-[var(--text-secondary)]">
                              {d.pct_complete.toFixed(0)}%
                            </span>
                          )}
                          {d.deadline && (
                            <span className="text-xs font-medium text-[var(--accent)]">
                              {d.deadline}
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </>
        )}

        {/* Create goal dialog */}
        {showCreate && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
            <div className="w-full max-w-md rounded-lg border border-[var(--border)] bg-[var(--bg)] p-6 shadow-xl">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-lg font-bold text-[var(--text)]">Nowy cel strategiczny</h2>
                <button type="button" onClick={() => setShowCreate(false)}>
                  <X size={18} className="text-[var(--text-secondary)] hover:text-[var(--text)]" />
                </button>
              </div>

              <div className="space-y-3">
                <div>
                  <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
                    Tytuł
                  </label>
                  <input
                    type="text"
                    value={form.title}
                    onChange={(e) => setForm({ ...form, title: e.target.value })}
                    className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text)]"
                    placeholder="Np. Zwiększenie przychodów REH"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
                      Wartość docelowa
                    </label>
                    <input
                      type="number"
                      value={form.target_value || ''}
                      onChange={(e) => setForm({ ...form, target_value: Number(e.target.value) })}
                      className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text)]"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
                      Jednostka
                    </label>
                    <input
                      type="text"
                      value={form.unit ?? ''}
                      onChange={(e) => setForm({ ...form, unit: e.target.value })}
                      className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text)]"
                      placeholder="PLN, %, szt."
                    />
                  </div>
                </div>

                <div>
                  <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
                    Termin
                  </label>
                  <input
                    type="date"
                    value={form.deadline ?? ''}
                    onChange={(e) => setForm({ ...form, deadline: e.target.value })}
                    className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text)]"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
                      Spółka
                    </label>
                    <input
                      type="text"
                      value={form.company ?? ''}
                      onChange={(e) => setForm({ ...form, company: e.target.value })}
                      className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text)]"
                      placeholder="REH, REF"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
                      Obszar
                    </label>
                    <select
                      value={form.area ?? ''}
                      onChange={(e) => setForm({ ...form, area: e.target.value })}
                      className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text)]"
                    >
                      <option value="">Wybierz obszar</option>
                      {AREA_OPTIONS.map((opt) => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>

              <div className="mt-5 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowCreate(false)}
                  className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--surface)] transition-colors"
                >
                  Anuluj
                </button>
                <button
                  type="button"
                  onClick={handleCreate}
                  disabled={!form.title || !form.target_value || createMutation.isPending}
                  className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 transition-opacity disabled:opacity-50"
                >
                  {createMutation.isPending ? 'Tworzenie...' : 'Utwórz cel'}
                </button>
              </div>

              {createMutation.isError && (
                <p className="mt-2 text-xs text-red-400">
                  Błąd: {(createMutation.error as Error).message}
                </p>
              )}
            </div>
          </div>
        )}
      </div>
    </RbacGate>
  );
}
