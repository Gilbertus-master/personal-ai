'use client';

import { X, FileText } from 'lucide-react';
import type { DocumentDetail, SourceType } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';

export interface DocumentDetailPanelProps {
  document: DocumentDetail | null;
  isLoading: boolean;
  onClose: () => void;
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

const CLASSIFICATION_BADGE: Record<string, { label: string; className: string }> = {
  public: { label: 'Publiczny', className: 'bg-emerald-500/20 text-emerald-400' },
  internal: { label: 'Wewnętrzny', className: 'bg-amber-500/20 text-amber-400' },
  confidential: { label: 'Poufny', className: 'bg-red-500/20 text-red-400' },
};

function formatDate(dateStr: string): string {
  try {
    return new Intl.DateTimeFormat('pl-PL', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(dateStr));
  } catch {
    return '\u2014';
  }
}

function Skeleton() {
  return (
    <div className="animate-pulse space-y-4 p-6">
      <div className="h-6 w-3/4 rounded bg-[var(--border)]" />
      <div className="flex gap-2">
        <div className="h-5 w-16 rounded bg-[var(--border)]" />
        <div className="h-5 w-20 rounded bg-[var(--border)]" />
      </div>
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="space-y-2">
          <div className="h-4 w-full rounded bg-[var(--border)]" />
          <div className="h-4 w-5/6 rounded bg-[var(--border)]" />
        </div>
      ))}
    </div>
  );
}

export function DocumentDetailPanel({ document: doc, isLoading, onClose }: DocumentDetailPanelProps) {
  return (
    <div
      className="flex h-full flex-col border-l overflow-hidden"
      style={{ borderColor: 'var(--border)', backgroundColor: 'var(--bg)' }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between border-b px-4 py-3"
        style={{ borderColor: 'var(--border)' }}
      >
        <span className="text-sm font-medium" style={{ color: 'var(--text)' }}>
          Szczegóły dokumentu
        </span>
        <button
          onClick={onClose}
          className="rounded-md p-1 transition-colors"
          style={{ color: 'var(--text-secondary)' }}
        >
          <X size={16} />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <Skeleton />
        ) : !doc ? (
          <div className="flex flex-col items-center justify-center gap-2 p-12 text-center">
            <FileText size={32} style={{ color: 'var(--text-secondary)', opacity: 0.4 }} />
            <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>
              Szczegóły dokumentu niedostępne
            </span>
          </div>
        ) : (
          <div className="space-y-5 p-4">
            {/* Title + badges */}
            <div>
              <h3 className="text-base font-semibold mb-2" style={{ color: 'var(--text)' }}>
                {doc.title}
              </h3>
              <div className="flex flex-wrap items-center gap-2">
                {(() => {
                  const srcBadge = SOURCE_BADGE[doc.source_type] ?? {
                    label: doc.source_type,
                    className: 'bg-gray-500/20 text-gray-400',
                  };
                  return (
                    <span className={cn('rounded-full px-2 py-0.5 text-[10px] font-medium', srcBadge.className)}>
                      {srcBadge.label}
                    </span>
                  );
                })()}
                {(() => {
                  const clsBadge = CLASSIFICATION_BADGE[doc.classification] ?? {
                    label: doc.classification,
                    className: 'bg-gray-500/20 text-gray-400',
                  };
                  return (
                    <span className={cn('rounded-full px-2 py-0.5 text-[10px] font-medium', clsBadge.className)}>
                      {clsBadge.label}
                    </span>
                  );
                })()}
                <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                  {formatDate(doc.created_at)}
                </span>
              </div>
            </div>

            {/* Chunks */}
            {doc.chunks.length > 0 && (
              <div>
                <p className="mb-2 text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--text-secondary)' }}>
                  Fragmenty ({doc.chunks.length})
                </p>
                <div className="space-y-2">
                  {doc.chunks
                    .sort((a, b) => a.position - b.position)
                    .map((chunk) => (
                      <div
                        key={chunk.id}
                        className="rounded-md border p-3"
                        style={{ borderColor: 'var(--border)', backgroundColor: 'var(--surface)' }}
                      >
                        <span
                          className="mb-1 inline-block text-[10px] font-medium"
                          style={{ color: 'var(--text-secondary)' }}
                        >
                          #{chunk.position}
                        </span>
                        <p
                          className="whitespace-pre-wrap text-xs leading-relaxed"
                          style={{ color: 'var(--text)' }}
                        >
                          {chunk.text}
                        </p>
                      </div>
                    ))}
                </div>
              </div>
            )}

            {/* Entities */}
            {doc.entities && (doc.entities as unknown[]).length > 0 && (
              <div>
                <p className="mb-2 text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--text-secondary)' }}>
                  Encje
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {(doc.entities as Array<{ name?: string; type?: string }>).map((entity, i) => (
                    <span
                      key={i}
                      className="rounded-full bg-[var(--accent)]/10 px-2 py-0.5 text-[10px] font-medium text-[var(--accent)]"
                    >
                      {entity.name ?? JSON.stringify(entity)}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Events */}
            {doc.events && (doc.events as unknown[]).length > 0 && (
              <div>
                <p className="mb-2 text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--text-secondary)' }}>
                  Zdarzenia
                </p>
                <div className="space-y-1.5">
                  {(doc.events as Array<{ event_type?: string; description?: string; event_date?: string }>).map(
                    (event, i) => (
                      <div
                        key={i}
                        className="flex items-start gap-2 text-xs"
                        style={{ color: 'var(--text-secondary)' }}
                      >
                        <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--accent)]" />
                        <span>
                          {event.event_type && (
                            <span className="font-medium" style={{ color: 'var(--text)' }}>
                              {event.event_type}:{' '}
                            </span>
                          )}
                          {event.description ?? JSON.stringify(event)}
                          {event.event_date && ` (${event.event_date})`}
                        </span>
                      </div>
                    ),
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
