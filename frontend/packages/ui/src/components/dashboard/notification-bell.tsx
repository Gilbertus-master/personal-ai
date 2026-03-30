'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { Bell, X } from 'lucide-react';
import type { AlertItem } from '@gilbertus/api-client';
import { ActionableItem } from '../shared/actionable-item';

interface NotificationBellProps {
  alerts?: AlertItem[];
  isLoading?: boolean;
  dismissedIds?: number[];
  onDismiss?: (alertId: number) => void;
  onViewAll?: () => void;
}

const SEVERITY_COLOR: Record<string, string> = {
  high: 'bg-red-500',
  medium: 'bg-amber-500',
  low: 'bg-blue-500',
};

function formatRelativeTime(dateStr: string | null): string {
  if (!dateStr) return '';
  const now = Date.now();
  const date = new Date(dateStr).getTime();
  const diffMs = now - date;
  const diffMin = Math.floor(diffMs / 60_000);
  const diffH = Math.floor(diffMs / 3_600_000);
  const diffD = Math.floor(diffMs / 86_400_000);

  if (diffMin < 1) return 'teraz';
  if (diffMin < 60) return `${diffMin}min temu`;
  if (diffH < 24) return `${diffH}h temu`;
  if (diffD === 1) return 'wczoraj';
  if (diffD < 7) return `${diffD}d temu`;
  return new Date(dateStr).toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' });
}

export function NotificationBell({
  alerts,
  isLoading,
  dismissedIds = [],
  onDismiss,
  onViewAll,
}: NotificationBellProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const activeAlerts = alerts?.filter((a) => !dismissedIds.includes(a.alert_id)) ?? [];
  const count = activeAlerts.length;
  const displayAlerts = activeAlerts.slice(0, 5);

  const close = useCallback(() => setOpen(false), []);

  // Close on click outside
  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        close();
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open, close]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') close();
    }
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [open, close]);

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="relative inline-flex items-center justify-center rounded-md p-2 text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] transition-colors"
        aria-label="Powiadomienia"
        aria-expanded={open}
      >
        <Bell className="h-5 w-5" />
        {count > 0 && (
          <span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">
            {count > 9 ? '9+' : count}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-80 rounded-lg bg-[var(--surface)] border border-[var(--border)] shadow-lg z-50">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-2.5">
            <span className="text-sm font-medium text-[var(--text)]">
              Powiadomienia
              {count > 0 && (
                <span className="ml-1.5 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-red-500/10 px-1.5 text-xs font-medium text-red-500">
                  {count}
                </span>
              )}
            </span>
          </div>

          {/* List */}
          <div className="max-h-80 overflow-y-auto">
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <span className="text-sm text-[var(--text-secondary)]">Ładowanie...</span>
              </div>
            ) : displayAlerts.length === 0 ? (
              <div className="flex flex-col items-center justify-center gap-2 py-8">
                <Bell className="h-8 w-8 text-[var(--text-secondary)] opacity-40" />
                <span className="text-sm text-[var(--text-secondary)]">Brak nowych powiadomień</span>
              </div>
            ) : (
              displayAlerts.map((alert) => {
                const severityDot = SEVERITY_COLOR[alert.severity] ?? 'bg-gray-400';
                return (
                  <ActionableItem
                    key={alert.alert_id}
                    itemId={`alert_${alert.alert_id}`}
                    itemType="alert"
                    itemTitle={alert.title}
                    itemContent={alert}
                    context="alerts"
                  >
                    <div className="group flex items-start gap-3 px-4 py-2.5 transition-colors hover:bg-[var(--surface-hover)]">
                      <span
                        className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${severityDot}`}
                        aria-label={`Severity: ${alert.severity}`}
                      />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-[var(--text)]">
                          {alert.title}
                        </p>
                        <span className="text-[10px] text-[var(--text-secondary)]">
                          {formatRelativeTime(alert.created_at)}
                        </span>
                      </div>
                      {onDismiss && (
                        <button
                          type="button"
                          onClick={() => onDismiss(alert.alert_id)}
                          className="shrink-0 rounded p-0.5 text-[var(--text-secondary)] opacity-0 transition-opacity hover:text-[var(--text)] group-hover:opacity-100"
                          aria-label="Odrzuć"
                        >
                          <X size={14} />
                        </button>
                      )}
                    </div>
                  </ActionableItem>
                );
              })
            )}
          </div>

          {/* Footer */}
          {count > 0 && (
            <div className="border-t border-[var(--border)] px-4 py-2">
              <button
                type="button"
                onClick={() => {
                  onViewAll?.();
                  close();
                }}
                className="w-full text-center text-xs font-medium text-[var(--accent)] hover:underline"
              >
                Pokaż wszystkie
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
