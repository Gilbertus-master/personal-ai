'use client';

import { Database, Search, Mic, HardDrive, Clock, Shield } from 'lucide-react';
import type { SystemStatus } from '@gilbertus/api-client';
import type { LucideIcon } from 'lucide-react';
import { cn } from '../../lib/utils';

// ── Props ──────────────────────────────────────────────────────────────────

interface SystemStatusProps {
  status: SystemStatus | undefined;
  isLoading: boolean;
}

// ── Helpers ────────────────────────────────────────────────────────────────

const SERVICE_ICONS: Record<string, LucideIcon> = {
  postgres: Database,
  qdrant: Search,
  whisper: Mic,
};

function timeAgo(isoDate: string): { text: string; color: string } {
  const diff = Date.now() - new Date(isoDate).getTime();
  const hours = diff / (1000 * 60 * 60);
  if (hours < 1) return { text: `${Math.round(hours * 60)} min temu`, color: 'text-green-400' };
  if (hours < 24) return { text: `${Math.round(hours)}h temu`, color: 'text-yellow-400' };
  const days = Math.round(hours / 24);
  return { text: `${days}d temu`, color: 'text-red-400' };
}

function SkeletonCard({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-lg bg-[var(--surface)]', className)} />;
}

// ── Component ──────────────────────────────────────────────────────────────

export function SystemStatusDashboard({ status, isLoading }: SystemStatusProps) {
  if (isLoading || !status) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => <SkeletonCard key={i} className="h-24" />)}
        </div>
        <div className="grid grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => <SkeletonCard key={i} className="h-20" />)}
        </div>
        <SkeletonCard className="h-48" />
      </div>
    );
  }

  const services = Object.entries(status.services);
  const sources = Object.entries(status.sources);

  return (
    <div className="space-y-6">
      {/* Service Health Grid */}
      <section>
        <h3 className="mb-3 text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">
          Usługi
        </h3>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {services.map(([name, svc]) => {
            const Icon = SERVICE_ICONS[name] ?? Shield;
            const isOk = svc.status === 'ok';
            return (
              <div key={name} className="flex items-center gap-4 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
                <div className={cn('rounded-lg p-2', isOk ? 'bg-green-500/10' : 'bg-red-500/10')}>
                  <Icon className={cn('h-5 w-5', isOk ? 'text-green-400' : 'text-red-400')} />
                </div>
                <div>
                  <p className="text-sm font-medium capitalize text-[var(--text)]">{name}</p>
                  <p className={cn('text-xs font-medium', isOk ? 'text-green-400' : 'text-red-400')}>
                    {isOk ? 'OK' : 'Error'}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Database Stats */}
      <section>
        <h3 className="mb-3 text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">
          Baza danych
        </h3>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {[
            { label: 'Chunks', value: status.db.total_chunks.toLocaleString('pl-PL') },
            { label: 'Events', value: status.db.total_events.toLocaleString('pl-PL') },
            { label: 'Źródła', value: status.db.total_sources.toLocaleString('pl-PL') },
            { label: 'Rozmiar', value: `${status.db.data_volume_gb.toFixed(2)} GB` },
          ].map((stat) => (
            <div key={stat.label} className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
              <p className="text-2xl font-semibold text-[var(--text)]">{stat.value}</p>
              <p className="mt-1 text-xs text-[var(--text-secondary)]">{stat.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Embedding Status */}
      <section>
        <h3 className="mb-3 text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">
          Embeddingi
        </h3>
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
          <div className="flex items-center gap-4">
            <div>
              <p className="text-lg font-semibold text-[var(--text)]">
                {status.embedding.indexed_chunks.toLocaleString('pl-PL')} zaindeksowanych
              </p>
              <div className="mt-1 flex items-center gap-2">
                <span
                  className={cn(
                    'inline-block h-2 w-2 rounded-full',
                    status.embedding.status === 'ok' ? 'bg-green-400' : status.embedding.status === 'degraded' ? 'bg-yellow-400' : 'bg-red-400',
                  )}
                />
                <span className="text-xs text-[var(--text-secondary)]">
                  Qdrant: {status.embedding.status}
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Source Sync Table */}
      <section>
        <h3 className="mb-3 text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">
          Synchronizacja źródeł
        </h3>
        <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] bg-[var(--surface)]">
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">Źródło</th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">Ostatni import</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {sources.map(([source, timestamp]) => {
                const ts = typeof timestamp === 'string' ? timestamp : String(timestamp);
                const ago = timeAgo(ts);
                return (
                  <tr key={source} className="bg-[var(--bg)]">
                    <td className="px-4 py-3 font-medium capitalize text-[var(--text)]">{source}</td>
                    <td className={cn('px-4 py-3 text-right text-xs', ago.color)}>{ago.text}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* Backup & Cron Health */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {/* Backup */}
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
          <div className="flex items-center gap-2 text-[var(--text-secondary)]">
            <HardDrive className="h-4 w-4" />
            <span className="text-xs font-medium uppercase tracking-wider">Backup</span>
          </div>
          {status.last_backup ? (
            <div className="mt-2">
              <p className="text-sm text-[var(--text)]">{new Date(status.last_backup).toLocaleString('pl-PL')}</p>
              <p className={cn('text-xs', timeAgo(status.last_backup).color)}>
                {timeAgo(status.last_backup).text}
              </p>
            </div>
          ) : (
            <p className="mt-2 text-sm text-[var(--text-secondary)]">Brak danych</p>
          )}
        </div>

        {/* Cron Health */}
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
          <div className="flex items-center gap-2 text-[var(--text-secondary)]">
            <Clock className="h-4 w-4" />
            <span className="text-xs font-medium uppercase tracking-wider">Crony</span>
          </div>
          <div className="mt-2 space-y-1">
            <p className="text-sm text-[var(--text)]">
              {status.crons.enabled} / {status.crons.total} aktywnych
            </p>
            {status.crons.failed.length > 0 && (
              <div className="mt-1 space-y-0.5">
                {status.crons.failed.map((f) => (
                  <p key={f} className="text-xs text-red-400">{f}</p>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
