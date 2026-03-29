'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp, Star, AlertTriangle, CheckCircle, XCircle } from 'lucide-react';
import type { TechSolution } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';

export interface TechSolutionCardProps {
  solution: TechSolution;
  onStatusChange?: (id: number, status: string) => void;
}

const TYPE_CONFIG: Record<TechSolution['solution_type'], { label: string; color: string }> = {
  build: { label: 'Budowa', color: 'bg-blue-500/20 text-blue-400' },
  buy: { label: 'Zakup', color: 'bg-green-500/20 text-green-400' },
  extend: { label: 'Rozszerzenie', color: 'bg-purple-500/20 text-purple-400' },
};

const STATUS_CONFIG: Record<TechSolution['status'], { label: string; color: string }> = {
  proposed: { label: 'Propozycja', color: 'bg-gray-500/20 text-gray-400' },
  approved: { label: 'Zatwierdzony', color: 'bg-green-500/20 text-green-400' },
  in_development: { label: 'W realizacji', color: 'bg-blue-500/20 text-blue-400' },
  deployed: { label: 'Wdrożony', color: 'bg-emerald-500/20 text-emerald-400' },
  rejected: { label: 'Odrzucony', color: 'bg-red-500/20 text-red-400' },
};

function formatPLN(amount: number): string {
  return new Intl.NumberFormat('pl-PL', { style: 'currency', currency: 'PLN', maximumFractionDigits: 0 }).format(amount);
}

function AlignmentStars({ score }: { score: number }) {
  const full = Math.round(score);
  return (
    <span className="flex items-center gap-0.5">
      {Array.from({ length: 5 }, (_, i) => (
        <Star
          key={i}
          size={12}
          className={i < full ? 'fill-amber-400 text-amber-400' : 'text-[var(--border)]'}
        />
      ))}
    </span>
  );
}

export function TechSolutionCard({ solution, onStatusChange }: TechSolutionCardProps) {
  const [riskOpen, setRiskOpen] = useState(false);
  const typeConfig = TYPE_CONFIG[solution.solution_type];
  const statusConfig = STATUS_CONFIG[solution.status];

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-sm font-medium text-[var(--text)]">{solution.name}</h3>
        <div className="flex shrink-0 items-center gap-1.5">
          <span className={cn('rounded-full px-2 py-0.5 text-[10px] font-semibold', typeConfig.color)}>
            {typeConfig.label}
          </span>
          <span className={cn('rounded-full px-2 py-0.5 text-[10px] font-semibold', statusConfig.color)}>
            {statusConfig.label}
          </span>
        </div>
      </div>

      {/* Metrics */}
      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <div className="rounded-md bg-[var(--bg-hover)] px-2.5 py-1.5">
          <span className="text-[10px] text-[var(--text-secondary)]">ROI</span>
          <p className="text-sm font-medium text-[var(--text)]">{solution.roi_ratio.toFixed(1)}x</p>
        </div>
        <div className="rounded-md bg-[var(--bg-hover)] px-2.5 py-1.5">
          <span className="text-[10px] text-[var(--text-secondary)]">Dev (h)</span>
          <p className="text-sm font-medium text-[var(--text)]">{solution.estimated_dev_hours}</p>
        </div>
        <div className="rounded-md bg-[var(--bg-hover)] px-2.5 py-1.5">
          <span className="text-[10px] text-[var(--text-secondary)]">Oszczędności/rok</span>
          <p className="text-sm font-medium text-[var(--text)]">{formatPLN(solution.estimated_annual_savings_pln)}</p>
        </div>
        <div className="rounded-md bg-[var(--bg-hover)] px-2.5 py-1.5">
          <span className="text-[10px] text-[var(--text-secondary)]">Zwrot (mies.)</span>
          <p className="text-sm font-medium text-[var(--text)]">{solution.payback_months}</p>
        </div>
      </div>

      {/* Strategic alignment */}
      <div className="mt-3 flex items-center gap-2">
        <span className="text-[10px] text-[var(--text-secondary)]">Dopasowanie strategiczne</span>
        <AlignmentStars score={solution.strategic_alignment_score} />
      </div>

      {/* Risk notes (collapsible) */}
      {solution.risk_notes && (
        <div className="mt-3 border-t border-[var(--border)] pt-2">
          <button
            type="button"
            onClick={() => setRiskOpen(!riskOpen)}
            className="flex items-center gap-1 text-[10px] text-[var(--text-secondary)] transition-colors hover:text-[var(--text)]"
          >
            <AlertTriangle size={10} />
            Ryzyko
            {riskOpen ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
          </button>
          {riskOpen && (
            <p className="mt-1 text-xs leading-relaxed text-[var(--text-secondary)]">{solution.risk_notes}</p>
          )}
        </div>
      )}

      {/* Action buttons */}
      {onStatusChange && (
        <div className="mt-3 flex items-center gap-2 border-t border-[var(--border)] pt-3">
          <button
            type="button"
            onClick={() => onStatusChange(solution.id, 'approved')}
            className="flex items-center gap-1 rounded-md bg-green-500/10 px-3 py-1.5 text-xs font-medium text-green-400 transition-colors hover:bg-green-500/20"
          >
            <CheckCircle size={12} />
            Zatwierdź
          </button>
          <button
            type="button"
            onClick={() => onStatusChange(solution.id, 'rejected')}
            className="flex items-center gap-1 rounded-md bg-red-500/10 px-3 py-1.5 text-xs font-medium text-red-400 transition-colors hover:bg-red-500/20"
          >
            <XCircle size={12} />
            Odrzuć
          </button>
        </div>
      )}
    </div>
  );
}
