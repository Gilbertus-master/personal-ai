'use client';

import { useState } from 'react';
import { RefreshCw, CheckCircle } from 'lucide-react';
import type { OmniusTenant } from '@gilbertus/api-client';

interface SyncTriggerProps {
  onSync: (tenant: OmniusTenant, source: string) => void;
  isSyncing: boolean;
}

const tenants: { id: OmniusTenant; name: string; company: string }[] = [
  { id: 'reh', name: 'REH', company: 'Respect Energy Holding' },
  { id: 'ref', name: 'REF', company: 'Respect Energy Fuels' },
];

export function SyncTrigger({ onSync, isSyncing }: SyncTriggerProps) {
  const [confirmTenant, setConfirmTenant] = useState<OmniusTenant | null>(null);
  const [recentlyTriggered, setRecentlyTriggered] = useState<OmniusTenant | null>(null);

  function handleConfirm() {
    if (!confirmTenant) return;
    onSync(confirmTenant, 'all');
    setRecentlyTriggered(confirmTenant);
    setConfirmTenant(null);
    setTimeout(() => setRecentlyTriggered(null), 3000);
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-6 md:grid-cols-2">
        {tenants.map((t) => (
          <div
            key={t.id}
            className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6"
          >
            <h3 className="mb-1 text-lg font-semibold text-[var(--text)]">{t.name}</h3>
            <p className="mb-4 text-sm text-[var(--text-secondary)]">{t.company}</p>

            {recentlyTriggered === t.id ? (
              <div className="flex items-center gap-2 text-sm text-green-400">
                <CheckCircle className="h-4 w-4" />
                Synchronizacja uruchomiona
              </div>
            ) : (
              <button
                onClick={() => setConfirmTenant(t.id)}
                disabled={isSyncing}
                className="flex items-center gap-1.5 rounded-md bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
              >
                <RefreshCw className={`h-4 w-4 ${isSyncing ? 'animate-spin' : ''}`} />
                Synchronizuj
              </button>
            )}
          </div>
        ))}
      </div>

      {/* Confirm dialog */}
      {confirmTenant && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-sm rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 shadow-xl">
            <h3 className="mb-2 text-lg font-semibold text-[var(--text)]">
              Potwierdź synchronizację
            </h3>
            <p className="mb-4 text-sm text-[var(--text-secondary)]">
              Czy chcesz uruchomić pełną synchronizację dla tenanta{' '}
              <strong>{confirmTenant.toUpperCase()}</strong>?
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setConfirmTenant(null)}
                className="rounded-md px-3 py-1.5 text-sm text-[var(--text-secondary)] hover:text-[var(--text)]"
              >
                Anuluj
              </button>
              <button
                onClick={handleConfirm}
                disabled={isSyncing}
                className="rounded-md bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
              >
                {isSyncing ? 'Synchronizacja...' : 'Potwierdź'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
