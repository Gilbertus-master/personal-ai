'use client';

import type { DiscoveredProcess } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';

export interface ProcessCardProps {
  process: DiscoveredProcess;
}

const TYPE_CONFIG: Record<DiscoveredProcess['process_type'], { label: string; color: string }> = {
  decision: { label: 'Decyzja', color: 'bg-blue-500/20 text-blue-400' },
  approval: { label: 'Zatwierdzenie', color: 'bg-purple-500/20 text-purple-400' },
  reporting: { label: 'Raportowanie', color: 'bg-cyan-500/20 text-cyan-400' },
  trading: { label: 'Trading', color: 'bg-green-500/20 text-green-400' },
  compliance: { label: 'Compliance', color: 'bg-orange-500/20 text-orange-400' },
  communication: { label: 'Komunikacja', color: 'bg-teal-500/20 text-teal-400' },
  operational: { label: 'Operacyjny', color: 'bg-amber-500/20 text-amber-400' },
};

const FREQUENCY_CONFIG: Record<DiscoveredProcess['frequency'], string> = {
  daily: 'Codziennie',
  weekly: 'Co tydzień',
  monthly: 'Co miesiąc',
  quarterly: 'Kwartalnie',
  ad_hoc: 'Ad hoc',
};

const STATUS_CONFIG: Record<DiscoveredProcess['status'], { label: string; color: string }> = {
  discovered: { label: 'Odkryty', color: 'bg-blue-500/20 text-blue-400' },
  confirmed: { label: 'Potwierdzony', color: 'bg-green-500/20 text-green-400' },
  automated: { label: 'Zautomatyzowany', color: 'bg-emerald-500/20 text-emerald-400' },
  archived: { label: 'Archiwalny', color: 'bg-gray-500/20 text-gray-400' },
};

function automationColor(pct: number): string {
  if (pct >= 70) return 'bg-green-500';
  if (pct >= 40) return 'bg-amber-500';
  return 'bg-red-500';
}

export function ProcessCard({ process }: ProcessCardProps) {
  const typeConfig = TYPE_CONFIG[process.process_type];
  const status = STATUS_CONFIG[process.status];
  const pct = Math.round(process.automation_potential);

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 transition-colors hover:bg-[var(--surface-hover)]">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-medium text-[var(--text)]">{process.name}</h3>
          <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-[var(--text-secondary)]">
            {process.description}
          </p>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className={cn('rounded-full px-2 py-0.5 text-[10px] font-semibold', typeConfig.color)}>
          {typeConfig.label}
        </span>
        <span className="rounded-full bg-[var(--bg-hover)] px-2 py-0.5 text-[10px] text-[var(--text-secondary)]">
          {FREQUENCY_CONFIG[process.frequency]}
        </span>
        <span className={cn('rounded-full px-2 py-0.5 text-[10px] font-semibold', status.color)}>
          {status.label}
        </span>
      </div>

      {/* Automation potential bar */}
      <div className="mt-3 flex items-center gap-2">
        <span className="text-[10px] text-[var(--text-secondary)]">Automatyzacja</span>
        <div className="h-1.5 flex-1 rounded-full bg-[var(--border)]">
          <div
            className={cn('h-full rounded-full transition-all', automationColor(pct))}
            style={{ width: `${pct}%` }}
          />
        </div>
        <span className="text-[10px] font-medium text-[var(--text-secondary)]">{pct}%</span>
      </div>
    </div>
  );
}
