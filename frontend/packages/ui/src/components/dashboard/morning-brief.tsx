'use client';

import { RefreshCw, ChevronDown, ChevronUp, Clock, AlertCircle } from 'lucide-react';
import type { MorningBriefResponse } from '@gilbertus/api-client';
import { MarkdownRenderer } from '../chat/markdown-renderer';

interface MorningBriefProps {
  data?: MorningBriefResponse;
  isLoading?: boolean;
  error?: Error | null;
  onRefresh?: () => void;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
}

function StatusDot({ status }: { status: string }) {
  const color =
    status === 'generated'
      ? 'bg-green-500'
      : status === 'cached'
        ? 'bg-gray-400'
        : 'bg-red-500';

  return <span className={`inline-block h-2 w-2 rounded-full ${color}`} />;
}

function LoadingSkeleton() {
  return (
    <div className="space-y-3 p-4">
      <div className="h-4 w-full animate-pulse rounded bg-[var(--surface-hover)]" />
      <div className="h-4 w-3/4 animate-pulse rounded bg-[var(--surface-hover)]" />
      <div className="h-4 w-5/6 animate-pulse rounded bg-[var(--surface-hover)]" />
      <div className="h-4 w-1/2 animate-pulse rounded bg-[var(--surface-hover)]" />
    </div>
  );
}

export function MorningBrief({
  data,
  isLoading,
  error,
  onRefresh,
  isCollapsed,
  onToggleCollapse,
}: MorningBriefProps) {
  if (error) {
    return (
      <div className="rounded-lg border-2 border-red-500/50 bg-[var(--surface)]">
        <div className="flex items-center gap-3 p-4">
          <AlertCircle size={20} className="shrink-0 text-red-500" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-red-500">
              Nie udalo sie zaladowac briefu
            </p>
            <p className="mt-1 text-xs text-[var(--text-secondary)]">
              {error.message}
            </p>
          </div>
          {onRefresh && (
            <button
              onClick={onRefresh}
              className="shrink-0 rounded-md px-3 py-1.5 text-sm font-medium text-[var(--accent)] hover:bg-[var(--surface-hover)] transition-colors"
            >
              Ponow
            </button>
          )}
        </div>
      </div>
    );
  }

  const formattedDate = data?.date
    ? new Date(data.date + 'T00:00:00').toLocaleDateString('pl-PL', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      })
    : null;

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)]">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-[var(--border)]">
        <div className="flex items-center gap-3">
          <h2 className="text-base font-semibold text-[var(--text)]">
            Poranny Brief
          </h2>
          {data?.status && <StatusDot status={data.status} />}
          {formattedDate && (
            <span className="rounded-full bg-[var(--surface-hover)] px-2.5 py-0.5 text-xs text-[var(--text-secondary)]">
              {formattedDate}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {onRefresh && (
            <button
              onClick={onRefresh}
              disabled={isLoading}
              className="inline-flex items-center justify-center rounded-md p-2 text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] transition-colors disabled:opacity-50"
              aria-label="Odswiez brief"
            >
              <RefreshCw
                size={16}
                className={isLoading ? 'animate-spin' : ''}
              />
            </button>
          )}
          {onToggleCollapse && (
            <button
              onClick={onToggleCollapse}
              className="inline-flex items-center justify-center rounded-md p-2 text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] transition-colors"
              aria-label={isCollapsed ? 'Rozwin' : 'Zwin'}
            >
              {isCollapsed ? (
                <ChevronDown size={16} />
              ) : (
                <ChevronUp size={16} />
              )}
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      {!isCollapsed && (
        <>
          {isLoading ? (
            <LoadingSkeleton />
          ) : data?.text ? (
            <div className="max-h-[600px] overflow-y-auto p-4">
              <MarkdownRenderer content={data.text} />
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center gap-2 p-8 text-[var(--text-secondary)]">
              <Clock size={24} />
              <p className="text-sm">Brief nie zostal jeszcze wygenerowany</p>
            </div>
          )}

          {/* Meta footer */}
          {data && !isLoading && data.text && (
            <div className="border-t border-[var(--border)] px-4 py-2.5">
              <p className="text-xs text-[var(--text-secondary)]">
                {data.events_count ?? 0} wydarzen &middot;{' '}
                {data.entities_count ?? 0} encji &middot;{' '}
                {data.open_loops_count ?? 0} otwartych watkow
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
