'use client';

import { Fragment, useState } from 'react';
import { ChevronDown, ChevronRight, CheckCircle, AlertTriangle, Wrench, Globe } from 'lucide-react';
import type { AutofixerDashboard as AutofixerDashboardData } from '@gilbertus/api-client';

interface AutofixerDashboardProps {
  data: AutofixerDashboardData | undefined;
  isLoading: boolean;
  error: Error | null;
}

const severityConfig: Record<string, { label: string; className: string }> = {
  critical: { label: 'Critical', className: 'bg-red-600/20 text-red-400' },
  high: { label: 'High', className: 'bg-orange-600/20 text-orange-400' },
  medium: { label: 'Medium', className: 'bg-yellow-600/20 text-yellow-400' },
  low: { label: 'Low', className: 'bg-blue-600/20 text-blue-400' },
};

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-3">
      <p className="text-xs text-[var(--text-secondary)]">{label}</p>
      <p className="mt-1 text-2xl font-bold text-[var(--text)]">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-[var(--text-secondary)]">{sub}</p>}
    </div>
  );
}

function ProgressRing({ pct }: { pct: number }) {
  const r = 28;
  const circ = 2 * Math.PI * r;
  const offset = circ - (pct / 100) * circ;
  return (
    <svg width={72} height={72} className="shrink-0">
      <circle cx={36} cy={36} r={r} fill="none" stroke="var(--border)" strokeWidth={6} />
      <circle
        cx={36} cy={36} r={r} fill="none"
        stroke="var(--success)" strokeWidth={6}
        strokeDasharray={circ} strokeDashoffset={offset}
        strokeLinecap="round"
        transform="rotate(-90 36 36)"
      />
      <text x={36} y={36} textAnchor="middle" dominantBaseline="central"
        className="fill-[var(--text)] text-xs font-bold">
        {pct}%
      </text>
    </svg>
  );
}

function DailyChart({ history }: { history: AutofixerDashboardData['daily_history'] }) {
  if (!history.length) return null;
  const maxVal = Math.max(...history.map(d => Math.max(d.found, d.fixed, d.webapp_errors, d.webapp_fixed)), 1);

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
      <h3 className="mb-3 text-sm font-semibold text-[var(--text)]">Dzienna aktywność (14 dni)</h3>
      <div className="flex items-end gap-1" style={{ height: 120 }}>
        {history.map((d) => (
          <div key={d.date} className="group relative flex flex-1 flex-col items-center gap-0.5" style={{ height: '100%' }}>
            <div className="flex w-full flex-1 items-end justify-center gap-px">
              <div
                className="w-1/4 rounded-t bg-orange-500/70"
                style={{ height: `${(d.found / maxVal) * 100}%`, minHeight: d.found ? 2 : 0 }}
              />
              <div
                className="w-1/4 rounded-t bg-green-500/70"
                style={{ height: `${(d.fixed / maxVal) * 100}%`, minHeight: d.fixed ? 2 : 0 }}
              />
              <div
                className="w-1/4 rounded-t bg-red-500/50"
                style={{ height: `${(d.webapp_errors / maxVal) * 100}%`, minHeight: d.webapp_errors ? 2 : 0 }}
              />
            </div>
            <span className="text-[8px] text-[var(--text-secondary)]">
              {d.date.slice(5)}
            </span>
            {/* Tooltip */}
            <div className="pointer-events-none absolute -top-16 left-1/2 z-10 hidden -translate-x-1/2 rounded bg-[var(--bg)] px-2 py-1 text-[10px] text-[var(--text)] shadow-lg group-hover:block">
              <div>{d.date}</div>
              <div>Znalezione: {d.found} / Naprawione: {d.fixed}</div>
              <div>Webapp: {d.webapp_errors} / {d.webapp_fixed}</div>
            </div>
          </div>
        ))}
      </div>
      <div className="mt-2 flex gap-4 text-[10px] text-[var(--text-secondary)]">
        <span className="flex items-center gap-1"><span className="inline-block h-2 w-2 rounded bg-orange-500/70" /> Znalezione</span>
        <span className="flex items-center gap-1"><span className="inline-block h-2 w-2 rounded bg-green-500/70" /> Naprawione</span>
        <span className="flex items-center gap-1"><span className="inline-block h-2 w-2 rounded bg-red-500/50" /> Webapp błędy</span>
      </div>
    </div>
  );
}

