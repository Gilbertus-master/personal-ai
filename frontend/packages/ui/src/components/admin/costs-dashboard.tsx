'use client';

import { useMemo } from 'react';
import { DollarSign, AlertTriangle } from 'lucide-react';
import type { CostBudget } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';

// ── Props ──────────────────────────────────────────────────────────────────

interface CostsDashboardProps {
  budget: CostBudget | undefined;
  isLoading: boolean;
}

// ── Helpers ────────────────────────────────────────────────────────────────

function statusColor(status: string): { bar: string; text: string } {
  switch (status) {
    case 'exceeded': return { bar: 'bg-red-500', text: 'text-red-400' };
    case 'warning': return { bar: 'bg-yellow-500', text: 'text-yellow-400' };
    default: return { bar: 'bg-green-500', text: 'text-green-400' };
  }
}

function SkeletonCard({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-lg bg-[var(--surface)]', className)} />;
}

// ── Component ──────────────────────────────────────────────────────────────

export function CostsDashboard({ budget, isLoading }: CostsDashboardProps) {
  const sortedModules = useMemo(() => {
    if (!budget?.budgets) return [];
    return Object.entries(budget.budgets as unknown as Record<string, number>);
  }, [budget]);

  const moduleCostEntries = useMemo(() => {
    if (!budget) return [];
    // module_costs may not exist on CostBudget — handle gracefully
    const costs = (budget as unknown as Record<string, unknown>)['module_costs'] as Record<string, number> | undefined;
    if (!costs) return [];
    return Object.entries(costs).sort(([, a], [, b]) => b - a);
  }, [budget]);

  if (isLoading || !budget) {
    return (
      <div className="space-y-6">
        <SkeletonCard className="h-28" />
        <div className="space-y-3">
          {[1, 2, 3].map((i) => <SkeletonCard key={i} className="h-16" />)}
        </div>
        <SkeletonCard className="h-48" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Daily Total */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6">
        <div className="flex items-center gap-2 text-[var(--text-secondary)]">
          <DollarSign className="h-4 w-4" />
          <span className="text-xs font-medium uppercase tracking-wider">Koszty dzisiaj</span>
        </div>
        <p className="mt-2 text-3xl font-semibold text-[var(--text)]">
          ${budget.daily_total_usd.toFixed(2)}
        </p>
      </div>

      {/* Budget Bars */}
      <section>
        <h3 className="mb-3 text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">
          Budżety
        </h3>
        <div className="space-y-3">
          {budget.budgets.map((b) => {
            const colors = statusColor(b.status);
            const pct = Math.min(b.pct, 100);
            return (
              <div key={b.scope} className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
                <div className="mb-2 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-[var(--text)]">{b.scope}</span>
                    {b.hard_limit && (
                      <span className="rounded bg-red-500/15 px-1.5 py-0.5 text-[10px] font-medium text-red-400">
                        HARD LIMIT
                      </span>
                    )}
                  </div>
                  <span className={cn('text-xs font-medium', colors.text)}>
                    ${b.spent_usd.toFixed(2)} / ${b.limit_usd.toFixed(2)}
                  </span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-[var(--border)]">
                  <div
                    className={cn('h-full rounded-full transition-all', colors.bar)}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <p className={cn('mt-1 text-right text-xs', colors.text)}>{b.pct.toFixed(1)}%</p>
              </div>
            );
          })}
        </div>
      </section>

      {/* Module Cost Breakdown */}
      {moduleCostEntries.length > 0 && (
        <section>
          <h3 className="mb-3 text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">
            Koszty wg modułu
          </h3>
          <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] bg-[var(--surface)]">
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">Moduł</th>
                  <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">Koszt (USD)</th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">Udział</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {moduleCostEntries.map(([module, cost]) => {
                  const totalModuleCost = moduleCostEntries.reduce((sum, [, c]) => sum + c, 0);
                  const share = totalModuleCost > 0 ? (cost / totalModuleCost) * 100 : 0;
                  return (
                    <tr key={module} className="bg-[var(--bg)]">
                      <td className="px-4 py-3 font-medium text-[var(--text)]">{module}</td>
                      <td className="px-4 py-3 text-right font-mono text-[var(--text)]">${cost.toFixed(2)}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div className="h-1.5 w-24 overflow-hidden rounded-full bg-[var(--border)]">
                            <div className="h-full rounded-full bg-[var(--accent)]" style={{ width: `${share}%` }} />
                          </div>
                          <span className="text-xs text-[var(--text-secondary)]">{share.toFixed(1)}%</span>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Cost Alerts */}
      {budget.alerts_today.length > 0 && (
        <section>
          <h3 className="mb-3 text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">
            Alerty kosztów
          </h3>
          <div className="space-y-2">
            {budget.alerts_today.map((alert, i) => (
              <div
                key={i}
                className="flex items-start gap-3 rounded-lg border border-yellow-500/30 bg-yellow-500/5 p-4"
              >
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-yellow-400" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-[var(--text)]">{alert.scope}</p>
                  <p className="text-xs text-[var(--text-secondary)]">{alert.message}</p>
                  <p className="mt-1 text-[10px] text-[var(--text-secondary)]">
                    {new Date(alert.at).toLocaleString('pl-PL')}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
