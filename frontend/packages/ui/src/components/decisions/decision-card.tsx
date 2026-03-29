'use client';

import { ChevronDown, ChevronRight, Plus } from 'lucide-react';
import type { Decision, DecisionArea } from '@gilbertus/api-client';
import { StarRating } from './star-rating';

export interface DecisionCardProps {
  decision: Decision;
  expanded: boolean;
  onToggle: () => void;
  onAddOutcome: (id: number) => void;
}

const AREA_COLORS: Record<DecisionArea, { bg: string; text: string; label: string }> = {
  business: { bg: '#1e3a5f', text: '#60a5fa', label: 'Biznes' },
  trading: { bg: '#14532d', text: '#4ade80', label: 'Trading' },
  relationships: { bg: '#3b0764', text: '#c084fc', label: 'Relacje' },
  wellbeing: { bg: '#422006', text: '#fbbf24', label: 'Wellbeing' },
  general: { bg: '#1f2937', text: '#9ca3af', label: 'Ogólne' },
};

function getConfidenceColor(val: number): string {
  if (val <= 0.25) return 'var(--danger)';
  if (val <= 0.5) return 'var(--warning)';
  return 'var(--success)';
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('pl-PL', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

export function DecisionCard({ decision, expanded, onToggle, onAddOutcome }: DecisionCardProps) {
  const area = AREA_COLORS[decision.area] ?? AREA_COLORS.general;
  const conf = decision.confidence;
  const confColor = getConfidenceColor(conf);
  const confPct = Math.round(conf * 100);

  return (
    <div
      className="rounded-lg border transition-colors"
      style={{ backgroundColor: 'var(--surface)', borderColor: 'var(--border)' }}
    >
      {/* Header row */}
      <button
        onClick={onToggle}
        className="flex w-full items-center gap-3 px-4 py-3 text-left"
      >
        {expanded ? (
          <ChevronDown size={16} style={{ color: 'var(--text-secondary)' }} />
        ) : (
          <ChevronRight size={16} style={{ color: 'var(--text-secondary)' }} />
        )}

        {/* Area badge */}
        <span
          className="rounded-full px-2 py-0.5 text-xs font-medium"
          style={{ backgroundColor: area.bg, color: area.text }}
        >
          {area.label}
        </span>

        {/* Decision text */}
        <span
          className={`flex-1 text-sm ${expanded ? '' : 'truncate'}`}
          style={{ color: 'var(--text)' }}
        >
          {decision.decision_text}
        </span>

        {/* Confidence bar */}
        <div className="flex w-24 items-center gap-2">
          <div
            className="h-1.5 flex-1 rounded-full"
            style={{ backgroundColor: 'var(--border)' }}
          >
            <div
              className="h-full rounded-full transition-all"
              style={{ width: `${confPct}%`, backgroundColor: confColor }}
            />
          </div>
          <span className="text-xs tabular-nums" style={{ color: confColor }}>
            {confPct}%
          </span>
        </div>

        {/* Date */}
        <span className="text-xs whitespace-nowrap" style={{ color: 'var(--text-secondary)' }}>
          {formatDate(decision.decided_at)}
        </span>
      </button>

      {/* Expanded section */}
      {expanded && (
        <div className="space-y-3 border-t px-4 py-3" style={{ borderColor: 'var(--border)' }}>
          {decision.context && (
            <div>
              <span className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
                Kontekst
              </span>
              <p className="mt-0.5 text-sm" style={{ color: 'var(--text)' }}>
                {decision.context}
              </p>
            </div>
          )}

          {decision.expected_outcome && (
            <div>
              <span className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
                Oczekiwany wynik
              </span>
              <p className="mt-0.5 text-sm" style={{ color: 'var(--text)' }}>
                {decision.expected_outcome}
              </p>
            </div>
          )}

          {/* Outcomes */}
          {decision.outcomes.length > 0 && (
            <div>
              <span className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
                Wyniki ({decision.outcomes.length})
              </span>
              <div className="mt-1 space-y-2">
                {decision.outcomes.map((o) => (
                  <div
                    key={o.id}
                    className="flex items-start gap-3 rounded-md p-2"
                    style={{ backgroundColor: 'var(--bg)' }}
                  >
                    <StarRating value={o.rating} readonly size="sm" />
                    <div className="flex-1">
                      <p className="text-sm" style={{ color: 'var(--text)' }}>
                        {o.actual_outcome}
                      </p>
                      <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                        {formatDate(o.outcome_date)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <button
            onClick={(e) => {
              e.stopPropagation();
              onAddOutcome(decision.id);
            }}
            className="inline-flex items-center gap-1 rounded-md px-3 py-1 text-xs font-medium transition-colors"
            style={{ backgroundColor: 'var(--accent)', color: '#fff' }}
          >
            <Plus size={12} />
            Dodaj wynik
          </button>
        </div>
      )}
    </div>
  );
}