export function AutofixerDashboard({ data, isLoading, error }: AutofixerDashboardProps) {
  const [expandedId, setExpandedId] = useState<number | null>(null);

  if (isLoading) {
    return (
      <div className="space-y-4 p-6">
        <div className="h-8 w-64 animate-pulse rounded bg-[var(--surface)]" />
        <div className="grid grid-cols-2 gap-4">
          <div className="h-40 animate-pulse rounded bg-[var(--surface)]" />
          <div className="h-40 animate-pulse rounded bg-[var(--surface)]" />
        </div>
        <div className="h-48 animate-pulse rounded bg-[var(--surface)]" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-red-400">
        <AlertTriangle className="h-5 w-5" />
        <span>Błąd ładowania: {error.message}</span>
      </div>
    );
  }

  if (!data) return null;

  const { code_fixer, webapp_fixer, daily_history, manual_queue } = data;

  return (
    <div className="space-y-6 p-6">
      <h2 className="text-xl font-bold text-[var(--text)]">Autofixer Dashboard</h2>

      {/* ── Section 1: Overview Cards ── */}
      <div className="grid gap-4 md:grid-cols-2">
        {/* Code Autofixer Card */}
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
          <div className="mb-3 flex items-center gap-2">
            <Wrench className="h-5 w-5 text-[var(--accent)]" />
            <h3 className="text-sm font-semibold text-[var(--text)]">Code Autofixer</h3>
          </div>
          <div className="flex items-center gap-4">
            <ProgressRing pct={code_fixer.success_rate} />
            <div className="grid flex-1 grid-cols-2 gap-2">
              <StatCard label="Razem" value={code_fixer.total} />
              <StatCard label="Naprawione" value={code_fixer.resolved} />
              <StatCard label="Otwarte" value={code_fixer.open} />
              <StatCard label="Zablokowane" value={code_fixer.stuck} sub={`${code_fixer.manual_review} do przeglądu`} />
            </div>
          </div>
          {/* Severity badges */}
          <div className="mt-3 flex flex-wrap gap-1.5">
            {Object.entries(code_fixer.by_severity).map(([sev, count]) => (
              <span key={sev} className={`rounded-full px-2 py-0.5 text-xs font-medium ${severityConfig[sev]?.className ?? 'bg-gray-600/20 text-gray-400'}`}>
                {severityConfig[sev]?.label ?? sev}: {count}
              </span>
            ))}
          </div>
          {/* Tier badges */}
          <div className="mt-2 flex gap-1.5">
            {Object.entries(code_fixer.by_tier).map(([tier, count]) => (
              <span key={tier} className="rounded-full bg-[var(--bg)] px-2 py-0.5 text-xs text-[var(--text-secondary)]">
                {tier}: {count}
              </span>
            ))}
          </div>
          {code_fixer.last_fix && (
            <p className="mt-2 text-xs text-[var(--text-secondary)]">
              Ostatnia naprawa: {new Date(code_fixer.last_fix).toLocaleString('pl-PL')}
            </p>
          )}
        </div>

        {/* Webapp AutoFix Card */}
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
          <div className="mb-3 flex items-center gap-2">
            <Globe className="h-5 w-5 text-[var(--accent)]" />
            <h3 className="text-sm font-semibold text-[var(--text)]">Webapp AutoFix</h3>
          </div>
          <div className="mb-3 flex items-center gap-2">
            <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${
              webapp_fixer.server_status === 'up' ? 'bg-green-600/20 text-green-400' :
              webapp_fixer.server_status === 'down' ? 'bg-red-600/20 text-red-400' :
              'bg-yellow-600/20 text-yellow-400'
            }`}>
              <span className={`h-1.5 w-1.5 rounded-full ${
                webapp_fixer.server_status === 'up' ? 'bg-green-400' :
                webapp_fixer.server_status === 'down' ? 'bg-red-400' : 'bg-yellow-400'
              }`} />
              {webapp_fixer.server_status === 'up' ? 'Serwer OK' :
               webapp_fixer.server_status === 'down' ? 'Serwer DOWN' : 'Nieznany'}
            </span>
            {webapp_fixer.consecutive_failures > 0 && (
              <span className="text-xs text-red-400">
                {webapp_fixer.consecutive_failures} kolejnych błędów
              </span>
            )}
          </div>
          <div className="grid grid-cols-2 gap-2">
            <StatCard label="Błędy razem" value={webapp_fixer.total_errors} />
            <StatCard label="Naprawione" value={webapp_fixer.resolved} />
            <StatCard label="Otwarte" value={webapp_fixer.open} />
            <StatCard label="Monitorowane trasy" value={webapp_fixer.routes_monitored} />
          </div>
          {webapp_fixer.last_check && (
            <p className="mt-2 text-xs text-[var(--text-secondary)]">
              Ostatnie sprawdzenie: {new Date(webapp_fixer.last_check).toLocaleString('pl-PL')}
            </p>
          )}
        </div>
      </div>

      {/* ── Section 2: Daily Chart ── */}
      <DailyChart history={daily_history} />

      {/* ── Section 3: Manual Review Queue ── */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
        <h3 className="mb-3 text-sm font-semibold text-[var(--text)]">
          Kolejka do przeglądu ({manual_queue.length})
        </h3>
        {manual_queue.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-8 text-[var(--text-secondary)]">
            <CheckCircle className="h-8 w-8 text-green-500" />
            <p className="text-sm">Brak znalezisk do przeglądu</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)]">
                  <th className="w-8 px-3 py-2" />
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-[var(--text-secondary)]">Poziom</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-[var(--text-secondary)]">Plik</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-[var(--text-secondary)]">Kategoria</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-[var(--text-secondary)]">Tytuł</th>
                  <th className="px-3 py-2 text-right text-xs font-semibold uppercase text-[var(--text-secondary)]">Próby</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-[var(--text-secondary)]">Tier3</th>
                </tr>
              </thead>
              <tbody>
                {manual_queue.map((item) => {
                  const expanded = expandedId === item.id;
                  return (
                    <Fragment key={item.id}>
                      <tr
                        className="cursor-pointer border-b border-[var(--border)] hover:bg-[var(--bg-hover)]"
                        onClick={() => setExpandedId(expanded ? null : item.id)}
                      >
                        <td className="px-3 py-2 text-[var(--text-secondary)]">
                          {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                        </td>
                        <td className="px-3 py-2">
                          <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${severityConfig[item.severity]?.className ?? 'bg-gray-600/20 text-gray-400'}`}>
                            {severityConfig[item.severity]?.label ?? item.severity}
                          </span>
                        </td>
                        <td className="max-w-[180px] truncate px-3 py-2 font-mono text-xs text-[var(--text)]">
                          {item.file_path.split('/').pop()}
                        </td>
                        <td className="px-3 py-2 text-[var(--text-secondary)]">{item.category}</td>
                        <td className="px-3 py-2 text-[var(--text)]">{item.title}</td>
                        <td className="px-3 py-2 text-right text-[var(--text-secondary)]">{item.attempts}</td>
                        <td className="px-3 py-2">
                          {item.tier3_attempted ? (
                            <span className="rounded bg-red-600/20 px-1.5 py-0.5 text-xs text-red-400">Tak</span>
                          ) : (
                            <span className="text-xs text-[var(--text-secondary)]">—</span>
                          )}
                        </td>
                      </tr>
                      {expanded && (
                        <tr className="border-b border-[var(--border)] bg-[var(--bg)]">
                          <td colSpan={7} className="px-6 py-4">
                            <p className="mb-1 font-mono text-xs text-[var(--text-secondary)]">{item.file_path}</p>
                            <p className="whitespace-pre-wrap text-sm text-[var(--text)]">{item.description}</p>
                            {item.suggested_fix && (
                              <div className="mt-3">
                                <p className="mb-1 text-xs font-semibold text-[var(--text-secondary)]">Sugerowana poprawka:</p>
                                <pre className="overflow-x-auto rounded bg-[var(--surface)] p-2 font-mono text-xs text-[var(--text)]">
                                  {item.suggested_fix}
                                </pre>
                              </div>
                            )}
                            {item.tier3_last_error && (
                              <div className="mt-2">
                                <p className="mb-1 text-xs font-semibold text-red-400">Ostatni błąd Tier3:</p>
                                <p className="text-xs text-red-300">{item.tier3_last_error}</p>
                              </div>
                            )}
                            <p className="mt-2 text-xs text-[var(--text-secondary)]">
                              Utworzone: {new Date(item.created_at).toLocaleString('pl-PL')}
                            </p>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
