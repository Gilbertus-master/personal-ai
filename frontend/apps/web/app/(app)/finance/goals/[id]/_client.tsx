'use client';

import { useState } from 'react';
import { useParams } from 'next/navigation';
import { RbacGate, GoalProgressChart } from '@gilbertus/ui';
import { useGoalDetail, useUpdateGoalProgress } from '@/lib/hooks/use-finance';
import type { StrategicGoal } from '@gilbertus/api-client';
import { cn } from '@gilbertus/ui';
import {
  Target,
  ArrowLeft,
  Calendar,
  Building2,
} from 'lucide-react';
import Link from 'next/link';

const STATUS_BADGE: Record<StrategicGoal['status'], { label: string; className: string }> = {
  on_track: { label: 'Na dobrej drodze', className: 'bg-emerald-500/20 text-emerald-400' },
  at_risk: { label: 'Zagrożony', className: 'bg-amber-500/20 text-amber-400' },
  behind: { label: 'Opóźniony', className: 'bg-red-500/20 text-red-400' },
  achieved: { label: 'Osiągnięty', className: 'bg-blue-500/20 text-blue-400' },
  cancelled: { label: 'Anulowany', className: 'bg-zinc-500/20 text-zinc-400' },
};

const AREA_BADGE: Record<StrategicGoal['area'], { label: string; className: string }> = {
  business: { label: 'Biznes', className: 'bg-indigo-500/20 text-indigo-400' },
  trading: { label: 'Trading', className: 'bg-cyan-500/20 text-cyan-400' },
  operations: { label: 'Operacje', className: 'bg-orange-500/20 text-orange-400' },
  people: { label: 'Ludzie', className: 'bg-pink-500/20 text-pink-400' },
  technology: { label: 'Technologia', className: 'bg-violet-500/20 text-violet-400' },
  wellbeing: { label: 'Wellbeing', className: 'bg-teal-500/20 text-teal-400' },
};

