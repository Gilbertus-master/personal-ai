'use client';

import { useParams, useRouter } from 'next/navigation';
import { RbacGate } from '@gilbertus/ui';
import { useAppDetail } from '@/lib/hooks/use-process-intel';
import {
  ArrowLeft,
  Building2,
  Tag,
  Banknote,
  Users,
  GitBranch,
  Replace,
  Database,
} from 'lucide-react';

function formatPLN(amount: number): string {
  return new Intl.NumberFormat('pl-PL', {
    style: 'currency',
    currency: 'PLN',
    maximumFractionDigits: 0,
  }).format(amount);
}

function FeasibilityBar({ value }: { value: number }) {
  const color =
    value >= 70 ? 'bg-green-500' : value >= 40 ? 'bg-amber-500' : 'bg-red-500';
  return (
    <div className="flex items-center gap-3">
      <div className="h-2.5 flex-1 rounded-full bg-[var(--border)]">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${value}%` }} />
      </div>
      <span className="text-sm font-medium text-[var(--text)]">{value}%</span>
    </div>
  );
}

export function PageClient() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const appId = Number(id);
  const { data: app, isLoading, error } = useAppDetail(appId);

  return (
    <RbacGate
      roles={['director', 'board', 'ceo']}
      permission="data:read:department"
      fallback={
        <div className="flex items-center justify-center h-64 text-[var(--text-secondary)]">
          Brak dostępu
        </div>
      }
    >
      <div className="space-y-6">
        {/* Back button */}
        <button
          type="button"
          onClick={() => router.push('/process/apps')}
          className="flex items-center gap-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text)] transition-colors"
        >
          <ArrowLeft size={14} />
          Powrót do aplikacji
        </button>

        {/* Loading skeleton */}
        {isLoading && (
          <div className="space-y-4">
            <div className="h-10 w-64 animate-pulse rounded-lg bg-[var(--bg-hover)]" />
            <div className="h-32 animate-pulse rounded-lg bg-[var(--bg-hover)]" />
            <div className="h-48 animate-pulse rounded-lg bg-[var(--bg-hover)]" />
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
            Błąd ładowania szczegółów: {(error as Error).message}
          </div>
        )}

        {app && (
          <>
            {/* Header */}
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold text-[var(--text)]">{app.name}</h1>
                <span className="rounded-full bg-[var(--accent)]/20 px-2.5 py-0.5 text-xs font-medium text-[var(--accent)]">
                  {app.category}
                </span>
              </div>
              {app.vendor && (
                <div className="mt-1 flex items-center gap-2 text-sm text-[var(--text-secondary)]">
                  <Building2 size={14} />
                  {app.vendor}
                </div>
              )}
            </div>

            {/* Cost section */}
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
              <div className="flex items-center gap-2 mb-3">
                <Banknote size={14} className="text-[var(--text-secondary)]" />
                <h2 className="text-sm font-semibold text-[var(--text)]">Koszty</h2>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="text-xs text-[var(--text-secondary)]">Miesięcznie</span>
                  <p className="text-lg font-bold text-[var(--text)]">{formatPLN(app.cost_monthly_pln)}</p>
                </div>
                <div>
                  <span className="text-xs text-[var(--text-secondary)]">Rocznie</span>
                  <p className="text-lg font-bold text-[var(--text)]">{formatPLN(app.cost_yearly_pln)}</p>
                </div>
              </div>
              {app.tco_analysis && (
                <div className="mt-3 rounded-md bg-[var(--bg)] p-3">
                  <span className="text-xs font-medium text-[var(--text-secondary)]">Analiza TCO</span>
                  <p className="mt-1 text-sm text-[var(--text)]">{app.tco_analysis}</p>
                </div>
              )}
            </div>

            {/* Users section */}
            {app.user_details && app.user_details.length > 0 && (
              <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
                <div className="flex items-center gap-2 mb-3">
                  <Users size={14} className="text-[var(--text-secondary)]" />
                  <h2 className="text-sm font-semibold text-[var(--text)]">
                    Użytkownicy ({app.user_details.length})
                  </h2>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-[var(--border)] text-left text-xs uppercase text-[var(--text-secondary)]">
                        <th className="px-3 py-2 font-medium">Użytkownik</th>
                        <th className="px-3 py-2 font-medium">Rola</th>
                        <th className="px-3 py-2 font-medium">Częstotliwość</th>
                      </tr>
                    </thead>
                    <tbody>
                      {app.user_details.map((u, idx) => (
                        <tr key={idx} className="border-b border-[var(--border)] last:border-0">
                          <td className="px-3 py-2 text-[var(--text)]">{u.user}</td>
                          <td className="px-3 py-2 text-[var(--text-secondary)]">{u.role}</td>
                          <td className="px-3 py-2 text-[var(--text-secondary)]">{u.usage_frequency}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Supported processes */}
            {app.supported_processes && app.supported_processes.length > 0 && (
              <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
                <div className="flex items-center gap-2 mb-3">
                  <GitBranch size={14} className="text-[var(--text-secondary)]" />
                  <h2 className="text-sm font-semibold text-[var(--text)]">Wspierane procesy</h2>
                </div>
                <div className="flex flex-wrap gap-2">
                  {app.supported_processes.map((proc, idx) => (
                    <span
                      key={idx}
                      className="rounded-full bg-[var(--bg)] px-2.5 py-1 text-xs text-[var(--text-secondary)]"
                    >
                      {proc}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Replacement section */}
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
              <div className="flex items-center gap-2 mb-3">
                <Replace size={14} className="text-[var(--text-secondary)]" />
                <h2 className="text-sm font-semibold text-[var(--text)]">Zastępowalność</h2>
              </div>
              <div className="space-y-3">
                <div>
                  <span className="text-xs text-[var(--text-secondary)]">Wykonalność zastąpienia</span>
                  <FeasibilityBar value={app.replacement_feasibility} />
                </div>
                {app.replacement_plan && (
                  <div className="rounded-md bg-[var(--bg)] p-3">
                    <span className="text-xs font-medium text-[var(--text-secondary)]">Plan zastąpienia</span>
                    <p className="mt-1 text-sm text-[var(--text)]">{app.replacement_plan}</p>
                  </div>
                )}
              </div>
            </div>

            {/* Data flow types */}
            {app.data_flow_types && app.data_flow_types.length > 0 && (
              <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
                <div className="flex items-center gap-2 mb-3">
                  <Database size={14} className="text-[var(--text-secondary)]" />
                  <h2 className="text-sm font-semibold text-[var(--text)]">Typy przepływów danych</h2>
                </div>
                <div className="flex flex-wrap gap-2">
                  {app.data_flow_types.map((flow, idx) => (
                    <span
                      key={idx}
                      className="rounded-full bg-blue-500/20 px-2.5 py-1 text-xs text-blue-400"
                    >
                      {flow}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </RbacGate>
  );
}

export default PageClient;
