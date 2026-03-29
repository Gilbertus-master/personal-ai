'use client';

import { useMemo } from 'react';
import { FileSearch } from 'lucide-react';
import type { AuditLogEntry } from '@gilbertus/api-client';
import type { OmniusTenant } from '@gilbertus/api-client';

interface CrossTenantAuditProps {
  activeTenant: OmniusTenant;
  onTenantChange: (t: OmniusTenant) => void;
  entries: AuditLogEntry[];
  isLoading: boolean;
}

const resultConfig: Record<string, { label: string; className: string }> = {
  ok: { label: 'OK', className: 'bg-green-600/20 text-green-400' },
  denied: { label: 'Denied', className: 'bg-yellow-600/20 text-yellow-400' },
  error: { label: 'Error', className: 'bg-red-600/20 text-red-400' },
  governance_violation: { label: 'Governance', className: 'bg-purple-600/20 text-purple-400' },
};

function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString('pl-PL', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function TenantTabs({
  active,
  onChange,
}: {
  active: OmniusTenant;
  onChange: (t: OmniusTenant) => void;
}) {
  const tenants: { id: OmniusTenant; label: string }[] = [
    { id: 'reh', label: 'REH' },
    { id: 'ref', label: 'REF' },
  ];
  return (
    <div className="flex gap-1 rounded-lg bg-[var(--bg)] p-1">
      {tenants.map((t) => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
            active === t.id
              ? 'bg-[var(--accent)] text-white'
              : 'text-[var(--text-secondary)] hover:text-[var(--text)]'
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function CrossTenantAudit({
  activeTenant,
  onTenantChange,
  entries,
  isLoading,
}: CrossTenantAuditProps) {
  const sorted = useMemo(
    () => [...entries].sort((a, b) => new Date(b.at).getTime() - new Date(a.at).getTime()),
    [entries],
  );

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-10 w-32 animate-pulse rounded bg-[var(--surface)]" />
        <div className="h-64 animate-pulse rounded bg-[var(--surface)]" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <TenantTabs active={activeTenant} onChange={onTenantChange} />

      {sorted.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-[var(--border)] py-16 text-[var(--text-secondary)]">
          <FileSearch className="h-8 w-8" />
          <p className="text-sm">Brak wpisów w logu</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] bg-[var(--surface)]">
                {['Czas', 'Użytkownik', 'Akcja', 'Zasób', 'Wynik', 'IP'].map((h) => (
                  <th
                    key={h}
                    className="px-4 py-2.5 text-left text-xs font-semibold uppercase text-[var(--text-secondary)]"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.map((e) => {
                const cfg = resultConfig[e.result] ?? resultConfig.error;
                return (
                  <tr
                    key={e.id}
                    className="border-b border-[var(--border)] hover:bg-[var(--bg-hover)]"
                  >
                    <td className="whitespace-nowrap px-4 py-2.5 text-[var(--text-secondary)]">
                      {formatTimestamp(e.at)}
                    </td>
                    <td className="px-4 py-2.5 text-[var(--text)]">{e.user ?? 'system'}</td>
                    <td className="px-4 py-2.5 text-[var(--text)]">{e.action}</td>
                    <td className="max-w-[200px] truncate px-4 py-2.5 text-[var(--text-secondary)]">
                      {e.resource}
                    </td>
                    <td className="px-4 py-2.5">
                      <span
                        className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${cfg.className}`}
                      >
                        {cfg.label}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 font-mono text-xs text-[var(--text-secondary)]">
                      {e.ip}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
