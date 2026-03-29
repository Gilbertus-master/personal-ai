'use client';

import { ChevronDown, ChevronUp, Building2, Clock } from 'lucide-react';
import type { MarketInsight } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';

interface InsightCardProps {
  insight: MarketInsight;
  expanded?: boolean;
  onToggle?: () => void;
}

const TYPE_BADGE: Record<MarketInsight['type'], { label: string; color: string }> = {
  price_change: { label: 'Zmiana ceny', color: 'bg-blue-500/20 text-blue-400' },
  regulation: { label: 'Regulacja', color: 'bg-orange-500/20 text-orange-400' },
  tender: { label: 'Przetarg', color: 'bg-green-500/20 text-green-400' },
  trend: { label: 'Trend', color: 'bg-purple-500/20 text-purple-400' },
  risk: { label: 'Ryzyko', color: 'bg-red-500/20 text-red-400' },
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

export function InsightCard({ insight, expanded = false, onToggle }: InsightCardProps) {
  const badge = TYPE_BADGE[insight.type];
  const relevancePct = Math.round(insight.relevance * 100);

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 transition-colors hover:bg-[var(--surface-hover)]">
      {/* Header row */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="mb-1.5 flex flex-wrap items-center gap-2">
            <span className={cn('rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase', badge.color)}>
              {badge.label}
            </span>
            <span className="flex items-center gap-1 text-[10px] text-[var(--text-secondary)]">
              <Clock size={10} />
              {formatRelativeTime(insight.created_at)}
            </span>
          </div>
          <h3 className="text-sm font-medium text-[var(--text)]">{insight.title}</h3>
        </div>

        {onToggle && (
          <button
            type="button"
            onClick={onToggle}
            className="shrink-0 rounded p-1 text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--text)]"
            aria-label={expanded ? 'Zwiń' : 'Rozwiń'}
          >
            {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
        )}
      </div>

      {/* Relevance bar */}
      <div className="mt-2.5 flex items-center gap-2">
        <span className="text-[10px] text-[var(--text-secondary)]">Trafność</span>
        <div className="h-1.5 flex-1 rounded-full bg-[var(--border)]">
          <div
            className="h-full rounded-full bg-[var(--accent)] transition-all"
            style={{ width: `${relevancePct}%` }}
          />
        </div>
        <span className="text-[10px] font-medium text-[var(--text-secondary)]">{relevancePct}%</span>
      </div>

      {/* Expanded section */}
      {expanded && (
        <div className="mt-3 space-y-2 border-t border-[var(--border)] pt-3">
          <p className="text-xs leading-relaxed text-[var(--text-secondary)]">{insight.description}</p>
          {insight.impact && (
            <div className="rounded-md bg-[var(--bg-hover)] px-3 py-2">
              <span className="text-[10px] font-semibold uppercase text-[var(--text-secondary)]">Wpływ</span>
              <p className="mt-0.5 text-xs text-[var(--text)]">{insight.impact}</p>
            </div>
          )}
        </div>
      )}

      {/* Companies tags */}
      {insight.companies.length > 0 && (
        <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
          <Building2 size={12} className="text-[var(--text-secondary)]" />
          {insight.companies.map((company) => (
            <span
              key={company}
              className="rounded-full bg-[var(--bg-hover)] px-2 py-0.5 text-[10px] text-[var(--text-secondary)]"
            >
              {company}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
