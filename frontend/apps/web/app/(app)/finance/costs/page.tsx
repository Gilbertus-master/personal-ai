'use client';

import { RbacGate, BudgetScopeTable } from '@gilbertus/ui';
import { useCostBudget } from '@/lib/hooks/use-finance';
import { DollarSign } from 'lucide-react';

export default function CostBudgetPage() {
  const { data, isLoading, error } = useCostBudget();

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
        <div className="flex items-center gap-2">
          <DollarSign size={20} className="text-[var(--accent)]" />
          <h1 className="text-2xl font-bold text-[var(--text)]">Budżety kosztów</h1>
        </div>

        {/* Loading */}
        {isLoading && (
          <div className="space-y-4">
            <div className="h-20 animate-pulse rounded-lg bg-[var(--surface)]" />
            <div className="h-64 animate-pulse rounded-lg bg-[var(--surface)]" />
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
            Błąd ładowania budżetów: {(error as Error).message}
          </div>
        )}

        {/* Content */}
        {data && (
          <BudgetScopeTable
            budgets={data.budgets}
            dailyTotal={data.daily_total_usd}
            alerts={data.alerts_today}
          />
        )}
      </div>
    </RbacGate>
  );
}
