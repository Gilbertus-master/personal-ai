'use client';

import type { OmniusTenantStatus } from '@gilbertus/api-client';
import { Users, FileText, Database, ListTodo } from 'lucide-react';

interface TenantQueryState {
  data: OmniusTenantStatus | undefined;
  isLoading: boolean;
  error: Error | null;
}

interface TenantOverviewProps {
  reh: TenantQueryState;
  refTenant: TenantQueryState;
}

const tenantMeta: Record<string, { name: string; company: string }> = {
  reh: { name: 'REH', company: 'Respect Energy Holding' },
  ref: { name: 'REF', company: 'Respect Energy Fuels' },
};

function pendingBadge(count: number) {
  if (count > 50) return 'bg-red-600/20 text-red-400';
  if (count > 10) return 'bg-yellow-600/20 text-yellow-400';
  return 'bg-green-600/20 text-green-400';
}

function TenantCard({ state, tenantKey }: { state: TenantQueryState; tenantKey: string }) {
  const meta = tenantMeta[tenantKey];

  if (state.isLoading) {
    return (
      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6">
        <div className="mb-4 h-6 w-40 animate-pulse rounded bg-[var(--bg)]" />
        <div className="grid grid-cols-2 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-16 animate-pulse rounded bg-[var(--bg)]" />
          ))}
        </div>
      </div>
    );
  }

  if (state.error) {
    return (
      <div className="rounded-lg border-2 border-red-500/50 bg-[var(--surface)] p-6">
        <div className="mb-2 flex items-center gap-2">
          <span className="inline-block h-2.5 w-2.5 rounded-full bg-red-500" />
          <h3 className="text-lg font-semibold text-[var(--text)]">
            {meta.name} — {meta.company}
          </h3>
        </div>
        <p className="text-sm text-red-400">{state.error.message}</p>
      </div>
    );
  }

  const d = state.data!;
  const stats = [
    { label: 'Użytkownicy', value: d.users, icon: Users },
    { label: 'Dokumenty', value: d.documents, icon: FileText },
    { label: 'Chunki', value: d.chunks, icon: Database },
    { label: 'Oczekujące', value: d.pending_tasks, icon: ListTodo },
  ];

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6">
      <div className="mb-4 flex items-center gap-2">
        <span className="inline-block h-2.5 w-2.5 rounded-full bg-green-500" />
        <h3 className="text-lg font-semibold text-[var(--text)]">
          {meta.name} — {meta.company}
        </h3>
      </div>
      <div className="grid grid-cols-2 gap-4">
        {stats.map((s) => (
          <div key={s.label} className="rounded-md bg-[var(--bg)] p-3">
            <div className="mb-1 flex items-center gap-1.5 text-[var(--text-secondary)]">
              <s.icon className="h-3.5 w-3.5" />
              <span className="text-xs">{s.label}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xl font-bold text-[var(--text)]">
                {s.value.toLocaleString('pl-PL')}
              </span>
              {s.label === 'Oczekujące' && (
                <span
                  className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${pendingBadge(s.value)}`}
                >
                  {s.value > 50 ? 'Krytyczne' : s.value > 10 ? 'Wysoki' : 'OK'}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function TenantOverview({ reh, refTenant }: TenantOverviewProps) {
  return (
    <div className="grid gap-6 md:grid-cols-2">
      <TenantCard state={reh} tenantKey="reh" />
      <TenantCard state={refTenant} tenantKey="ref" />
    </div>
  );
}
