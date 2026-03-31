'use client';

import { useState } from 'react';
import { useRole } from '@gilbertus/rbac';
import { RbacGate, InsightCard, SourceTable } from '@gilbertus/ui';
import { useMarketDashboard, useScanMarket } from '@/lib/hooks/use-market';
import { useMarketStore } from '@/lib/stores/market-store';
import {
  TrendingUp,
  AlertTriangle,
  Rss,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  Search,
} from 'lucide-react';
import Link from 'next/link';
import type { MarketInsight } from '@gilbertus/api-client';

const INSIGHT_TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: 'price_change', label: 'Zmiana ceny' },
  { value: 'regulation', label: 'Regulacja' },
  { value: 'tender', label: 'Przetarg' },
  { value: 'trend', label: 'Trend' },
  { value: 'risk', label: 'Ryzyko' },
];

function KpiCard({ label, value, icon: Icon }: { label: string; value: number; icon: typeof TrendingUp }) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
      <div className="flex items-center gap-2 text-[var(--text-secondary)]">
        <Icon size={14} />
        <span className="text-xs font-medium uppercase">{label}</span>
      </div>
      <p className="mt-1.5 text-2xl font-bold text-[var(--text)]">{value}</p>
    </div>
  );
}

function StatsByType({ byType }: { byType: Record<string, number> }) {
  const entries = Object.entries(byType);
  if (entries.length === 0) return null;
  const max = Math.max(...entries.map(([, v]) => v), 1);

  const TYPE_COLORS: Record<string, string> = {
    price_change: 'bg-blue-500',
    regulation: 'bg-orange-500',
    tender: 'bg-green-500',
    trend: 'bg-purple-500',
    risk: 'bg-red-500',
  };

  const TYPE_LABELS: Record<string, string> = {
    price_change: 'Zmiana ceny',
    regulation: 'Regulacja',
    tender: 'Przetarg',
    trend: 'Trend',
    risk: 'Ryzyko',
  };

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
      <h2 className="mb-3 text-xs font-semibold uppercase text-[var(--text-secondary)]">Insighty wg typu</h2>
      <div className="space-y-2">
        {entries.map(([type, count]) => (
          <div key={type} className="flex items-center gap-3">
            <span className="w-24 truncate text-xs text-[var(--text-secondary)]">
              {TYPE_LABELS[type] ?? type}
            </span>
            <div className="h-2 flex-1 rounded-full bg-[var(--border)]">
              <div
                className={`h-full rounded-full ${TYPE_COLORS[type] ?? 'bg-[var(--accent)]'}`}
                style={{ width: `${(count / max) * 100}%` }}
              />
            </div>
            <span className="w-6 text-right text-xs font-medium text-[var(--text)]">{count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function MarketPage() {
  const { role } = useRole();
  const store = useMarketStore();
  const { data: dashboard, isLoading, error } = useMarketDashboard();
  const scanMutation = useScanMarket();
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const handleScan = () => {
    if (!scanMutation.isPending) {
      scanMutation.mutate();
    }
  };

  // Filter insights
  const insights: MarketInsight[] = (dashboard?.insights ?? []).filter((i) => {
    if (store.insightTypeFilter && i.type !== store.insightTypeFilter) return false;
    if (i.relevance < store.minRelevance) return false;
    return true;
  });

  return (
    <RbacGate
      roles={['owner', 'director', 'board', 'ceo']}
      permission="data:read:department"
      fallback={
        <div className="flex items-center justify-center h-64 text-[var(--text-secondary)]">
          Brak dostępu do modułu Rynek
        </div>
      }
    >
      <div className="space-y-6">
        {/* Active alerts banner */}
        {dashboard && dashboard.stats.active_alerts > 0 && (
          <Link
            href="/market/alerts"
            className="flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-2.5 text-sm text-amber-400 transition-colors hover:bg-amber-500/20"
          >
            <AlertTriangle size={16} />
            <span className="font-medium">
              {dashboard.stats.active_alerts} aktywn{dashboard.stats.active_alerts === 1 ? 'y' : 'ych'} alert{dashboard.stats.active_alerts === 1 ? '' : 'ów'}
            </span>
            <span className="ml-auto text-xs">Zobacz alerty &rarr;</span>
          </Link>
        )}

        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-[var(--text)]">Rynek Energii</h1>
          <button
            type="button"
            onClick={handleScan}
            disabled={scanMutation.isPending}
            className="flex items-center gap-2 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            <RefreshCw size={14} className={scanMutation.isPending ? 'animate-spin' : ''} />
            {scanMutation.isPending ? 'Skanowanie...' : 'Skanuj rynek'}
          </button>
        </div>

        {/* Scan result toast */}
        {scanMutation.isSuccess && scanMutation.data && (
          <div className="rounded-lg border border-green-500/30 bg-green-500/10 px-4 py-2.5 text-sm text-green-400">
            Skan zakończony: {scanMutation.data.analysis?.insights_created ?? 0} nowych insightów, {scanMutation.data.analysis?.alerts_created ?? 0} alertów
          </div>
        )}

        {/* Loading skeleton */}
        {isLoading && (
          <div className="space-y-4">
            <div className="grid grid-cols-3 gap-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-20 animate-pulse rounded-lg bg-[var(--bg-hover)]" />
              ))}
            </div>
            <div className="h-32 animate-pulse rounded-lg bg-[var(--bg-hover)]" />
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
            Błąd ładowania danych rynkowych: {(error as Error).message}
          </div>
        )}

        {/* Dashboard content */}
        {dashboard && (
          <>
            {/* KPI row */}
            <div className="grid grid-cols-3 gap-4">
              <KpiCard label="Insighty" value={dashboard.stats.total_insights} icon={TrendingUp} />
              <KpiCard label="Aktywne alerty" value={dashboard.stats.active_alerts} icon={AlertTriangle} />
              <KpiCard label="Źródła" value={dashboard.sources.length} icon={Rss} />
            </div>

            {/* Stats by type */}
            <StatsByType byType={dashboard.stats.by_type} />

            {/* Filter bar */}
            <div className="flex flex-wrap items-center gap-3 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-3">
              <Search size={14} className="text-[var(--text-secondary)]" />
              <select
                value={store.insightTypeFilter ?? ''}
                onChange={(e) => store.setInsightTypeFilter(e.target.value || null)}
                className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-2.5 py-1.5 text-xs text-[var(--text)]"
              >
                <option value="">Wszystkie typy</option>
                {INSIGHT_TYPE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
              <div className="flex items-center gap-2">
                <span className="text-xs text-[var(--text-secondary)]">Min. trafność:</span>
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.1}
                  value={store.minRelevance}
                  onChange={(e) => store.setMinRelevance(Number(e.target.value))}
                  className="w-24"
                />
                <span className="text-xs font-medium text-[var(--text)]">{Math.round(store.minRelevance * 100)}%</span>
              </div>
            </div>

            {/* Insights feed */}
            <div>
              <h2 className="mb-3 text-sm font-semibold text-[var(--text)]">
                Insighty ({insights.length})
              </h2>
              {insights.length === 0 ? (
                <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 text-center text-sm text-[var(--text-secondary)]">
                  Brak insightów spełniających filtry
                </div>
              ) : (
                <div className="space-y-3">
                  {insights.map((insight) => (
                    <InsightCard
                      key={insight.id}
                      insight={insight}
                      expanded={expandedId === insight.id}
                      onToggle={() => setExpandedId(expandedId === insight.id ? null : insight.id)}
                    />
                  ))}
                </div>
              )}
            </div>

            {/* Collapsible sources panel */}
            <div>
              <button
                type="button"
                onClick={store.toggleSourcesExpanded}
                className="mb-3 flex items-center gap-2 text-sm font-semibold text-[var(--text)] hover:text-[var(--accent)] transition-colors"
              >
                {store.sourcesExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                Źródła danych ({dashboard.sources.length})
              </button>
              {store.sourcesExpanded && <SourceTable sources={dashboard.sources} />}
            </div>
          </>
        )}
      </div>
    </RbacGate>
  );
}
