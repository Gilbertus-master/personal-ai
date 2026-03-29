'use client';

import { AlertCircle, RefreshCw } from 'lucide-react';
import type { IngestionDashboard } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';

export interface IngestionStatusProps {
  dashboard: IngestionDashboard | undefined;
  isLoading: boolean;
}

function formatRelativeDate(dateStr: string | null): string {
  if (!dateStr) return '\u2014';
  try {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMin = Math.floor(diffMs / 60_000);
    const diffH = Math.floor(diffMs / 3_600_000);
    const diffD = Math.floor(diffMs / 86_400_000);

    if (diffMin < 1) return 'przed chwilą';
    if (diffMin < 60) return `${diffMin} min temu`;
    if (diffH < 24) return `${diffH}h temu`;
    if (diffD < 7) return `${diffD}d temu`;
    return new Intl.DateTimeFormat('pl-PL', { day: 'numeric', month: 'short' }).format(date);
  } catch {
    return '\u2014';
  }
}

function SkeletonCards() {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <div
          key={i}
          className="rounded-lg border p-3 animate-pulse"
          style={{ borderColor: 'var(--border)', backgroundColor: 'var(--surface)' }}
        >
          <div className="h-3 w-16 rounded bg-[var(--border)] mb-2" />
          <div className="h-5 w-10 rounded bg-[var(--border)]" />
        </div>
      ))}
    </div>
  );
}

export function IngestionStatus({ dashboard, isLoading }: IngestionStatusProps) {
  if (isLoading || !dashboard) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <RefreshCw size={14} className="animate-spin" style={{ color: 'var(--text-secondary)' }} />
          <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
            Ładowanie statusu...
          </span>
        </div>
        <SkeletonCards />
      </div>
    );
  }

  const sources = Object.entries(dashboard.sources);
  const backlogs = Object.entries(dashboard.extraction_backlogs);
  const { dlq_stats, guardian_alerts } = dashboard;

  return (
    <div className="space-y-4">
      {/* Source health cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {sources.map(([type, info]) => (
          <div
            key={type}
            className="rounded-lg border p-3"
            style={{ borderColor: 'var(--border)', backgroundColor: 'var(--surface)' }}
          >
            <p className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--text-secondary)' }}>
              {type}
            </p>
            <p className="mt-1 text-lg font-semibold" style={{ color: 'var(--text)' }}>
              {info.total.toLocaleString('pl-PL')}
            </p>
            <p className="text-[10px]" style={{ color: 'var(--text-secondary)' }}>
              {formatRelativeDate(info.last_imported)}
            </p>
          </div>
        ))}
      </div>

      {/* Extraction backlog */}
      {backlogs.length > 0 && (
        <div
          className="rounded-lg border p-4"
          style={{ borderColor: 'var(--border)', backgroundColor: 'var(--surface)' }}
        >
          <p className="mb-2 text-xs font-medium" style={{ color: 'var(--text)' }}>
            Zaległości ekstrakcji
          </p>
          <div className="space-y-2">
            {backlogs.map(([source, pending]) => (
              <div key={source} className="flex items-center gap-2">
                <span className="w-20 text-[10px] uppercase" style={{ color: 'var(--text-secondary)' }}>
                  {source}
                </span>
                <div className="flex-1 h-2 rounded-full" style={{ backgroundColor: 'var(--border)' }}>
                  <div
                    className={cn(
                      'h-full rounded-full transition-all',
                      pending > 100 ? 'bg-amber-500' : 'bg-emerald-500',
                    )}
                    style={{ width: `${Math.min(100, (pending / Math.max(...backlogs.map(([, v]) => v), 1)) * 100)}%` }}
                  />
                </div>
                <span className="w-12 text-right text-[10px]" style={{ color: 'var(--text-secondary)' }}>
                  {pending}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* DLQ + Guardian */}
      <div className="grid grid-cols-2 gap-3">
        {/* DLQ stats */}
        <div
          className="rounded-lg border p-4"
          style={{ borderColor: 'var(--border)', backgroundColor: 'var(--surface)' }}
        >
          <p className="mb-2 text-xs font-medium" style={{ color: 'var(--text)' }}>
            Kolejka błędów (DLQ)
          </p>
          <p className="text-lg font-semibold" style={{ color: dlq_stats.total > 0 ? 'var(--text)' : 'var(--text-secondary)' }}>
            {dlq_stats.total}
          </p>
          {Object.entries(dlq_stats.by_error).length > 0 && (
            <div className="mt-2 space-y-0.5">
              {Object.entries(dlq_stats.by_error).map(([err, count]) => (
                <div key={err} className="flex justify-between text-[10px]" style={{ color: 'var(--text-secondary)' }}>
                  <span className="truncate max-w-[120px]">{err}</span>
                  <span>{count}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Guardian alerts */}
        <div
          className="rounded-lg border p-4"
          style={{ borderColor: 'var(--border)', backgroundColor: 'var(--surface)' }}
        >
          <p className="mb-2 text-xs font-medium" style={{ color: 'var(--text)' }}>
            Alerty Guardian
          </p>
          <div className="flex items-center gap-2">
            <p className="text-lg font-semibold" style={{ color: 'var(--text)' }}>
              {guardian_alerts.total}
            </p>
            {guardian_alerts.critical > 0 && (
              <span className="flex items-center gap-1 rounded-full bg-red-500/20 px-2 py-0.5 text-[10px] font-medium text-red-400">
                <AlertCircle size={10} />
                {guardian_alerts.critical} krytycznych
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
