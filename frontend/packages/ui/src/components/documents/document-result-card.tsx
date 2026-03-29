'use client';

import type { DocumentSource, DocumentSearchMatch, SourceType } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';

export interface DocumentResultCardProps {
  source: DocumentSource;
  match: DocumentSearchMatch;
  onClick?: (documentId: number) => void;
}

const SOURCE_BADGE: Record<SourceType, { label: string; className: string }> = {
  email: { label: 'Email', className: 'bg-blue-500/20 text-blue-400' },
  teams: { label: 'Teams', className: 'bg-violet-500/20 text-violet-400' },
  whatsapp: { label: 'WhatsApp', className: 'bg-emerald-500/20 text-emerald-400' },
  document: { label: 'Dokument', className: 'bg-amber-500/20 text-amber-400' },
  pdf: { label: 'PDF', className: 'bg-red-500/20 text-red-400' },
  plaud: { label: 'Plaud', className: 'bg-pink-500/20 text-pink-400' },
  chatgpt: { label: 'ChatGPT', className: 'bg-teal-500/20 text-teal-400' },
  calendar: { label: 'Kalendarz', className: 'bg-orange-500/20 text-orange-400' },
};

function formatDate(dateStr: string): string {
  try {
    return new Intl.DateTimeFormat('pl-PL', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    }).format(new Date(dateStr));
  } catch {
    return '\u2014';
  }
}

export function DocumentResultCard({ source, match, onClick }: DocumentResultCardProps) {
  const badge = SOURCE_BADGE[source.source_type] ?? {
    label: source.source_type,
    className: 'bg-gray-500/20 text-gray-400',
  };
  const scorePercent = Math.round(match.score * 100);

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onClick?.(source.document_id)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') onClick?.(source.document_id);
      }}
      className="cursor-pointer rounded-lg border p-4 transition-colors hover:bg-[var(--surface-hover)]"
      style={{ borderColor: 'var(--border)', backgroundColor: 'var(--surface)' }}
    >
      {/* Header */}
      <div className="mb-2 flex items-center gap-2">
        <span className="flex-1 truncate text-sm font-semibold" style={{ color: 'var(--text)' }}>
          {source.title}
        </span>
        <span className={cn('rounded-full px-2 py-0.5 text-[10px] font-medium', badge.className)}>
          {badge.label}
        </span>
      </div>

      {/* Score bar */}
      <div className="mb-2 flex items-center gap-2">
        <div
          className="h-1.5 flex-1 rounded-full"
          style={{ backgroundColor: 'var(--border)' }}
        >
          <div
            className="h-full rounded-full bg-[var(--accent)] transition-all"
            style={{ width: `${scorePercent}%` }}
          />
        </div>
        <span className="text-[10px]" style={{ color: 'var(--text-secondary)' }}>
          {scorePercent}%
        </span>
      </div>

      {/* Snippet */}
      <p
        className="mb-2 line-clamp-3 text-xs leading-relaxed"
        style={{ color: 'var(--text-secondary)' }}
      >
        {match.text}
      </p>

      {/* Date */}
      <span className="text-[10px]" style={{ color: 'var(--text-secondary)' }}>
        {formatDate(source.created_at)}
      </span>
    </div>
  );
}
