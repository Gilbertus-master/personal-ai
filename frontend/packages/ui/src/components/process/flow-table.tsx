'use client';

import type { DataFlow } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';

export interface FlowTableProps {
  flows: DataFlow[];
}

const AUTOMATION_CONFIG: Record<DataFlow['automation'], { label: string; color: string }> = {
  manual: { label: 'Ręczna', color: 'bg-red-500/20 text-red-400' },
  semi_auto: { label: 'Częściowa', color: 'bg-amber-500/20 text-amber-400' },
  automated: { label: 'Automatyczna', color: 'bg-green-500/20 text-green-400' },
  gilbertus: { label: 'Gilbertus', color: 'bg-blue-500/20 text-blue-400' },
};

const BOTTLENECK_CONFIG: Record<DataFlow['bottleneck'], { label: string; color: string }> = {
  high: { label: 'Wysoki', color: 'bg-red-500/20 text-red-400' },
  medium: { label: 'Średni', color: 'bg-amber-500/20 text-amber-400' },
  low: { label: 'Niski', color: 'bg-green-500/20 text-green-400' },
};

const FREQUENCY_LABELS: Record<DataFlow['frequency'], string> = {
  daily: 'Codziennie',
  weekly: 'Co tydzień',
  monthly: 'Co miesiąc',
  occasional: 'Okazjonalnie',
};

function formatVolume(vol: number): string {
  if (vol >= 1_000_000) return `${(vol / 1_000_000).toFixed(1)}M`;
  if (vol >= 1_000) return `${(vol / 1_000).toFixed(1)}K`;
  return vol.toLocaleString('pl-PL');
}

export function FlowTable({ flows }: FlowTableProps) {
  if (flows.length === 0) {
    return (
      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 text-center text-sm text-[var(--text-secondary)]">
        Brak przepływów danych
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-[var(--border)] bg-[var(--surface)]">
            <th className="px-4 py-2.5 text-xs font-semibold uppercase text-[var(--text-secondary)]">Przepływ</th>
            <th className="px-4 py-2.5 text-xs font-semibold uppercase text-[var(--text-secondary)]">Źródło</th>
            <th className="px-4 py-2.5 text-xs font-semibold uppercase text-[var(--text-secondary)]">Kanał</th>
            <th className="px-4 py-2.5 text-xs font-semibold uppercase text-[var(--text-secondary)]">Częstotliwość</th>
            <th className="px-4 py-2.5 text-xs font-semibold uppercase text-[var(--text-secondary)]">Wolumen</th>
            <th className="px-4 py-2.5 text-xs font-semibold uppercase text-[var(--text-secondary)]">Automatyzacja</th>
            <th className="px-4 py-2.5 text-xs font-semibold uppercase text-[var(--text-secondary)]">Wąskie gardło</th>
          </tr>
        </thead>
        <tbody>
          {flows.map((flow, i) => {
            const automation = AUTOMATION_CONFIG[flow.automation];
            const bottleneck = BOTTLENECK_CONFIG[flow.bottleneck];

            return (
              <tr
                key={`${flow.flow}-${i}`}
                className="border-b border-[var(--border)] last:border-b-0 transition-colors hover:bg-[var(--surface-hover)]"
              >
                <td className="px-4 py-2.5 font-medium text-[var(--text)]">{flow.flow}</td>
                <td className="px-4 py-2.5 text-xs text-[var(--text-secondary)]">{flow.source}</td>
                <td className="px-4 py-2.5 text-xs text-[var(--text-secondary)]">{flow.channel}</td>
                <td className="px-4 py-2.5 text-xs text-[var(--text-secondary)]">
                  {FREQUENCY_LABELS[flow.frequency]}
                </td>
                <td className="px-4 py-2.5 text-xs font-medium text-[var(--text)]">
                  {formatVolume(flow.volume)}
                </td>
                <td className="px-4 py-2.5">
                  <span className={cn('rounded-full px-2 py-0.5 text-[10px] font-semibold', automation.color)}>
                    {automation.label}
                  </span>
                </td>
                <td className="px-4 py-2.5">
                  <span className={cn('rounded-full px-2 py-0.5 text-[10px] font-semibold', bottleneck.color)}>
                    {bottleneck.label}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
