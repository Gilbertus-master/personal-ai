'use client';

import { useState } from 'react';
import {
  AlertTriangle,
  MessageSquareOff,
  Clock,
  ChevronDown,
  ChevronRight,
  CheckCircle,
  Bell,
} from 'lucide-react';
import { cn } from '../../lib/utils';
import type { PredictiveAlerts as PredictiveAlertsType } from '@gilbertus/api-client';

interface PredictiveAlertsProps {
  data?: PredictiveAlertsType;
  isLoading?: boolean;
}

const RISK_BADGE: Record<string, string> = {
  high: 'bg-red-400/10 text-red-400',
  medium: 'bg-amber-400/10 text-amber-400',
  low: 'bg-blue-400/10 text-blue-400',
};

const RISK_LABEL: Record<string, string> = {
  high: 'Wysoki',
  medium: 'Średni',
  low: 'Niski',
};

function Section({
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

function EmptySection() {
  return (
    <div className="flex items-center gap-2 py-3 text-sm text-[var(--text-secondary)]">
      <CheckCircle className="h-4 w-4 text-emerald-400" />
      Brak alertów
    </div>
  );
}

export function PredictiveAlerts({ data, isLoading }: PredictiveAlertsProps) {
  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-10 rounded-lg bg-[var(--bg-hover)] animate-pulse" />
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-24 rounded-lg bg-[var(--bg-hover)] animate-pulse" />
        ))}
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="flex items-center gap-2">
        <Bell className="h-4 w-4 text-[var(--accent)]" />
        <span className="text-sm font-medium text-[var(--text)]">
          {data.total_alerts} {data.total_alerts === 1 ? 'alert' : 'alertów'}
        </span>
      </div>

      {/* 1. Escalation risks */}
      <Section
        title="Ryzyko eskalacji"
        icon={<AlertTriangle />}
        count={data.escalation_risks.length}
      >
        {data.escalation_risks.length === 0 ? (
          <EmptySection />
        ) : (
          <ul className="space-y-3">
            {data.escalation_risks.map((r, i) => (
              <li key={i} className="flex items-start gap-3">
                <span className={cn('shrink-0 mt-0.5 rounded-full px-2 py-0.5 text-xs font-medium', RISK_BADGE[r.risk])}>
                  {RISK_LABEL[r.risk]}
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-[var(--text)]">
                    {r.person_name}
                    <span className="ml-2 text-xs text-[var(--text-muted)]">
                      {Math.round(r.probability * 100)}%
                    </span>
                  </p>
                  {r.prediction && (
                    <p className="text-xs text-[var(--text-secondary)] mt-0.5">{r.prediction}</p>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Section>

      {/* 2. Communication gaps */}
      <Section
        title="Luki komunikacyjne"
        icon={<MessageSquareOff />}
        count={data.communication_gaps.length}
      >
        {data.communication_gaps.length === 0 ? (
          <EmptySection />
        ) : (
          <ul className="space-y-3">
            {data.communication_gaps.map((g, i) => (
              <li key={i} className="flex items-start gap-3">
                <div className="shrink-0 mt-0.5 h-8 w-8 rounded-full bg-amber-400/10 flex items-center justify-center text-xs font-bold text-amber-400">
                  {g.silence_days}d
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-[var(--text)]">
                    {g.person_name}
                    <span className="ml-2 text-xs text-[var(--text-muted)]">
                      zwykle {g.baseline_events_per_week.toFixed(1)}/tydz.
                    </span>
                  </p>
                  <p className="text-xs text-[var(--text-secondary)] mt-0.5">{g.prediction}</p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Section>

      {/* 3. Deadline risks */}
      <Section
        title="Ryzyko terminów"
        icon={<Clock />}
        count={data.deadline_risks.length}
      >
        {data.deadline_risks.length === 0 ? (
          <EmptySection />
        ) : (
          <ul className="space-y-3">
            {data.deadline_risks.map((d, i) => (
              <li key={i} className="flex items-start gap-3">
                <div
                  className={cn(
                    'shrink-0 mt-0.5 h-8 w-8 rounded-full flex items-center justify-center text-xs font-bold',
                    d.days_until_deadline < 3
                      ? 'bg-red-400/10 text-red-400'
                      : d.days_until_deadline < 7
                        ? 'bg-amber-400/10 text-amber-400'
                        : 'bg-blue-400/10 text-blue-400',
                  )}
                >
                  {d.days_until_deadline}d
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-[var(--text)]">{d.description}</p>
                  <p className="text-xs text-[var(--text-secondary)] mt-0.5">{d.prediction}</p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Section>
    </div>
  );
}
