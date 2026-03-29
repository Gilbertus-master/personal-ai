'use client';

import { RbacGate, MetricCard, BudgetBar, CostTrendChart } from '@gilbertus/ui';
import { useFinanceDashboard } from '@/lib/hooks/use-finance';
import { useFinanceStore } from '@/lib/stores/finance-store';
import type { CompanyFinance } from '@gilbertus/api-client';
import {
  DollarSign,
  AlertTriangle,
  TrendingUp,
  ChevronDown,
  ChevronUp,
  Building2,
} from 'lucide-react';

function KpiCard({
  label,
  value,
  icon: Icon,
  color,
}: {
  label: string;
  value: string | number;
  icon: typeof DollarSign;
  color?: string;
}) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
      <div className="flex items-center gap-2 text-[var(--text-secondary)]">
        <Icon size={14} className={color} />
        <span className="text-xs font-medium uppercase">{label}</span>
      </div>
      <p className="mt-1.5 text-2xl font-bold text-[var(--text)]">{value}</p>
    </div>
  );
}

function CompanySection({
  name,
  data,
  expanded,
  onToggle,
}: {
  name: string;
  data: CompanyFinance;
  expanded: boolean;
  onToggle: () => void;
}) {
  const metrics = Object.entries(data.latest_metrics);

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)]">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-[var(--surface-hover)] transition-colors rounded-lg"
      >
        <div className="flex items-center gap-2">
          <Building2 size={16} className="text-[var(--accent)]" />
          <span className="font-semibold text-[var(--text)]">{name}</span>
          {data.alerts.length > 0 && (
            <span className="rounded-full bg-amber-500/20 px-2 py-0.5 text-xs font-medium text-amber-400">
              {data.alerts.length} alert{data.alerts.length > 1 ? 'y' : ''}
            </span>
          )}
        </div>
        {expanded ? (
          <ChevronUp size={16} className="text-[var(--text-secondary)]" />
        ) : (
          <ChevronDown size={16} className="text-[var(--text-secondary)]" />
        )}
      </button>

      {expanded && (
        <div className="space-y-4 border-t border-[var(--border)] px-4 py-4">
          {/* Latest metrics */}
          {metrics.length > 0 && (
            <div>
              <h4 className="mb-2 text-xs font-semibold uppercase text-[var(--text-secondary)]">
                Metryki
              </h4>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {metrics.map(([key, m]) => (
                  <MetricCard
                    key={key}
                    label={key}
                    value={m.value}
                    currency={m.currency}
                    period={m.period_start}
                    source={m.source}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Budget utilization */}
          {data.budget_utilization.length > 0 && (
            <div>
              <h4 className="mb-2 text-xs font-semibold uppercase text-[var(--text-secondary)]">
                Budżety
              </h4>
              <div className="space-y-3">
                {data.budget_utilization.map((b) => (
                  <BudgetBar
                    key={b.category}
                    category={b.category}
                    planned={b.planned}
                    actual={b.actual}
                    pct={b.pct}
                    currency={b.currency}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Company alerts */}
          {data.alerts.length > 0 && (
            <div>
              <h4 className="mb-2 text-xs font-semibold uppercase text-[var(--text-secondary)]">
                Alerty
              </h4>
              <div className="space-y-2">
                {data.alerts.map((a, i) => (
                  <div
                    key={`${a.alert_type}-${i}`}
                    className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-amber-400">{a.alert_type}</span>
                      <span className="text-xs text-[var(--text-secondary)]">
                        {a.severity}
                      </span>
                    </div>
                    <p className="mt-0.5 text-[var(--text-secondary)]">{a.description}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function trendBadge(trend: string) {
  const isUp = trend === 'increasing';
  const isDown = trend === 'decreasing';
  return (
    <span
      className={
        isUp
          ? 'rounded-full bg-red-500/20 px-2 py-0.5 text-xs font-medium text-red-400'
          : isDown
            ? 'rounded-full bg-emerald-500/20 px-2 py-0.5 text-xs font-medium text-emerald-400'
            : 'rounded-full bg-zinc-500/20 px-2 py-0.5 text-xs font-medium text-zinc-400'
      }
    >
      {isUp ? 'Rosnący' : isDown ? 'Malejący' : 'Stabilny'}
    </span>
  );
}

export default function FinancePage() {
  const store = useFinanceStore();
  const { data: dashboard, isLoading, error } = useFinanceDashboard(
    store.selectedCompany ?? undefined,
  );

  const companies = dashboard ? Object.entries(dashboard.companies) : [];
  const companyNames = companies.map(([name]) => name);

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
        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-[var(--text)]">Finanse</h1>
          <select
            value={store.selectedCompany ?? ''}
            onChange={(e) => store.setSelectedCompany(e.target.value || null)}
            className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-2.5 py-1.5 text-sm text-[var(--text)]"
          >
            <option value="">Wszystkie spółki</option>
            {companyNames.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </div>

        {/* Loading */}
        {isLoading && (
          <div className="space-y-4">
            <div className="grid grid-cols-3 gap-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-20 animate-pulse rounded-lg bg-[var(--surface)]" />
              ))}
            </div>
            <div className="h-64 animate-pulse rounded-lg bg-[var(--surface)]" />
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
            Błąd ładowania danych finansowych: {(error as Error).message}
          </div>
        )}

        {dashboard && (
          <>
            {/* KPI row */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <KpiCard
                label="Aktywne alerty"
                value={dashboard.active_alerts}
                icon={AlertTriangle}
                color="text-amber-400"
              />
              <KpiCard
                label="Wykorzystanie budżetu"
                value={`${dashboard.total_budget_utilization.toFixed(0)}%`}
                icon={DollarSign}
              />
              <KpiCard
                label="Koszt API (śr. mies.)"
                value={`$${dashboard.api_costs.avg_monthly_usd.toFixed(2)}`}
                icon={TrendingUp}
              />
            </div>

            {/* Company sections */}
            <div className="space-y-3">
              <h2 className="text-sm font-semibold text-[var(--text)]">
                Spółki ({companies.length})
              </h2>
              {companies.map(([name, data]) => (
                <CompanySection
                  key={name}
                  name={name}
                  data={data}
                  expanded={store.expandedCompanies.includes(name)}
                  onToggle={() => store.toggleCompanyExpanded(name)}
                />
              ))}
            </div>

            {/* API Costs */}
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-sm font-semibold text-[var(--text)]">Koszty API</h2>
                <div className="flex items-center gap-3">
                  {trendBadge(dashboard.api_costs.trend)}
                  <span className="text-xs text-[var(--text-secondary)]">
                    Prognoza: ${dashboard.api_costs.current_month_forecast_usd.toFixed(2)}
                  </span>
                </div>
              </div>
              <CostTrendChart
                data={dashboard.api_costs.monthly}
                forecast={dashboard.api_costs.current_month_forecast_usd}
              />
              <div className="mt-3 flex items-center gap-4 text-xs text-[var(--text-secondary)]">
                <span>Średnia miesięczna: ${dashboard.api_costs.avg_monthly_usd.toFixed(2)}</span>
                <span>Trend: {dashboard.api_costs.trend}</span>
              </div>
            </div>

            {/* Finance alerts summary */}
            {dashboard.active_alerts > 0 && (
              <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-400">
                <AlertTriangle size={14} className="mr-1 inline" />
                {dashboard.active_alerts} aktywn{dashboard.active_alerts === 1 ? 'y' : 'ych'}{' '}
                alert{dashboard.active_alerts === 1 ? '' : 'ów'} finansowych
              </div>
            )}
          </>
        )}
      </div>
    </RbacGate>
  );
}
