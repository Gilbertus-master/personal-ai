'use client';

import { useMemo } from 'react';
import { FileText } from 'lucide-react';
import type { ComplianceDocument } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';
import { ComplianceBadge } from './compliance-badge';
import { AreaFilter } from './area-filter';

export interface DocumentsTableProps {
  documents: ComplianceDocument[];
  staleDocuments?: ComplianceDocument[];
  isLoading?: boolean;
  showStaleOnly: boolean;
  areaFilter: string | null;
  docTypeFilter: string | null;
  statusFilter: string | null;
  onAreaChange: (v: string | null) => void;
  onDocTypeChange: (v: string | null) => void;
  onStatusChange: (v: string | null) => void;
  onStaleToggle: (v: boolean) => void;
  renderActions?: (doc: ComplianceDocument) => React.ReactNode;
}

const COLUMNS = ['Tytuł', 'Typ', 'Obszar', 'Status', 'Podpis', 'Okres ważności', 'Przegląd', ''] as const;

const DOC_TYPE_OPTIONS: { value: string | null; label: string }[] = [
  { value: null, label: 'Wszystkie typy' },
  { value: 'policy', label: 'Polityka' },
  { value: 'procedure', label: 'Procedura' },
  { value: 'form', label: 'Formularz' },
  { value: 'template', label: 'Szablon' },
  { value: 'register', label: 'Rejestr' },
  { value: 'report', label: 'Raport' },
  { value: 'certificate', label: 'Certyfikat' },
  { value: 'license', label: 'Licencja' },
  { value: 'contract_annex', label: 'Aneks umowy' },
  { value: 'training_material', label: 'Materiał szkoleniowy' },
  { value: 'communication', label: 'Komunikacja' },
  { value: 'regulation_text', label: 'Tekst regulacji' },
  { value: 'internal_regulation', label: 'Regulacja wewnętrzna' },
  { value: 'risk_assessment', label: 'Ocena ryzyka' },
  { value: 'audit_report', label: 'Raport audytu' },
  { value: 'other', label: 'Inne' },
];

const STATUS_FILTERS = [
  { value: null, label: 'Wszystkie' },
  { value: 'draft', label: 'Szkic' },
  { value: 'review', label: 'Przegląd' },
  { value: 'approved', label: 'Zatwierdzony' },
  { value: 'active', label: 'Aktywny' },
  { value: 'superseded', label: 'Zastąpiony' },
  { value: 'expired', label: 'Wygasły' },
  { value: 'archived', label: 'Zarchiwizowany' },
] as const;

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '\u2014';
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

function isExpired(dateStr: string | null | undefined): boolean {
  if (!dateStr) return false;
  try {
    return new Date(dateStr).getTime() < Date.now();
  } catch {
    return false;
  }
}

function SkeletonRows() {
  return (
    <>
      {Array.from({ length: 6 }).map((_, i) => (
        <tr key={i} className="border-b border-[var(--border)]">
          {Array.from({ length: COLUMNS.length }).map((_, j) => (
            <td key={j} className="px-4 py-3">
              <div
                className="h-4 rounded bg-[var(--surface)] animate-pulse"
                style={{ width: `${50 + j * 7}%` }}
              />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}

export function DocumentsTable({
  documents,
  staleDocuments,
  isLoading,
  showStaleOnly,
  areaFilter,
  docTypeFilter,
  statusFilter,
  onAreaChange,
  onDocTypeChange,
  onStatusChange,
  onStaleToggle,
  renderActions,
}: DocumentsTableProps) {
  const data = useMemo(
    () => (showStaleOnly ? (staleDocuments ?? []) : (documents ?? [])),
    [documents, staleDocuments, showStaleOnly],
  );

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Status chips */}
        <div className="flex items-center gap-1.5">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f.label}
              onClick={() => onStatusChange(f.value)}
              className={cn(
                'rounded-full px-3 py-1 text-xs font-medium transition-colors',
                statusFilter === f.value
                  ? 'bg-[var(--accent)] text-white'
                  : 'bg-[var(--surface)] text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]',
              )}
            >
              {f.label}
            </button>
          ))}
        </div>

        {/* Doc type select */}
        <select
          value={docTypeFilter ?? ''}
          onChange={(e) => onDocTypeChange(e.target.value || null)}
          className="rounded-md border px-3 py-1 text-xs"
          style={{
            backgroundColor: 'var(--surface)',
            borderColor: 'var(--border)',
            color: 'var(--text)',
          }}
        >
          {DOC_TYPE_OPTIONS.map((o) => (
            <option key={o.label} value={o.value ?? ''}>
              {o.label}
            </option>
          ))}
        </select>

        {/* Area select */}
        <AreaFilter value={areaFilter} onChange={onAreaChange} className="w-48" />

        {/* Stale toggle */}
        <button
          onClick={() => onStaleToggle(!showStaleOnly)}
          className={cn(
            'rounded-full px-3 py-1 text-xs font-medium transition-colors',
            showStaleOnly
              ? 'bg-orange-500/20 text-orange-400'
              : 'bg-[var(--surface)] text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]',
          )}
        >
          Tylko przeterminowane
        </button>
      </div>

      {/* Table */}
      <div className="border border-[var(--border)] rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] bg-[var(--surface)]">
              {COLUMNS.map((col) => (
                <th
                  key={col}
                  className="px-4 py-3 text-left text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <SkeletonRows />
            ) : data.length === 0 ? (
              <tr>
                <td colSpan={COLUMNS.length} className="px-4 py-16 text-center">
                  <div className="flex flex-col items-center gap-2 text-[var(--text-secondary)]">
                    <FileText className="h-10 w-10 opacity-40" />
                    <span className="text-sm">Brak dokumentów do wyświetlenia</span>
                  </div>
                </td>
              </tr>
            ) : (
              data.map((doc) => (
                <tr
                  key={doc.id}
                  className="border-b border-[var(--border)] hover:bg-[var(--surface-hover)] transition-colors"
                >
                  <td className="px-4 py-3 font-medium text-[var(--text)] max-w-[260px] truncate">
                    {doc.title}
                    <span className="ml-1 text-xs text-[var(--text-secondary)]">v{doc.version}</span>
                  </td>
                  <td className="px-4 py-3 text-xs text-[var(--text-secondary)]">
                    {DOC_TYPE_OPTIONS.find((o) => o.value === doc.doc_type)?.label ?? doc.doc_type}
                  </td>
                  <td className="px-4 py-3">
                    <ComplianceBadge type="area" value={doc.area_code} />
                  </td>
                  <td className="px-4 py-3">
                    <ComplianceBadge type="doc_status" value={doc.status} />
                  </td>
                  <td className="px-4 py-3">
                    <ComplianceBadge type="signature" value={doc.signature_status} />
                  </td>
                  <td className="px-4 py-3 text-xs">
                    <span style={{ color: isExpired(doc.valid_until) ? '#ef4444' : 'var(--text-secondary)' }}>
                      {formatDate(doc.valid_from)} &rarr; {formatDate(doc.valid_until)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs" style={{ color: isExpired(doc.review_due) ? '#ef4444' : 'var(--text-secondary)' }}>
                    {formatDate(doc.review_due)}
                  </td>
                  <td className="px-4 py-3">
                    {renderActions?.(doc)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
