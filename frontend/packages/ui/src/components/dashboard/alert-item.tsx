'use client';

import { X } from 'lucide-react';
import type { AlertItem as AlertItemType } from '@gilbertus/api-client';

interface AlertItemProps {
  alert: AlertItemType;
  onDismiss?: (alertId: number) => void;
}

const SEVERITY_COLOR: Record<string, string> = {
  high: 'bg-red-500',
  medium: 'bg-amber-500',
  low: 'bg-blue-500',
};

const ALERT_TYPE_LABEL: Record<string, string> = {
  decision_no_followup: 'Brak follow-up',
  conflict_spike: 'Konflikt',
  missing_communication: 'Brak komunikacji',
  health_clustering: 'Zdrowie',
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

export function AlertItem({ alert, onDismiss }: AlertItemProps) {
  const severityDot = SEVERITY_COLOR[alert.severity] ?? 'bg-gray-400';
  const typeLabel = ALERT_TYPE_LABEL[alert.alert_type] ?? alert.alert_type;

  return (
    <div className="group flex items-start gap-3 rounded-md px-3 py-2.5 transition-colors hover:bg-[var(--surface-hover)]">
      {/* Severity dot */}
      <span
        className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${severityDot}`}
        aria-label={`Severity: ${alert.severity}`}
      />

      {/* Center content */}
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-[var(--text)]">
          {alert.title}
        </p>
        <p className="line-clamp-2 text-xs text-[var(--text-secondary)]">
          {alert.description}
        </p>
        <span className="mt-1 inline-block rounded-full bg-[var(--surface-hover)] px-2 py-0.5 text-[10px] text-[var(--text-secondary)]">
          {typeLabel}
        </span>
      </div>

      {/* Right side */}
      <div className="flex shrink-0 flex-col items-end gap-1">
        <span className="whitespace-nowrap text-[10px] text-[var(--text-secondary)]">
          {formatRelativeTime(alert.created_at)}
        </span>
        {onDismiss && (
          <button
            type="button"
            onClick={() => onDismiss(alert.alert_id)}
            className="rounded p-0.5 text-[var(--text-secondary)] opacity-0 transition-opacity hover:text-[var(--text)] group-hover:opacity-100"
            aria-label="Odrzuć alert"
          >
            <X size={14} />
          </button>
        )}
      </div>
    </div>
  );
}
