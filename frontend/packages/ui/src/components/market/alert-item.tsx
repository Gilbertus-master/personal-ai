'use client';

import { Info, AlertTriangle, Octagon, Check } from 'lucide-react';
import type { MarketAlert } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';

interface MarketAlertItemProps {
  alert: MarketAlert;
  onAcknowledge?: (id: number) => void;
}

const LEVEL_CONFIG: Record<MarketAlert['level'], { icon: typeof Info; color: string; bg: string }> = {
  info: { icon: Info, color: 'text-blue-400', bg: 'bg-blue-500/10' },
  warning: { icon: AlertTriangle, color: 'text-amber-400', bg: 'bg-amber-500/10' },
  critical: { icon: Octagon, color: 'text-red-400', bg: 'bg-red-500/10' },
};

const LEVEL_LABEL: Record<MarketAlert['level'], string> = {
  info: 'Info',
  warning: 'Ostrzeżenie',
  critical: 'Krytyczny',
};

function formatRelativeTime(dateStr: string): string {
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

export function MarketAlertItem({ alert, onAcknowledge }: MarketAlertItemProps) {
  const config = LEVEL_CONFIG[alert.level];
  const Icon = config.icon;

  return (
    <div
      className={cn(
        'flex items-start gap-3 rounded-lg border border-[var(--border)] p-3 transition-colors',
        alert.acknowledged ? 'opacity-60' : 'hover:bg-[var(--surface-hover)]',
      )}
    >
      {/* Level icon */}
      <div className={cn('mt-0.5 shrink-0 rounded-md p-1.5', config.bg)}>
        <Icon size={16} className={config.color} />
      </div>

      {/* Content */}
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex items-center gap-2">
          <span className={cn('text-[10px] font-semibold uppercase', config.color)}>
            {LEVEL_LABEL[alert.level]}
          </span>
          <span className="text-[10px] text-[var(--text-secondary)]">
            {formatRelativeTime(alert.created_at)}
          </span>
        </div>
        <p className="text-sm text-[var(--text)]">{alert.message}</p>
        {alert.insight_title && (
          <p className="mt-1 text-xs text-[var(--text-secondary)]">
            Insight: {alert.insight_title}
          </p>
        )}
      </div>

      {/* Acknowledge button */}
      <div className="shrink-0">
        {alert.acknowledged ? (
          <span className="flex items-center gap-1 rounded-full bg-green-500/10 px-2 py-1 text-[10px] text-green-400">
            <Check size={12} />
            Potwierdzone
          </span>
        ) : (
          <button
            type="button"
            onClick={() => onAcknowledge?.(alert.id)}
            disabled={!onAcknowledge}
            className={cn(
              'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
              onAcknowledge
                ? 'bg-[var(--accent)] text-white hover:opacity-90'
                : 'cursor-not-allowed bg-[var(--border)] text-[var(--text-secondary)] opacity-50',
            )}
          >
            Potwierdź
          </button>
        )}
      </div>
    </div>
  );
}
