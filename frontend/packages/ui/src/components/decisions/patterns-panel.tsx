'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export interface PatternsPanelProps {
  insights: string | undefined;
  isLoading: boolean;
  meta?: { decision_count: number; areas: string[] };
}

function Skeleton() {
  return (
    <div className="space-y-3 animate-pulse">
      <div className="h-4 w-3/4 rounded" style={{ backgroundColor: 'var(--surface-hover)' }} />
      <div className="h-4 w-full rounded" style={{ backgroundColor: 'var(--surface-hover)' }} />
      <div className="h-4 w-5/6 rounded" style={{ backgroundColor: 'var(--surface-hover)' }} />
      <div className="h-4 w-2/3 rounded" style={{ backgroundColor: 'var(--surface-hover)' }} />
      <div className="h-4 w-full rounded" style={{ backgroundColor: 'var(--surface-hover)' }} />
    </div>
  );
}

export function PatternsPanel({ insights, isLoading, meta }: PatternsPanelProps) {
  if (isLoading) {
    return (
      <div className="rounded-lg border p-4" style={{ backgroundColor: 'var(--surface)', borderColor: 'var(--border)' }}>
        <Skeleton />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {meta && (
        <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
          Analiza {meta.decision_count} decyzji w {meta.areas.length} obszarach
        </p>
      )}

      {insights ? (
        <div
          className="prose prose-sm prose-invert max-w-none rounded-lg border p-4"
          style={{ backgroundColor: 'var(--surface)', borderColor: 'var(--border)', color: 'var(--text)' }}
        >
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{insights}</ReactMarkdown>
        </div>
      ) : (
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
          Brak danych do analizy wzorców.
        </p>
      )}
    </div>
  );
}
