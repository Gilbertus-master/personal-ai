'use client';

import { useState, useMemo } from 'react';
import { FileText, ChevronUp, ChevronDown } from 'lucide-react';
import type { DocumentListItem, SourceType } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';

export interface DocumentsTableProps {
  documents: DocumentListItem[];
  onRowClick?: (id: number) => void;
  isLoading?: boolean;
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

type SortKey = 'title' | 'source_type' | 'classification' | 'created_at' | 'chunk_count';
type SortDir = 'asc' | 'desc';

const COLUMNS: { key: SortKey; label: string }[] = [
  { key: 'title', label: 'Tytuł' },
  { key: 'source_type', label: 'Typ źródła' },
  { key: 'classification', label: 'Klasyfikacja' },
  { key: 'created_at', label: 'Data' },
  { key: 'chunk_count', label: 'Chunki' },
];

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

function SkeletonRows() {
  return (
    <>
      {Array.from({ length: 6 }).map((_, i) => (
        <tr key={i} className="border-b border-[var(--border)]">
          {COLUMNS.map((_, j) => (
            <td key={j} className="px-4 py-3">
              <div
                className="h-4 rounded bg-[var(--surface)] animate-pulse"
                style={{ width: `${50 + j * 8}%` }}
              />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}

export function DocumentsTable({ documents, onRowClick, isLoading }: DocumentsTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('created_at');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  };

  const sorted = useMemo(() => {
    const list = [...documents];
    list.sort((a, b) => {
      const av = a[sortKey] ?? '';
      const bv = b[sortKey] ?? '';
      const cmp = typeof av === 'number' && typeof bv === 'number' ? av - bv : String(av).localeCompare(String(bv), 'pl-PL');
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return list;
  }, [documents, sortKey, sortDir]);

  return (
    <div className="border border-[var(--border)] rounded-lg overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--border)] bg-[var(--surface)]">
            {COLUMNS.map((col) => (
              <th
                key={col.key}
                onClick={() => handleSort(col.key)}
                className="cursor-pointer select-none px-4 py-3 text-left text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider"
              >
                <span className="inline-flex items-center gap-1">
                  {col.label}
                  {sortKey === col.key && (
                    sortDir === 'asc' ? <ChevronUp size={12} /> : <ChevronDown size={12} />
                  )}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {isLoading ? (
            <SkeletonRows />
          ) : sorted.length === 0 ? (
            <tr>
              <td colSpan={COLUMNS.length} className="px-4 py-16 text-center">
                <div className="flex flex-col items-center gap-2 text-[var(--text-secondary)]">
                  <FileText className="h-10 w-10 opacity-40" />
                  <span className="text-sm">Brak dokumentów</span>
                  <span className="text-xs opacity-60">Zmień filtry lub wgraj nowy dokument</span>
                </div>
              </td>
            </tr>
          ) : (
            sorted.map((doc) => {
              const srcBadge = SOURCE_BADGE[doc.source_type] ?? {
                label: doc.source_type,
                className: 'bg-gray-500/20 text-gray-400',
              };
              const clsBadge = CLASSIFICATION_BADGE[doc.classification] ?? {
                label: doc.classification,
                className: 'bg-gray-500/20 text-gray-400',
              };
              return (
                <tr
                  key={doc.id}
                  onClick={() => onRowClick?.(doc.id)}
                  className={cn(
                    'border-b border-[var(--border)] transition-colors',
                    onRowClick && 'cursor-pointer hover:bg-[var(--surface-hover)]',
                  )}
                >
                  <td className="px-4 py-3 font-medium text-[var(--text)] max-w-[300px] truncate">
                    {doc.title}
                  </td>
                  <td className="px-4 py-3">
                    <span className={cn('rounded-full px-2 py-0.5 text-[10px] font-medium', srcBadge.className)}>
                      {srcBadge.label}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={cn('rounded-full px-2 py-0.5 text-[10px] font-medium', clsBadge.className)}>
                      {clsBadge.label}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-[var(--text-secondary)]">
                    {formatDate(doc.created_at)}
                  </td>
                  <td className="px-4 py-3 text-[var(--text-secondary)]">
                    {doc.chunk_count ?? '\u2014'}
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
