'use client';

import { useState } from 'react';
import { Lock, Settings2 } from 'lucide-react';
import type { OmniusTenant, OmniusConfigEntry } from '@gilbertus/api-client';

interface ConfigPushProps {
  activeTenant: OmniusTenant;
  onTenantChange: (t: OmniusTenant) => void;
  config: OmniusConfigEntry[];
  isLoading: boolean;
  onPush: (key: string, value: unknown) => void;
  isPushing: boolean;
}

const protectedPrefixes = ['rbac:', 'governance:', 'data_sources:', 'sync:schedule:', 'prompt:system'];

function isProtected(key: string): boolean {
  return protectedPrefixes.some((p) => key.startsWith(p));
}

function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString('pl-PL', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
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

export function ConfigPush({
  activeTenant,
  onTenantChange,
  config,
  isLoading,
  onPush,
  isPushing,
}: ConfigPushProps) {
  const [showPush, setShowPush] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [form, setForm] = useState({ key: '', value: '' });
  const [parseError, setParseError] = useState<string | null>(null);

  function handleSubmit() {
    try {
      const parsed = JSON.parse(form.value);
      setParseError(null);
      setShowConfirm(true);
    } catch {
      setParseError('Nieprawidłowy JSON');
    }
  }

  function handleConfirm() {
    const parsed = JSON.parse(form.value);
    onPush(form.key, parsed);
    setForm({ key: '', value: '' });
    setShowPush(false);
    setShowConfirm(false);
  }

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
      <div className="flex items-center justify-between">
        <TenantTabs active={activeTenant} onChange={onTenantChange} />
        <button
          onClick={() => setShowPush(true)}
          className="flex items-center gap-1.5 rounded-md bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-white hover:opacity-90"
        >
          Push Config
        </button>
      </div>

      {/* Push dialog */}
      {showPush && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-md rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 shadow-xl">
            <h3 className="mb-4 text-lg font-semibold text-[var(--text)]">Push Config</h3>
            <div className="space-y-3">
              <input
                type="text"
                placeholder="Klucz konfiguracji"
                value={form.key}
                onChange={(e) => setForm((f) => ({ ...f, key: e.target.value }))}
                className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-muted)]"
              />
              <textarea
                placeholder='Wartość (JSON, np. {"key": "value"})'
                value={form.value}
                onChange={(e) => {
                  setForm((f) => ({ ...f, value: e.target.value }));
                  setParseError(null);
                }}
                rows={4}
                className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 font-mono text-sm text-[var(--text)] placeholder:text-[var(--text-muted)]"
              />
              {parseError && <p className="text-sm text-red-400">{parseError}</p>}
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={() => {
                  setShowPush(false);
                  setParseError(null);
                }}
                className="rounded-md px-3 py-1.5 text-sm text-[var(--text-secondary)] hover:text-[var(--text)]"
              >
                Anuluj
              </button>
              <button
                onClick={handleSubmit}
                disabled={!form.key.trim() || !form.value.trim()}
                className="rounded-md bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
              >
                Dalej
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Confirm dialog */}
      {showConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-sm rounded-lg border border-yellow-500/50 bg-[var(--surface)] p-6 shadow-xl">
            <h3 className="mb-2 text-lg font-semibold text-yellow-400">Potwierdzenie</h3>
            <p className="mb-4 text-sm text-[var(--text-secondary)]">
              Zmiana konfiguracji tenanta <strong>{activeTenant.toUpperCase()}</strong> jest
              operacją governance. Upewnij się, że zmiana jest autoryzowana.
            </p>
            <div className="mb-4 rounded-md bg-[var(--bg)] p-3 font-mono text-xs text-[var(--text)]">
              <div>
                <span className="text-[var(--text-secondary)]">Klucz:</span> {form.key}
              </div>
              <div>
                <span className="text-[var(--text-secondary)]">Wartość:</span> {form.value}
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowConfirm(false)}
                className="rounded-md px-3 py-1.5 text-sm text-[var(--text-secondary)] hover:text-[var(--text)]"
              >
                Anuluj
              </button>
              <button
                onClick={handleConfirm}
                disabled={isPushing}
                className="rounded-md bg-yellow-600 px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
              >
                {isPushing ? 'Zapisywanie...' : 'Potwierdź'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Config table */}
      {config.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-[var(--border)] py-16 text-[var(--text-secondary)]">
          <Settings2 className="h-8 w-8" />
          <p className="text-sm">Brak konfiguracji</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] bg-[var(--surface)]">
                {['Klucz', 'Wartość', 'Zmieniony przez', 'Zaktualizowany'].map((h) => (
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
              {config.map((entry) => (
                <tr
                  key={entry.key}
                  className="border-b border-[var(--border)] hover:bg-[var(--bg-hover)]"
                >
                  <td className="px-4 py-2.5">
                    <span className="flex items-center gap-1.5 font-mono text-[var(--text)]">
                      {isProtected(entry.key) && (
                        <Lock className="h-3.5 w-3.5 text-yellow-400" />
                      )}
                      {entry.key}
                    </span>
                  </td>
                  <td className="max-w-[300px] truncate px-4 py-2.5 font-mono text-xs text-[var(--text-secondary)]">
                    {JSON.stringify(entry.value)}
                  </td>
                  <td className="px-4 py-2.5 text-[var(--text)]">{entry.pushed_by}</td>
                  <td className="whitespace-nowrap px-4 py-2.5 text-[var(--text-secondary)]">
                    {formatTimestamp(entry.updated_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
