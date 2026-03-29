'use client';

import { Signal } from 'lucide-react';
import type { SwotAnalysis } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';

interface SwotCardProps {
  analysis: SwotAnalysis;
}

const QUADRANTS = [
  { key: 'strengths' as const, label: 'Mocne strony', color: 'border-green-500/30', heading: 'text-green-400', bg: 'bg-green-500/5' },
  { key: 'weaknesses' as const, label: 'Słabe strony', color: 'border-red-500/30', heading: 'text-red-400', bg: 'bg-red-500/5' },
  { key: 'opportunities' as const, label: 'Szanse', color: 'border-blue-500/30', heading: 'text-blue-400', bg: 'bg-blue-500/5' },
  { key: 'threats' as const, label: 'Zagrożenia', color: 'border-amber-500/30', heading: 'text-amber-400', bg: 'bg-amber-500/5' },
] as const;

export function SwotCard({ analysis }: SwotCardProps) {
  return (
    <div className="space-y-4">
      {/* 2x2 grid */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {QUADRANTS.map((q) => {
          const items = analysis.swot[q.key];
          return (
            <div
              key={q.key}
              className={cn('rounded-lg border p-3', q.color, q.bg)}
            >
              <h4 className={cn('mb-2 text-xs font-semibold uppercase', q.heading)}>
                {q.label}
              </h4>
              {items.length > 0 ? (
                <ul className="space-y-1">
                  {items.map((item, idx) => (
                    <li key={idx} className="flex items-start gap-1.5 text-xs text-[var(--text)]">
                      <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-current opacity-40" />
                      {item}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs italic text-[var(--text-secondary)]">Brak danych</p>
              )}
            </div>
          );
        })}
      </div>

      {/* Summary */}
      {analysis.swot.summary && (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3">
          <p className="text-xs leading-relaxed text-[var(--text-secondary)]">{analysis.swot.summary}</p>
        </div>
      )}

      {/* Signals count */}
      <div className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)]">
        <Signal size={12} />
        <span>{analysis.signals_count} sygnałów</span>
      </div>
    </div>
  );
}
