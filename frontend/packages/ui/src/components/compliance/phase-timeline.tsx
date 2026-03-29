'use client';

import type { MatterPhase } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';

export interface PhaseTimelineProps {
  currentPhase: MatterPhase;
}

const PHASES: { key: MatterPhase; label: string }[] = [
  { key: 'initiation', label: 'Inicjacja' },
  { key: 'research', label: 'Badanie' },
  { key: 'analysis', label: 'Analiza' },
  { key: 'planning', label: 'Planowanie' },
  { key: 'document_generation', label: 'Generowanie dok.' },
  { key: 'approval', label: 'Zatwierdzanie' },
  { key: 'training', label: 'Szkolenie' },
  { key: 'communication', label: 'Komunikacja' },
  { key: 'verification', label: 'Weryfikacja' },
  { key: 'monitoring', label: 'Monitoring' },
  { key: 'closed', label: 'Zamknięte' },
];

export function PhaseTimeline({ currentPhase }: PhaseTimelineProps) {
  const currentIdx = PHASES.findIndex((p) => p.key === currentPhase);

  return (
    <div className="overflow-x-auto">
      <div className="flex items-center gap-0 min-w-max px-2 py-3">
        {PHASES.map((phase, i) => {
          const isCompleted = i < currentIdx;
          const isCurrent = i === currentIdx;

          return (
            <div key={phase.key} className="flex items-center">
              {/* Step */}
              <div className="flex flex-col items-center gap-1.5">
                <div
                  className={cn(
                    'flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold transition-colors',
                    isCompleted && 'bg-green-500/20 text-green-400',
                    isCurrent && 'bg-[var(--accent)] text-white animate-pulse',
                    !isCompleted && !isCurrent && 'bg-[var(--surface)] text-[var(--text-secondary)]',
                  )}
                >
                  {isCompleted ? (
                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  ) : (
                    i + 1
                  )}
                </div>
                <span
                  className={cn(
                    'text-[10px] whitespace-nowrap',
                    isCurrent && 'font-bold text-[var(--text)]',
                    isCompleted && 'text-green-400',
                    !isCompleted && !isCurrent && 'text-[var(--text-secondary)]',
                  )}
                >
                  {phase.label}
                </span>
              </div>

              {/* Connector line */}
              {i < PHASES.length - 1 && (
                <div
                  className={cn(
                    'mx-1 h-0.5 w-6',
                    i < currentIdx ? 'bg-green-500/40' : 'bg-[var(--border)]',
                  )}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
