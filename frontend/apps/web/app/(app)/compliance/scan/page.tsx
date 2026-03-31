'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Loader2, Radar } from 'lucide-react';
import { RbacGate } from '@gilbertus/ui';
import { ComplianceBadge } from '@gilbertus/ui/compliance';
import { useScanRegulatory } from '@/lib/hooks/use-compliance';
import type { ScanResult } from '@gilbertus/api-client';
import { cn } from '@gilbertus/ui';

const HOURS_OPTIONS = [6, 12, 24, 48, 72] as const;

export default function ScanPage() {
  const [hours, setHours] = useState<number>(24);
  const [results, setResults] = useState<ScanResult | null>(null);
  const scan = useScanRegulatory();

  function handleScan() {
    scan.mutate(hours, {
      onSuccess: (data) => setResults(data),
    });
  }

  return (
    <RbacGate roles={['owner', 'ceo', 'board', 'gilbertus_admin']}>
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-[var(--text)]">Skan regulacyjny</h1>

        {/* Controls */}
        <div className="flex flex-wrap items-center gap-4">
          {/* Hours selector */}
          <div className="flex items-center gap-1.5">
            {HOURS_OPTIONS.map((h) => (
              <button
                key={h}
                onClick={() => setHours(h)}
                className={cn(
                  'rounded-full px-3 py-1.5 text-sm font-medium transition-colors',
                  hours === h
                    ? 'bg-[var(--accent)] text-white'
                    : 'bg-[var(--surface)] text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]',
                )}
              >
                {h}h
              </button>
            ))}
          </div>

          {/* Scan button */}
          <button
            onClick={handleScan}
            disabled={scan.isPending}
            className={cn(
              'flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium text-white transition-colors',
              scan.isPending ? 'opacity-60 cursor-not-allowed' : 'hover:opacity-90',
            )}
            style={{ backgroundColor: 'var(--accent)' }}
          >
            {scan.isPending ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                Skanuję...
              </>
            ) : (
              <>
                <Radar size={16} />
                Skanuj ({hours}h)
              </>
            )}
          </button>
        </div>

        {/* Results */}
        {results && (
          <div className="space-y-4">
            {/* Summary cards */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
                <p className="text-xs text-[var(--text-secondary)] uppercase tracking-wider">
                  Przeskanowane chunki
                </p>
                <p className="text-2xl font-bold text-[var(--text)] mt-1">
                  {results.scanned_chunks}
                </p>
              </div>
              <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
                <p className="text-xs text-[var(--text-secondary)] uppercase tracking-wider">
                  Znalezione regulacje
                </p>
                <p className="text-2xl font-bold text-[var(--text)] mt-1">
                  {results.regulatory_found}
                </p>
              </div>
              <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
                <p className="text-xs text-[var(--text-secondary)] uppercase tracking-wider">
                  Utworzone sprawy
                </p>
                <p className="text-2xl font-bold text-[var(--text)] mt-1">
                  {results.matters_created}
                </p>
              </div>
            </div>

            {/* Details list */}
            {results.details.length > 0 && (
              <div className="space-y-2">
                <h3 className="text-sm font-semibold text-[var(--text)]">Szczegóły</h3>
                <div className="space-y-2">
                  {results.details.map((item, i) => (
                    <div
                      key={i}
                      className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4"
                    >
                      <div className="flex flex-wrap items-center gap-2 mb-2">
                        <span className="text-sm font-medium text-[var(--text)]">{item.title}</span>
                        <ComplianceBadge type="area" value={item.area_code} />
                        <ComplianceBadge type="matter_type" value={item.matter_type} />
                        <ComplianceBadge type="priority" value={item.priority} />
                      </div>
                      <p className="text-xs text-[var(--text-secondary)] mb-2">{item.action}</p>
                      <Link
                        href={`/compliance/matters/${item.matter_id}`}
                        className="text-xs text-blue-400 hover:underline"
                      >
                        Otwórz sprawę #{item.matter_id}
                      </Link>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* No results yet */}
        {!results && !scan.isPending && (
          <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-12 text-center text-[var(--text-secondary)]">
            <Radar className="h-10 w-10 opacity-40 mx-auto mb-3" />
            <p className="text-sm">
              Wybierz zakres godzinowy i kliknij &quot;Skanuj&quot;, aby przeskanować bazę wiedzy pod
              kątem zmian regulacyjnych.
            </p>
          </div>
        )}
      </div>
    </RbacGate>
  );
}
