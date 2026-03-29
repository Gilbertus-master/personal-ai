'use client';

import { useState } from 'react';
import { ChevronDown, ChevronRight, Repeat, AlertTriangle, Calendar, Zap } from 'lucide-react';
import { cn } from '../../lib/utils';
import { KpiCard } from '../dashboard/kpi-card';
import type { InefficiencyReport as InefficiencyReportType } from '@gilbertus/api-client';

interface InefficiencyReportProps {
  data?: InefficiencyReportType;
  isLoading?: boolean;
}

function CollapsibleSection({
  title,
  icon,
  count,
  defaultOpen = true,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  count: number;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)]">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-[var(--surface-hover)] transition-colors"
      >
        {open ? (
          <ChevronDown className="h-4 w-4 text-[var(--text-secondary)] shrink-0" />
        ) : (
          <ChevronRight className="h-4 w-4 text-[var(--text-secondary)] shrink-0" />
        )}
        <span className="text-[var(--text-muted)] [&>svg]:h-4 [&>svg]:w-4">{icon}</span>
        <span className="text-sm font-medium text-[var(--text)]">{title}</span>
        <span className="rounded-full bg-[var(--accent)]/10 px-2 py-0.5 text-xs font-medium text-[var(--accent)]">
          {count}
        </span>
      </button>
      {open && <div className="px-4 pb-4">{children}</div>}
    </div>
  );
}

const AUTOMATION_BADGE = {
  high: 'bg-emerald-400/10 text-emerald-400',
  medium: 'bg-amber-400/10 text-amber-400',
} as const;

function formatPln(value: number): string {
  return new Intl.NumberFormat('pl-PL', { maximumFractionDigits: 0 }).format(value);
}

export function InefficiencyReport({ data, isLoading }: InefficiencyReportProps) {
  if (isLoading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-24 rounded-lg bg-[var(--bg-hover)] animate-pulse" />
        ))}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-20 rounded-lg bg-[var(--bg-hover)] animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="space-y-4">
      {/* Repeating tasks */}
      <CollapsibleSection
        title="Powtarzajace sie zadania"
        icon={<Repeat />}
        count={data.repeating_tasks.length}
      >
        {data.repeating_tasks.length === 0 ? (
          <p className="text-sm text-[var(--text-secondary)]">Brak wykrytych wzorcow</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)]">
                  <th className="pb-2 text-left font-medium text-[var(--text-secondary)]">Typ</th>
                  <th className="pb-2 text-left font-medium text-[var(--text-secondary)]">Wzorzec</th>
                  <th className="pb-2 text-right font-medium text-[var(--text-secondary)]">Tygodnie</th>
                  <th className="pb-2 text-right font-medium text-[var(--text-secondary)]">Godz./mies.</th>
                  <th className="pb-2 text-left font-medium text-[var(--text-secondary)]">Automatyzacja</th>
                </tr>
              </thead>
              <tbody>
                {data.repeating_tasks.map((task, i) => (
                  <tr key={i} className="border-b border-[var(--border)] last:border-b-0">
                    <td className="py-2 text-[var(--text)]">{task.type}</td>
                    <td className="py-2 text-[var(--text)] max-w-xs truncate">{task.pattern}</td>
                    <td className="py-2 text-right text-[var(--text)]">{task.weeks_seen}</td>
                    <td className="py-2 text-right text-[var(--text)]">{task.est_hours_per_month.toFixed(1)}</td>
                    <td className="py-2">
                      <span
                        className={cn(
                          'rounded-full px-2 py-0.5 text-xs font-medium',
                          AUTOMATION_BADGE[task.automation_potential],
                        )}
                      >
                        {task.automation_potential}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CollapsibleSection>

      {/* Escalation bottlenecks */}
      <CollapsibleSection
        title="Waskie gardla eskalacji"
        icon={<AlertTriangle />}
        count={data.escalation_bottlenecks.length}
      >
        {data.escalation_bottlenecks.length === 0 ? (
          <p className="text-sm text-[var(--text-secondary)]">Brak wykrytych waskich gardel</p>
        ) : (
          <ul className="space-y-3">
            {data.escalation_bottlenecks.map((b, i) => (
              <li key={i} className="flex items-start gap-3">
                <div className="shrink-0 mt-0.5 h-8 w-8 rounded-full bg-[var(--surface-hover)] flex items-center justify-center text-xs font-bold text-[var(--text)]">
                  {b.escalations}
                </div>
                <div>
                  <p className="text-sm font-medium text-[var(--text)]">{b.person}</p>
                  <p className="text-xs text-[var(--text-secondary)]">{b.interpretation}</p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CollapsibleSection>

      {/* Meeting overload */}
      <CollapsibleSection
        title="Przeciazenie spotkaniami"
        icon={<Calendar />}
        count={data.meeting_overload.length}
      >
        {data.meeting_overload.length === 0 ? (
          <p className="text-sm text-[var(--text-secondary)]">Brak przeciazonych dni</p>
        ) : (
          <ul className="space-y-3">
            {data.meeting_overload.map((m, i) => (
              <li key={i} className="flex items-start gap-3">
                <div className="shrink-0 mt-0.5 h-8 w-8 rounded-full bg-amber-400/10 flex items-center justify-center text-xs font-bold text-amber-400">
                  {m.meetings}
                </div>
                <div>
                  <p className="text-sm font-medium text-[var(--text)]">
                    {m.person} <span className="text-[var(--text-secondary)] font-normal">— {m.date}</span>
                  </p>
                  <p className="text-xs text-[var(--text-secondary)]">{m.interpretation}</p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CollapsibleSection>

      {/* Summary KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard
          label="Wzorce powtarzalne"
          value={data.summary.repeating_patterns}
          icon={<Repeat />}
        />
        <KpiCard
          label="Osoby-waskie gardla"
          value={data.summary.bottleneck_people}
          icon={<AlertTriangle />}
          color={data.summary.bottleneck_people > 3 ? 'danger' : 'default'}
        />
        <KpiCard
          label="Przeciazone dni"
          value={data.summary.overloaded_days}
          icon={<Calendar />}
          color={data.summary.overloaded_days > 5 ? 'warning' : 'default'}
        />
        <KpiCard
          label="Oszczednosci automatyzacji"
          value={`${formatPln(data.summary.est_automation_savings_pln)} zl`}
          icon={<Zap />}
          color="success"
        />
      </div>
    </div>
  );
}
