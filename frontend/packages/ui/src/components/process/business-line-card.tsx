'use client';

import { Clock, Radio } from 'lucide-react';
import type { BusinessLine } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';

export interface BusinessLineCardProps {
  line: BusinessLine;
  onClick?: () => void;
}

const IMPORTANCE_CONFIG: Record<BusinessLine['importance'], { label: string; color: string }> = {
  critical: { label: 'Krytyczny', color: 'bg-red-500/20 text-red-400' },
  high: { label: 'Wysoki', color: 'bg-orange-500/20 text-orange-400' },
  medium: { label: 'Średni', color: 'bg-amber-500/20 text-amber-400' },
  low: { label: 'Niski', color: 'bg-gray-500/20 text-gray-400' },
};

const STATUS_CONFIG: Record<BusinessLine['status'], { label: string; color: string }> = {
  active: { label: 'Aktywny', color: 'bg-green-500/20 text-green-400' },
  archived: { label: 'Archiwalny', color: 'bg-gray-500/20 text-gray-400' },
  merged: { label: 'Scalony', color: 'bg-blue-500/20 text-blue-400' },
};

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('pl-PL', { day: 'numeric', month: 'short', year: 'numeric' });
}

export function BusinessLineCard({ line, onClick }: BusinessLineCardProps) {
  const importance = IMPORTANCE_CONFIG[line.importance];
  const status = STATUS_CONFIG[line.status];

  return (
    <div
      onClick={onClick}
      className={cn(
        'rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 transition-colors hover:bg-[var(--surface-hover)]',
        onClick && 'cursor-pointer hover:ring-1 hover:ring-[var(--accent)]',
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-bold text-[var(--text)]">{line.name}</h3>
          <p className="mt-1 text-xs leading-relaxed text-[var(--text-secondary)]">{line.description}</p>
        </div>
        <span className={cn('shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold', importance.color)}>
          {importance.label}
        </span>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-3 text-[10px] text-[var(--text-secondary)]">
        <span className="flex items-center gap-1">
          <Radio size={10} />
          {line.signals} {line.signals === 1 ? 'sygnał' : 'sygnałów'}
        </span>
        <span className={cn('rounded-full px-2 py-0.5 font-semibold', status.color)}>
          {status.label}
        </span>
        <span className="flex items-center gap-1">
          <Clock size={10} />
          {formatDate(line.discovered_at)}
        </span>
      </div>
    </div>
  );
}
