'use client';

import { Database, Server, HardDrive, AlertCircle } from 'lucide-react';
import type { StatusResponse } from '@gilbertus/api-client';

interface SystemStatusProps {
  status?: StatusResponse;
  isLoading?: boolean;
  error?: Error | null;
}

interface ServiceInfo {
  key: string;
  label: string;
  status: string;
  error?: string;
}

function formatNumber(n: number): string {
  return n.toLocaleString('pl-PL');
}

function formatBackupTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  const date = new Date(dateStr);
  return date.toLocaleDateString('pl-PL', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function LoadingSkeleton() {
  return (
    <div className="space-y-4 p-4">
      <div className="grid grid-cols-3 gap-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-10 animate-pulse rounded bg-[var(--surface-hover)]" />
        ))}
      </div>
      <div className="h-4 w-full animate-pulse rounded bg-[var(--surface-hover)]" />
      <div className="h-3 w-2/3 animate-pulse rounded bg-[var(--surface-hover)]" />
    </div>
  );
}

export function SystemStatus({ status, isLoading, error }: SystemStatusProps) {
  if (error) {
    return (
      <div className="rounded-lg border-2 border-red-500/50 bg-[var(--surface)]">
        <div className="flex items-center gap-3 p-4">
          <AlertCircle size={20} className="shrink-0 text-red-500" />
          <p className="text-sm text-red-500">{error.message}</p>
        </div>
      </div>
    );
  }

  const services: ServiceInfo[] = status
    ? [
        { key: 'postgres', label: 'Postgres', ...status.services.postgres },
        { key: 'qdrant', label: 'Qdrant', ...status.services.qdrant },
        { key: 'whisper', label: 'Whisper', ...status.services.whisper },
      ]
    : [];

  const embeddingsPct =
    status && status.embeddings.total > 0
      ? Math.round((status.embeddings.done / status.embeddings.total) * 100)
      : 0;

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)]">
      {/* Header */}
      <div className="border-b border-[var(--border)] p-4">
        <h2 className="text-base font-semibold text-[var(--text)]">Status systemu</h2>
      </div>

      {isLoading ? (
        <LoadingSkeleton />
      ) : status ? (
        <div className="space-y-4 p-4">
          {/* Services grid */}
          <div className="grid grid-cols-3 gap-3">
            {services.map((svc) => (
              <div
                key={svc.key}
                className="flex flex-col items-center gap-1 rounded-md bg-[var(--bg)] p-2"
              >
                <div className="flex items-center gap-1.5">
                  <span
                    className={`h-2 w-2 rounded-full ${svc.status === 'ok' ? 'bg-emerald-500' : 'bg-red-500'}`}
                  />
                  <span className="text-xs font-medium text-[var(--text)]">
                    {svc.label}
                  </span>
                </div>
                {svc.error && (
                  <span className="text-[10px] text-red-400">{svc.error}</span>
                )}
              </div>
            ))}
          </div>

          {/* DB stats */}
          <div className="flex items-center gap-4 text-xs text-[var(--text-secondary)]">
            <Database size={14} className="shrink-0" />
            <span>
              <strong className="text-[var(--text)]">{formatNumber(status.db.chunks)}</strong>{' '}
              chunks
            </span>
            <span>
              <strong className="text-[var(--text)]">{formatNumber(status.db.entities)}</strong>{' '}
              encji
            </span>
            <span>
              <strong className="text-[var(--text)]">{formatNumber(status.db.events)}</strong>{' '}
              wydarzeń
            </span>
          </div>

          {/* Embeddings progress */}
          <div className="space-y-1">
            <div className="flex items-center justify-between text-xs text-[var(--text-secondary)]">
              <div className="flex items-center gap-1.5">
                <Server size={14} />
                <span>Embeddingi</span>
              </div>
              <span>
                {formatNumber(status.embeddings.done)}/{formatNumber(status.embeddings.total)}
              </span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--surface-hover)]">
              <div
                className="h-full rounded-full bg-[var(--accent)] transition-all"
                style={{ width: `${embeddingsPct}%` }}
              />
            </div>
          </div>

          {/* Last backup */}
          <div className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)]">
            <HardDrive size={14} />
            <span>Ostatni backup: {formatBackupTime(status.last_backup)}</span>
          </div>
        </div>
      ) : null}
    </div>
  );
}
