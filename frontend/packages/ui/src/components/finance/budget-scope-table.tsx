'use client';

import type { BudgetScope, CostAlert } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';

interface BudgetScopeTableProps {
  budgets: BudgetScope[];
  dailyTotal: number;
  alerts: CostAlert[];
}

const STATUS_BADGE: Record<BudgetScope['status'], { label: string; className: string }> = {
  ok: { label: 'OK', className: 'bg-emerald-500/20 text-emerald-400' },
  warning: { label: 'Uwaga', className: 'bg-amber-500/20 text-amber-400' },
  exceeded: { label: 'Przekroczony', className: 'bg-red-500/20 text-red-400' },
};

function formatUsd(value: number): string {
  return `$${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function BudgetScopeTable({ budgets, dailyTotal, alerts }: BudgetScopeTableProps) {
  return (
    <div className="space-y-4">
      {/* Daily total KPI */}
      <div className="rounded-lg bg-[var(--surface)] border border-[var(--border)] p-4">
        <p className="text-sm text-[var(--text-secondary)]">Dzienny koszt łączny</p>
        <p className="mt-1 text-2xl font-bold text-[var(--text)]">{formatUsd(dailyTotal)}</p>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] bg-[var(--surface)]">
              <th className="px-3 py-2 text-left font-medium text-[var(--text-secondary)]">Zakres</th>
              <th className="px-3 py-2 text-right font-medium text-[var(--text-secondary)]">Limit (USD)</th>
              <th className="px-3 py-2 text-right font-medium text-[var(--text-secondary)]">Wydano (USD)</th>
              <th className="px-3 py-2 text-right font-medium text-[var(--text-secondary)]">%</th>
              <th className="px-3 py-2 text-center font-medium text-[var(--text-secondary)]">Hard limit</th>
              <th className="px-3 py-2 text-center font-medium text-[var(--text-secondary)]">Status</th>
            </tr>
          </thead>
          <tbody>
            {budgets.map((b) => {
              const st = STATUS_BADGE[b.status];
              return (
                <tr
                  key={b.scope}
                  className="border-b border-[var(--border)] last:border-b-0 hover:bg-[var(--surface-hover)] transition-colors"
                >
                  <td className="px-3 py-2 font-medium text-[var(--text)]">{b.scope}</td>
                  <td className="px-3 py-2 text-right text-[var(--text-secondary)]">
                    {formatUsd(b.limit_usd)}
                  </td>
                  <td className="px-3 py-2 text-right text-[var(--text)]">
                    {formatUsd(b.spent_usd)}
                  </td>
                  <td className="px-3 py-2 text-right text-[var(--text-secondary)]">
                    {b.pct.toFixed(0)}%
                  </td>
                  <td className="px-3 py-2 text-center text-[var(--text-secondary)]">
                    {b.hard_limit ? 'Tak' : 'Nie'}
                  </td>
                  <td className="px-3 py-2 text-center">
                    <span className={cn('rounded-full px-2 py-0.5 text-xs font-medium', st.className)}>
                      {st.label}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Alerts */}
      {alerts.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-sm font-medium text-[var(--text-secondary)]">Alerty</h4>
          {alerts.map((a, i) => (
            <div
              key={`${a.scope}-${i}`}
              className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm"
            >
              <div className="flex items-center justify-between">
                <span className="font-medium text-red-400">{a.scope}</span>
                <span className="text-xs text-[var(--text-muted)]">{a.at}</span>
              </div>
              <p className="mt-0.5 text-[var(--text-secondary)]">{a.message}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
