'use client';

import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';
import type { ComplianceArea } from '@gilbertus/api-client';
import { RbacGate, ComplianceBadge } from '@gilbertus/ui';
import { useComplianceArea } from '@/lib/hooks/use-compliance';
import { useComplianceStore } from '@/lib/stores/compliance-store';

const TABS = [
  { id: 'overview', label: 'Przegląd' },
  { id: 'obligations', label: 'Obowiązki' },
  { id: 'matters', label: 'Sprawy' },
  { id: 'documents', label: 'Dokumenty' },
  { id: 'deadlines', label: 'Terminy' },
  { id: 'trainings', label: 'Szkolenia' },
  { id: 'risks', label: 'Ryzyka' },
  { id: 'raci', label: 'RACI' },
] as const;

type TabId = (typeof TABS)[number]['id'];

export default function AreaDetailPage() {
  const params = useParams<{ code: string }>();
  const router = useRouter();
  const code = params.code;
  const { data: area, isLoading, error } = useComplianceArea(code);
  const { areaDetailTab, setAreaDetailTab } = useComplianceStore();

  return (
    <RbacGate roles={['ceo', 'board', 'director', 'gilbertus_admin']}>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => router.push('/compliance')}
            className="p-1.5 rounded-md hover:bg-[var(--bg-hover)] text-[var(--text-secondary)] transition-colors"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-[var(--text)]">
              {isLoading ? (
                <span className="inline-block h-7 w-48 animate-pulse rounded bg-[var(--bg-hover)]" />
              ) : (
                area?.name_pl ?? code
              )}
            </h1>
            {area && (
              <p className="text-sm text-[var(--text-secondary)]">{area.governing_body}</p>
            )}
          </div>
          {area && <ComplianceBadge type="risk" value={area.risk_level} size="md" />}
        </div>

        {/* Tab Navigation */}
        <div className="flex gap-1 border-b border-[var(--border)]">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setAreaDetailTab(tab.id)}
              className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
                areaDetailTab === tab.id
                  ? 'border-blue-500 text-blue-400'
                  : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text)]'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        {isLoading && (
          <div className="space-y-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-12 animate-pulse rounded-lg bg-[var(--bg-hover)]" />
            ))}
          </div>
        )}

        {error && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-red-400 text-sm">
            Nie udało się załadować danych obszaru: {(error as Error).message}
          </div>
        )}

        {!isLoading && area && areaDetailTab === 'overview' && (
          <AreaOverview area={area} />
        )}

        {!isLoading && area && areaDetailTab !== 'overview' && (
          <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 text-center text-[var(--text-secondary)]">
            Sekcja &ldquo;{TABS.find((t) => t.id === areaDetailTab)?.label}&rdquo; zostanie dodana wkrótce.
          </div>
        )}
      </div>
    </RbacGate>
  );
}

// ── Overview Tab ─────────────────────────────────────────────────────────────

function AreaOverview({ area }: { area: ComplianceArea }) {

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Basic Info */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5 space-y-4">
        <h3 className="font-semibold text-[var(--text)]">Informacje podstawowe</h3>
        <dl className="space-y-3 text-sm">
          <div className="flex justify-between">
            <dt className="text-[var(--text-secondary)]">Kod</dt>
            <dd className="text-[var(--text)] font-mono">{area.code}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-[var(--text-secondary)]">Nazwa (EN)</dt>
            <dd className="text-[var(--text)]">{area.name_en}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-[var(--text-secondary)]">Organ nadzorczy</dt>
            <dd className="text-[var(--text)]">{area.governing_body}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-[var(--text-secondary)]">Poziom ryzyka</dt>
            <dd><ComplianceBadge type="risk" value={area.risk_level} /></dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-[var(--text-secondary)]">Status</dt>
            <dd><ComplianceBadge type="compliance" value={area.status} /></dd>
          </div>
        </dl>
      </div>

      {/* Key Regulations */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5 space-y-4">
        <h3 className="font-semibold text-[var(--text)]">Kluczowe regulacje</h3>
        {area.key_regulations.length > 0 ? (
          <ul className="space-y-2">
            {area.key_regulations.map((reg, i) => (
              <li
                key={i}
                className="text-sm text-[var(--text-secondary)] pl-3 border-l-2 border-[var(--border)]"
              >
                {reg}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-[var(--text-muted)]">Brak zdefiniowanych regulacji.</p>
        )}
      </div>
    </div>
  );
}
