'use client';

import { Loader2, Play } from 'lucide-react';

export interface DecisionIntelligenceProps {
  data: unknown;
  isLoading: boolean;
  months: number;
  onMonthsChange: (m: number) => void;
  onRunAnalysis: () => void;
  isRunning?: boolean;
}

const MONTH_OPTIONS = [3, 6, 12];

function Skeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className="h-24 rounded-lg"
          style={{ backgroundColor: 'var(--surface-hover)' }}
        />
      ))}
    </div>
  );
}

function renderData(data: unknown): React.ReactNode {
  if (!data) return null;

  if (typeof data === 'object' && data !== null) {
    const obj = data as Record<string, unknown>;

    // Try to render known sections
    const sections = Object.entries(obj).filter(([k]) => k !== 'meta');

    if (sections.length === 0) {
      return (
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
          Brak danych.
        </p>
      );
    }

    return (
      <div className="space-y-4">
        {sections.map(([key, value]) => (
          <div
            key={key}
            className="rounded-lg border p-4"
            style={{ backgroundColor: 'var(--surface)', borderColor: 'var(--border)' }}
          >
            <h4 className="mb-2 text-sm font-medium capitalize" style={{ color: 'var(--text)' }}>
              {key.replace(/_/g, ' ')}
            </h4>
            {typeof value === 'string' ? (
              <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                {value}
              </p>
            ) : (
              <pre
                className="overflow-x-auto text-xs"
                style={{ color: 'var(--text-secondary)' }}
              >
                {JSON.stringify(value, null, 2)}
              </pre>
            )}
          </div>
        ))}
      </div>
    );
  }

  return (
    <pre className="overflow-x-auto rounded-lg border p-4 text-xs" style={{ backgroundColor: 'var(--surface)', borderColor: 'var(--border)', color: 'var(--text-secondary)' }}>
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}

export function DecisionIntelligence({
  data,
  isLoading,
  months,
  onMonthsChange,
  onRunAnalysis,
  isRunning = false,
}: DecisionIntelligenceProps) {
  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex items-center gap-3">
        {/* Months selector */}
        <div className="flex rounded-md border" style={{ borderColor: 'var(--border)' }}>
          {MONTH_OPTIONS.map((m) => (
            <button
              key={m}
              onClick={() => onMonthsChange(m)}
              className="px-3 py-1 text-xs font-medium transition-colors first:rounded-l-md last:rounded-r-md"
              style={{
                backgroundColor: months === m ? 'var(--accent)' : 'var(--surface)',
                color: months === m ? '#fff' : 'var(--text-secondary)',
              }}
            >
              {m} mies.
            </button>
          ))}
        </div>

        <button
          onClick={onRunAnalysis}
          disabled={isRunning}
          className="inline-flex items-center gap-1.5 rounded-md px-3 py-1 text-xs font-medium transition-colors disabled:opacity-50"
          style={{ backgroundColor: 'var(--accent)', color: '#fff' }}
        >
          {isRunning ? (
            <Loader2 size={12} className="animate-spin" />
          ) : (
            <Play size={12} />
          )}
          Uruchom analize
        </button>
      </div>

      {/* Content */}
      {isLoading ? <Skeleton /> : renderData(data)}
    </div>
  );
}
