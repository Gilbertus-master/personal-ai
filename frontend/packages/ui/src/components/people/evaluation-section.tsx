'use client';

import { useState } from 'react';
import { Star, Loader2, AlertTriangle } from 'lucide-react';
import { MarkdownRenderer } from '../chat/markdown-renderer';

interface EvaluationSectionProps {
  personSlug: string;
  onEvaluate: (dateFrom?: string, dateTo?: string) => void;
  result?: { evaluation: string; latency_ms: number } | null;
  isEvaluating?: boolean;
}

function defaultDateFrom(): string {
  const d = new Date();
  d.setMonth(d.getMonth() - 3);
  return d.toISOString().slice(0, 10);
}

function defaultDateTo(): string {
  return new Date().toISOString().slice(0, 10);
}

export function EvaluationSection({
  onEvaluate,
  result,
  isEvaluating = false,
}: EvaluationSectionProps) {
  const [dateFrom, setDateFrom] = useState(defaultDateFrom);
  const [dateTo, setDateTo] = useState(defaultDateTo);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        <Star size={18} style={{ color: 'var(--accent)' }} />
        <h3 className="text-lg font-semibold" style={{ color: 'var(--text)' }}>
          Ocena AI
        </h3>
      </div>

      {/* Date range + button */}
      <div className="flex flex-wrap items-end gap-3">
        <label className="space-y-1">
          <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
            Od
          </span>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="block rounded-md border px-3 py-1.5 text-sm"
            style={{
              backgroundColor: 'var(--surface)',
              borderColor: 'var(--border)',
              color: 'var(--text)',
            }}
          />
        </label>
        <label className="space-y-1">
          <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
            Do
          </span>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="block rounded-md border px-3 py-1.5 text-sm"
            style={{
              backgroundColor: 'var(--surface)',
              borderColor: 'var(--border)',
              color: 'var(--text)',
            }}
          />
        </label>
        <button
          onClick={() => onEvaluate(dateFrom || undefined, dateTo || undefined)}
          disabled={isEvaluating}
          className="flex items-center gap-2 rounded-md px-4 py-1.5 text-sm font-medium transition-colors disabled:opacity-50"
          style={{
            backgroundColor: 'var(--accent)',
            color: '#fff',
          }}
        >
          {isEvaluating ? (
            <>
              <Loader2 size={14} className="animate-spin" />
              Oceniam...
            </>
          ) : (
            'Oceń'
          )}
        </button>
      </div>

      {/* Warning */}
      <div
        className="flex items-start gap-2 rounded-md px-3 py-2 text-xs"
        style={{
          backgroundColor: 'rgba(234, 179, 8, 0.1)',
          color: '#eab308',
          border: '1px solid rgba(234, 179, 8, 0.2)',
        }}
      >
        <AlertTriangle size={14} className="mt-0.5 flex-shrink-0" />
        <span>Ocena jest generowana przez AI i wymaga weryfikacji</span>
      </div>

      {/* Result */}
      {result && (
        <div
          className="rounded-lg p-4"
          style={{ backgroundColor: 'var(--surface)', border: '1px solid var(--border)' }}
        >
          <MarkdownRenderer content={result.evaluation} />
          <p className="mt-3 text-xs" style={{ color: 'var(--text-muted)' }}>
            Wygenerowano w {(result.latency_ms / 1000).toFixed(1)}s
          </p>
        </div>
      )}
    </div>
  );
}
