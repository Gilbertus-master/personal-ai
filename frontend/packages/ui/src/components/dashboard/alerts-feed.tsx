'use client';

import { ChevronDown, ChevronUp, CircleCheck, AlertCircle } from 'lucide-react';
import type { AlertItem as AlertItemType } from '@gilbertus/api-client';
import { SkeletonCard } from '../skeleton-card';
import { AlertItem } from './alert-item';

interface AlertsFeedProps {
  alerts?: AlertItemType[];
  dismissedIds?: number[];
  isLoading?: boolean;
  error?: Error | null;
  onDismiss?: (alertId: number) => void;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
}

export function AlertsFeed({
  alerts,
  dismissedIds = [],
  isLoading,
  error,
  onDismiss,
  isCollapsed,
  onToggleCollapse,
}: AlertsFeedProps) {
  const dismissedSet = new Set(dismissedIds);
  const visibleAlerts = alerts?.filter((a) => !dismissedSet.has(a.alert_id)) ?? [];

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)]">
      {/* Header */}
      <button
        type="button"
        onClick={onToggleCollapse}
        className="flex w-full items-center justify-between px-4 py-3"
      >
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-[var(--text)]">Alerty</h3>
          {!isLoading && visibleAlerts.length > 0 && (
            <span className="rounded-full bg-red-500/20 px-2 py-0.5 text-xs text-red-400">
              {visibleAlerts.length}
            </span>
          )}
        </div>
        {isCollapsed ? (
          <ChevronDown size={16} className="text-[var(--text-secondary)]" />
        ) : (
          <ChevronUp size={16} className="text-[var(--text-secondary)]" />
        )}
      </button>

      {/* Content */}
      {!isCollapsed && (
        <div className="border-t border-[var(--border)]">
          {isLoading && (
            <div className="space-y-2 p-4">
              <SkeletonCard height="h-16" />
              <SkeletonCard height="h-16" />
              <SkeletonCard height="h-16" />
            </div>
          )}

          {!isLoading && error && (
            <div className="flex flex-col items-center gap-2 p-6 text-center">
              <AlertCircle size={24} className="text-red-400" />
              <p className="text-sm text-[var(--text-secondary)]">
                Nie udało się załadować alertów
              </p>
              <button
                type="button"
                onClick={onToggleCollapse}
                className="text-xs text-blue-400 hover:underline"
              >
                Spróbuj ponownie
              </button>
            </div>
          )}

          {!isLoading && !error && visibleAlerts.length === 0 && (
            <div className="flex flex-col items-center gap-2 p-6 text-center">
              <CircleCheck size={24} className="text-green-400" />
              <p className="text-sm text-[var(--text-secondary)]">
                Brak aktywnych alertów
              </p>
            </div>
          )}

          {!isLoading && !error && visibleAlerts.length > 0 && (
            <div className="max-h-96 overflow-y-auto">
              {visibleAlerts.map((alert) => (
                <AlertItem
                  key={alert.alert_id}
                  alert={alert}
                  onDismiss={onDismiss}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