export function PageClient() {
  const params = useParams();
  const goalId = Number(params.id);
  const { data: goal, isLoading, error } = useGoalDetail(goalId);
  const updateMutation = useUpdateGoalProgress();
  const [updateValue, setUpdateValue] = useState('');
  const [updateNote, setUpdateNote] = useState('');
  const [showToast, setShowToast] = useState(false);

  const handleUpdate = () => {
    const val = Number(updateValue);
    if (!val) return;
    updateMutation.mutate(
      { goalId, data: { value: val, note: updateNote || undefined } },
      {
        onSuccess: () => {
          setUpdateValue('');
          setUpdateNote('');
          setShowToast(true);
          setTimeout(() => setShowToast(false), 3000);
        },
      },
    );
  };

  return (
    <RbacGate
      roles={['board', 'ceo']}
      permission="financials:read"
      fallback={
        <div className="flex h-64 items-center justify-center text-[var(--text-secondary)]">
          Brak dostępu do modułu Finanse
        </div>
      }
    >
      <div className="space-y-6">
        {/* Back link */}
        <Link
          href="/finance/goals"
          className="inline-flex items-center gap-1 text-sm text-[var(--text-secondary)] hover:text-[var(--accent)] transition-colors"
        >
          <ArrowLeft size={14} />
          Cele strategiczne
        </Link>

        {/* Loading */}
        {isLoading && (
          <div className="space-y-4">
            <div className="h-24 animate-pulse rounded-lg bg-[var(--surface)]" />
            <div className="h-64 animate-pulse rounded-lg bg-[var(--surface)]" />
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
            Błąd ładowania celu: {(error as Error).message}
          </div>
        )}

        {/* Success toast */}
        {showToast && (
          <div className="rounded-lg border border-green-500/30 bg-green-500/10 px-4 py-2.5 text-sm text-green-400">
            Postęp zaktualizowany
          </div>
        )}

        {goal && (
          <>
            {/* Header */}
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <Target size={18} className="text-[var(--accent)]" />
                    <h1 className="text-xl font-bold text-[var(--text)]">{goal.title}</h1>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={cn(
                        'rounded-full px-2 py-0.5 text-xs font-medium',
                        AREA_BADGE[goal.area].className,
                      )}
                    >
                      {AREA_BADGE[goal.area].label}
                    </span>
                    <span className="flex items-center gap-1 text-xs text-[var(--text-secondary)]">
                      <Building2 size={12} />
                      {goal.company}
                    </span>
                    <span className="flex items-center gap-1 text-xs text-[var(--text-secondary)]">
                      <Calendar size={12} />
                      {goal.deadline}
                    </span>
                  </div>
                </div>
                <span
                  className={cn(
                    'shrink-0 rounded-full px-3 py-1 text-xs font-medium',
                    STATUS_BADGE[goal.status].className,
                  )}
                >
                  {STATUS_BADGE[goal.status].label}
                </span>
              </div>
              {goal.description && (
                <p className="mt-3 text-sm text-[var(--text-secondary)]">{goal.description}</p>
              )}
            </div>

            {/* Progress chart */}
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
              <h2 className="mb-3 text-sm font-semibold text-[var(--text)]">Postęp</h2>
              <GoalProgressChart
                progress={goal.progress ?? []}
                targetValue={goal.target_value}
                unit={goal.unit}
              />
            </div>

            {/* Current vs target */}
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 text-center">
              <p className="text-sm text-[var(--text-secondary)]">Obecna wartość</p>
              <p className="mt-1 text-4xl font-bold text-[var(--text)]">
                {goal.current_value.toLocaleString('pl-PL')}
                <span className="ml-1 text-lg text-[var(--text-secondary)]">{goal.unit}</span>
              </p>
              <p className="mt-2 text-sm text-[var(--text-secondary)]">
                z {goal.target_value.toLocaleString('pl-PL')} {goal.unit}
              </p>
              <div className="mx-auto mt-3 h-3 max-w-xs rounded-full bg-[var(--bg)]">
                <div
                  className="h-full rounded-full bg-[var(--accent)] transition-all"
                  style={{ width: `${Math.min(goal.pct_complete, 100)}%` }}
                />
              </div>
              <p className="mt-1 text-lg font-semibold text-[var(--accent)]">
                {goal.pct_complete.toFixed(0)}%
              </p>
            </div>

            {/* Sub-goals */}
            {goal.sub_goals && goal.sub_goals.length > 0 && (
              <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
                <h2 className="mb-3 text-sm font-semibold text-[var(--text)]">Pod-cele</h2>
                <div className="space-y-3">
                  {goal.sub_goals.map((sg) => (
                    <div
                      key={sg.id}
                      className="rounded-lg border border-[var(--border)] bg-[var(--bg)] p-3"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium text-[var(--text)]">{sg.title}</span>
                        <span
                          className={cn(
                            'rounded-full px-2 py-0.5 text-xs font-medium',
                            STATUS_BADGE[sg.status].className,
                          )}
                        >
                          {STATUS_BADGE[sg.status].label}
                        </span>
                      </div>
                      <div className="mt-2 flex items-center gap-2">
                        <div className="h-2 flex-1 rounded-full bg-[var(--surface)]">
                          <div
                            className="h-full rounded-full bg-[var(--accent)] transition-all"
                            style={{ width: `${Math.min(sg.pct_complete, 100)}%` }}
                          />
                        </div>
                        <span className="text-xs text-[var(--text-secondary)]">
                          {sg.pct_complete.toFixed(0)}%
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-[var(--text-secondary)]">
                        {sg.current_value} / {sg.target_value} {sg.unit}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Dependencies */}
            {goal.dependencies && goal.dependencies.length > 0 && (
              <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
                <h2 className="mb-3 text-sm font-semibold text-[var(--text)]">Zależności</h2>
                <div className="flex flex-wrap gap-2">
                  {goal.dependencies.map((depId) => (
                    <Link
                      key={depId}
                      href={`/finance/goals/${depId}`}
                      className="rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-1.5 text-sm text-[var(--accent)] hover:bg-[var(--surface-hover)] transition-colors"
                    >
                      Cel #{depId}
                    </Link>
                  ))}
                </div>
              </div>
            )}

            {/* Update progress form */}
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
              <h2 className="mb-3 text-sm font-semibold text-[var(--text)]">Aktualizuj postęp</h2>
              <div className="space-y-3">
                <div>
                  <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
                    Wartość
                  </label>
                  <input
                    type="number"
                    value={updateValue}
                    onChange={(e) => setUpdateValue(e.target.value)}
                    placeholder={`Obecna: ${goal.current_value}`}
                    className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)]"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
                    Notatka (opcjonalnie)
                  </label>
                  <textarea
                    value={updateNote}
                    onChange={(e) => setUpdateNote(e.target.value)}
                    rows={2}
                    className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] resize-none"
                    placeholder="Opis zmian..."
                  />
                </div>
                <button
                  type="button"
                  onClick={handleUpdate}
                  disabled={!updateValue || updateMutation.isPending}
                  className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 transition-opacity disabled:opacity-50"
                >
                  {updateMutation.isPending ? 'Zapisywanie...' : 'Zapisz postęp'}
                </button>
                {updateMutation.isError && (
                  <p className="text-xs text-red-400">
                    Błąd: {(updateMutation.error as Error).message}
                  </p>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </RbacGate>
  );
}

export default PageClient;
