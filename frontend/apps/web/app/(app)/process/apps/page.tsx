'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { RbacGate, AppTable, AppRankingTable } from '@gilbertus/ui';
import {
  useApps,
  useAppRanking,
  useAppCosts,
  useScanApps,
  useScanAppsDeep,
} from '@/lib/hooks/use-process-intel';
import { useProcessStore } from '@/lib/stores/process-store';
import { cn } from '@gilbertus/ui';
import {
  Package,
  Trophy,
  Banknote,
  RefreshCw,
  Search,
} from 'lucide-react';
import type { AppCostSummary } from '@gilbertus/api-client';

type TabId = 'inventory' | 'ranking' | 'costs';

const TABS: { id: TabId; label: string; icon: typeof Package }[] = [
  { id: 'inventory', label: 'Inwentarz', icon: Package },
  { id: 'ranking', label: 'Ranking', icon: Trophy },
  { id: 'costs', label: 'Koszty', icon: Banknote },
];

function formatPLN(amount: number): string {
  return new Intl.NumberFormat('pl-PL', {
    style: 'currency',
    currency: 'PLN',
    maximumFractionDigits: 0,
  }).format(amount);
}

export default function AppsPage() {
  const router = useRouter();
  const store = useProcessStore();
  const { data: apps, isLoading: appsLoading, error: appsError } = useApps();
  const { data: ranking } = useAppRanking();
  const costsMut = useAppCosts();
  const scanMut = useScanApps();
  const deepScanMut = useScanAppsDeep();

  // Load costs when switching to costs tab
  useEffect(() => {
    if (store.appViewMode === 'costs' && !costsMut.data && !costsMut.isPending) {
      costsMut.mutate();
    }
  }, [store.appViewMode]); // eslint-disable-line react-hooks/exhaustive-deps

  const costs: AppCostSummary | undefined = costsMut.data as AppCostSummary | undefined;

  return (
    <RbacGate
      roles={['director', 'board', 'ceo']}
      permission="data:read:department"
      fallback={
        <div className="flex items-center justify-center h-64 text-[var(--text-secondary)]">
          Brak dostępu do modułu Aplikacje
        </div>
      }
    >
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-[var(--text)]">Aplikacje</h1>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => { if (!scanMut.isPending) scanMut.mutate(); }}
              disabled={scanMut.isPending}
              className="flex items-center gap-2 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              <RefreshCw size={14} className={scanMut.isPending ? 'animate-spin' : ''} />
              {scanMut.isPending ? 'Skanowanie...' : 'Skanuj'}
            </button>
            <button
              type="button"
              onClick={() => { if (!deepScanMut.isPending) deepScanMut.mutate(); }}
              disabled={deepScanMut.isPending}
              className="flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm font-medium text-[var(--text)] hover:bg-[var(--bg-hover)] transition-colors disabled:opacity-50"
            >
              <Search size={14} className={deepScanMut.isPending ? 'animate-spin' : ''} />
              {deepScanMut.isPending ? 'Głębokie skanowanie...' : 'Głębokie skanowanie'}
            </button>
          </div>
        </div>

        {/* Scan success messages */}
        {scanMut.isSuccess && scanMut.data && (
          <div className="rounded-lg border border-green-500/30 bg-green-500/10 px-4 py-2.5 text-sm text-green-400">
            Skan zakończony: {(scanMut.data as { apps_found?: number }).apps_found ?? 0} aplikacji znalezionych
          </div>
        )}
        {deepScanMut.isSuccess && (
          <div className="rounded-lg border border-green-500/30 bg-green-500/10 px-4 py-2.5 text-sm text-green-400">
            Głębokie skanowanie zakończone
          </div>
        )}

        {/* Tab bar */}
        <div className="flex items-center border-b border-[var(--border)]">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => store.setAppViewMode(tab.id)}
              className={cn(
                'flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors',
                store.appViewMode === tab.id
                  ? 'border-[var(--accent)] text-[var(--accent)]'
                  : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text)]',
              )}
            >
              <tab.icon size={14} />
              {tab.label}
            </button>
          ))}
        </div>

        {/* Loading skeleton */}
        {appsLoading && (
          <div className="space-y-3">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-12 animate-pulse rounded-lg bg-[var(--bg-hover)]" />
            ))}
          </div>
        )}

        {/* Error state */}
        {appsError && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
            Błąd ładowania aplikacji: {(appsError as Error).message}
          </div>
        )}

        {/* Inventory tab */}
        {store.appViewMode === 'inventory' && apps && (
          <AppTable
            apps={apps}
            onRowClick={(name) => {
              const app = apps.find((a) => a.name === name);
              if (app && 'id' in app) {
                router.push(`/process/apps/${(app as { id: number }).id}`);
              }
            }}
          />
        )}

        {/* Ranking tab */}
        {store.appViewMode === 'ranking' && (
          <>
            {ranking ? (
              <AppRankingTable ranking={ranking} />
            ) : (
              <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 text-center text-sm text-[var(--text-secondary)]">
                Ładowanie rankingu...
              </div>
            )}
          </>
        )}

        {/* Costs tab */}
        {store.appViewMode === 'costs' && (
          <>
            {costsMut.isPending && (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-12 animate-pulse rounded-lg bg-[var(--bg-hover)]" />
                ))}
              </div>
            )}
            {costs && (
              <div className="space-y-4">
                {/* Cost KPIs */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
                    <div className="flex items-center gap-2 text-[var(--text-secondary)]">
                      <Banknote size={14} />
                      <span className="text-xs font-medium uppercase">Miesięcznie</span>
                    </div>
                    <p className="mt-1.5 text-2xl font-bold text-[var(--text)]">
                      {formatPLN(costs.total_monthly_pln)}
                    </p>
                  </div>
                  <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
                    <div className="flex items-center gap-2 text-[var(--text-secondary)]">
                      <Banknote size={14} />
                      <span className="text-xs font-medium uppercase">Rocznie</span>
                    </div>
                    <p className="mt-1.5 text-2xl font-bold text-[var(--text)]">
                      {formatPLN(costs.total_yearly_pln)}
                    </p>
                  </div>
                </div>

                {/* Cost breakdown table */}
                {Array.isArray(costs.cost_breakdown) && costs.cost_breakdown.length > 0 && (
                  <div className="overflow-x-auto rounded-lg border border-[var(--border)] bg-[var(--surface)]">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-[var(--border)] text-left text-xs uppercase text-[var(--text-secondary)]">
                          <th className="px-4 py-3 font-medium">Aplikacja</th>
                          <th className="px-4 py-3 font-medium">Miesięcznie</th>
                          <th className="px-4 py-3 font-medium">Rocznie</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(costs.cost_breakdown as Record<string, unknown>[]).map((item, idx) => (
                          <tr key={idx} className="border-b border-[var(--border)] last:border-0">
                            <td className="px-4 py-2.5 text-[var(--text)]">
                              {String(item.name ?? item.app ?? `App ${idx + 1}`)}
                            </td>
                            <td className="px-4 py-2.5 text-[var(--text-secondary)]">
                              {formatPLN(Number(item.monthly_pln ?? item.monthly ?? 0))}
                            </td>
                            <td className="px-4 py-2.5 text-[var(--text-secondary)]">
                              {formatPLN(Number(item.yearly_pln ?? item.yearly ?? 0))}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
            {costsMut.error && (
              <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
                Błąd ładowania kosztów: {(costsMut.error as Error).message}
              </div>
            )}
          </>
        )}
      </div>
    </RbacGate>
  );
}
