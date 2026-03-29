'use client';

import { ExternalLink } from 'lucide-react';
import type { CompetitorSignal } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';

interface SignalTimelineProps {
  signals: CompetitorSignal[];
  showCompetitorName?: boolean;
}

const SIGNAL_TYPE_BADGE: Record<CompetitorSignal['type'], { label: string; color: string }> = {
  krs_change: { label: 'KRS', color: 'bg-purple-500/20 text-purple-400' },
  hiring: { label: 'Rekrutacja', color: 'bg-blue-500/20 text-blue-400' },
  media: { label: 'Media', color: 'bg-cyan-500/20 text-cyan-400' },
  tender: { label: 'Przetarg', color: 'bg-green-500/20 text-green-400' },
  financial: { label: 'Finanse', color: 'bg-amber-500/20 text-amber-400' },
};

const SEVERITY_BADGE: Record<CompetitorSignal['severity'], { label: string; color: string }> = {
  low: { label: 'Niski', color: 'bg-gray-500/20 text-gray-400' },
  medium: { label: 'Średni', color: 'bg-amber-500/20 text-amber-400' },
  high: { label: 'Wysoki', color: 'bg-red-500/20 text-red-400' },
};

function formatDate(dateStr: string | null): string {
  if (!dateStr) return 'Brak daty';
  return new Date(dateStr).toLocaleDateString('pl-PL', { day: 'numeric', month: 'short', year: 'numeric' });
}

export function SignalTimeline({ signals, showCompetitorName = false }: SignalTimelineProps) {
  if (signals.length === 0) {
    return (
      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 text-center text-sm text-[var(--text-secondary)]">
        Brak sygnałów
      </div>
    );
  }

  return (
    <div className="relative space-y-0">
      {/* Timeline line */}
      <div className="absolute bottom-0 left-[59px] top-0 w-px bg-[var(--border)]" />

      {signals.map((signal) => {
        const typeBadge = SIGNAL_TYPE_BADGE[signal.type];
        const sevBadge = SEVERITY_BADGE[signal.severity];

        return (
          <div key={signal.id} className="relative flex gap-4 py-3">
            {/* Date (left side) */}
            <div className="w-[52px] shrink-0 pt-0.5 text-right text-[10px] text-[var(--text-secondary)]">
              {formatDate(signal.date)}
            </div>

            {/* Timeline dot */}
            <div className="relative z-10 mt-1.5 h-3 w-3 shrink-0 rounded-full border-2 border-[var(--accent)] bg-[var(--surface)]" />

            {/* Content */}
            <div className="min-w-0 flex-1 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3 transition-colors hover:bg-[var(--surface-hover)]">
              <div className="mb-1.5 flex flex-wrap items-center gap-1.5">
                <span className={cn('rounded-full px-2 py-0.5 text-[10px] font-semibold', typeBadge.color)}>
                  {typeBadge.label}
                </span>
                <span className={cn('rounded-full px-2 py-0.5 text-[10px] font-semibold', sevBadge.color)}>
                  {sevBadge.label}
                </span>
                {showCompetitorName && (
                  <span className="rounded-full bg-[var(--bg-hover)] px-2 py-0.5 text-[10px] text-[var(--text-secondary)]">
                    {signal.competitor}
                  </span>
                )}
              </div>

              <h4 className="text-sm font-medium text-[var(--text)]">{signal.title}</h4>
              {signal.description && (
                <p className="mt-1 text-xs leading-relaxed text-[var(--text-secondary)]">{signal.description}</p>
              )}

              {signal.source_url && (
                <a
                  href={signal.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-2 inline-flex items-center gap-1 text-[10px] text-[var(--accent)] hover:underline"
                >
                  <ExternalLink size={10} />
                  Źródło
                </a>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
