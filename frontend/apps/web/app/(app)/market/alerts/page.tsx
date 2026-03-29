'use client';

import { RbacGate, MarketAlertItem } from '@gilbertus/ui';
import { useMarketAlerts } from '@/lib/hooks/use-market';
import { useMarketStore } from '@/lib/stores/market-store';
import { AlertTriangle, Bell } from 'lucide-react';

export default function MarketAlertsPage() {
  const store = useMarketStore();
  const { data: alerts, isLoading, error } = useMarketAlerts(
    store.alertsShowAcknowledged ? undefined : false,
  );

  return (
    <RbacGate
      roles={['director', 'board', 'ceo']}
      permission="data:read:department"
      fallback={
        <div className="flex items-center justify-center h-64 text-[var(--text-secondary)]">
          Brak dostępu do alertów rynkowych
        </div>
      }
    >
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-[var(--text)]">Alerty rynkowe</h1>
            {!isLoading && alerts && (
              <span className="rounded-full bg-[var(--surface)] px-2.5 py-0.5 text-xs font-medium text-[var(--text-secondary)]">
                {alerts.length}
              </span>
            )}
          </div>
          <label className="flex items-center gap-2 text-sm text-[var(--text-secondary)] cursor-pointer">
            <input
              type="checkbox"
              checked={store.alertsShowAcknowledged}
              onChange={(e) => store.setAlertsShowAcknowledged(e.target.checked)}
              className="rounded border-[var(--border)]"
            />
            Pokaż potwierdzone
          </label>
        </div>

        {/* Loading skeleton */}
        {isLoading && (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-20 animate-pulse rounded-lg bg-[var(--bg-hover)]" />
            ))}
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
            Błąd ładowania alertów: {(error as Error).message}
          </div>
        )}

        {/* Alert list */}
        {alerts && alerts.length > 0 && (
          <div className="space-y-3">
            {alerts.map((alert) => (
              <MarketAlertItem
                key={alert.id}
                alert={alert}
                // TODO: acknowledge button disabled — backend POST /market/alerts/{id}/acknowledge endpoint missing
              />
            ))}
          </div>
        )}

        {/* Empty state */}
        {alerts && alerts.length === 0 && (
          <div className="flex flex-col items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--surface)] py-16">
            {store.alertsShowAcknowledged ? (
              <Bell size={32} className="mb-3 text-[var(--text-secondary)]" />
            ) : (
              <AlertTriangle size={32} className="mb-3 text-[var(--text-secondary)]" />
            )}
            <p className="text-sm text-[var(--text-secondary)]">
              {store.alertsShowAcknowledged
                ? 'Brak alertów'
                : 'Brak aktywnych alertów'}
            </p>
          </div>
        )}
      </div>
    </RbacGate>
  );
}
