'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRole } from '@gilbertus/rbac';
import { cn, RbacGate, OrgHealthBanner } from '@gilbertus/ui';
import {
  useOrgHealth,
  useAssessOrgHealth,
  useOpportunities,
  useInefficiency,
  usePredictions,
} from '@/lib/hooks/use-intelligence';
import { useQuery } from '@tanstack/react-query';
import { fetchDecisionPatterns, postCorrelation } from '@gilbertus/api-client';

type BizTab = 'opportunities' | 'correlations' | 'inefficiencies' | 'decisions';

const TABS: { id: BizTab; label: string }[] = [
  { id: 'opportunities', label: 'Szanse' },
  { id: 'correlations', label: 'Korelacje' },
  { id: 'inefficiencies', label: 'Nieefektywnosci' },
  { id: 'decisions', label: 'Decyzje' },
];

function Skeleton() {
  return (
    <div className="animate-pulse space-y-3">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="h-10 bg-[var(--surface)] rounded-lg" />
      ))}
    </div>
  );
}

function StatCard({ label, value, sub, color }: { label: string; value: string | number; sub?: string; color?: string }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
      <p className="text-xs font-medium text-[var(--text-secondary)]">{label}</p>
      <p className={cn('text-2xl font-bold mt-1', color ?? 'text-[var(--text)]')}>{value}</p>
      {sub && <p className="text-xs text-[var(--text-secondary)] mt-0.5">{sub}</p>}
    </div>
  );
}

function OpportunitiesTab() {
  const { data, isLoading } = useOpportunities();
  if (isLoading) return <Skeleton />;
  const opps = data ?? [];

  const totalValue = opps.reduce((s: number, o: Record<string, unknown>) => s + (Number(o.estimated_value) || 0), 0);
  const highRoi = opps.filter((o: Record<string, unknown>) => (Number(o.roi_score) || 0) >= 7);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Szanse" value={opps.length} />
        <StatCard label="Wysoki ROI" value={highRoi.length} color="text-emerald-500" />
        <StatCard
          label="Szac. wartosc"
          value={totalValue > 0 ? `${(totalValue / 1000).toFixed(0)}k` : '-'}
          sub="PLN"
        />
      </div>
      {opps.length === 0 ? (
        <p className="text-sm text-[var(--text-secondary)]">Brak aktywnych szans.</p>
      ) : (
        <div className="rounded-xl border border-[var(--border)] overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-[var(--surface)]">
                <th className="text-left px-4 py-2.5 font-medium text-[var(--text-secondary)]">Typ</th>
                <th className="text-left px-4 py-2.5 font-medium text-[var(--text-secondary)]">Opis</th>
                <th className="text-left px-4 py-2.5 font-medium text-[var(--text-secondary)]">ROI</th>
                <th className="text-left px-4 py-2.5 font-medium text-[var(--text-secondary)]">Pewnosc</th>
              </tr>
            </thead>
            <tbody>
              {opps.slice(0, 10).map((o: Record<string, unknown>, i: number) => (
                <tr key={i} className="border-t border-[var(--border)]">
                  <td className="px-4 py-2.5 font-medium text-[var(--text)]">{String(o.opportunity_type ?? o.type ?? '-')}</td>
                  <td className="px-4 py-2.5 text-[var(--text-secondary)] max-w-md truncate">{String(o.description ?? '')}</td>
                  <td className="px-4 py-2.5">
                    <span
                      className={cn(
                        'font-medium',
                        (Number(o.roi_score) || 0) >= 7 ? 'text-emerald-500' : (Number(o.roi_score) || 0) >= 4 ? 'text-amber-500' : 'text-[var(--text-secondary)]',
                      )}
                    >
                      {Number(o.roi_score)?.toFixed(1) ?? '-'}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-[var(--text-secondary)]">{Number(o.confidence)?.toFixed(0) ?? '-'}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function CorrelationsTab() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['correlations', 'report'],
    queryFn: () => postCorrelation({ correlation_type: 'report', window: 'month' }),
  });

  if (isLoading) return <Skeleton />;
  if (error) return <p className="text-sm text-red-500">Blad ladowania korelacji.</p>;

  const correlations = (data as Record<string, unknown>)?.correlations as Array<Record<string, unknown>> ?? [];
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Wykryte korelacje" value={correlations.length} />
      </div>
      {correlations.length === 0 ? (
        <p className="text-sm text-[var(--text-secondary)]">Brak wykrytych korelacji w ostatnim miesiacu.</p>
      ) : (
        <div className="space-y-3">
          {correlations.slice(0, 10).map((c, i) => (
            <div key={i} className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
              <div className="flex items-start justify-between">
                <div>
                  <p className="font-medium text-[var(--text)]">{String(c.description ?? c.pattern ?? c.type ?? 'Korelacja')}</p>
                  {c.details && <p className="text-sm text-[var(--text-secondary)] mt-1">{String(c.details)}</p>}
                </div>
                {c.strength && (
                  <span
                    className={cn(
                      'text-xs font-medium px-2 py-0.5 rounded-full',
                      Number(c.strength) >= 0.7 ? 'bg-emerald-500/10 text-emerald-500' : 'bg-amber-500/10 text-amber-500',
                    )}
                  >
                    {(Number(c.strength) * 100).toFixed(0)}%
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function InefficiencyTab() {
  const { data, isLoading } = useInefficiency();
  if (isLoading) return <Skeleton />;
  const report = data as Record<string, unknown> | undefined;
  const items = (report?.inefficiencies ?? report?.items ?? []) as Array<Record<string, unknown>>;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Nieefektywnosci" value={items.length} />
      </div>
      {items.length === 0 ? (
        <p className="text-sm text-[var(--text-secondary)]">Brak wykrytych nieefektywnosci.</p>
      ) : (
        <div className="space-y-3">
          {items.map((item, i) => (
            <div key={i} className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
              <div className="flex items-start gap-3">
                <span
                  className={cn(
                    'mt-1 h-2 w-2 rounded-full shrink-0',
                    String(item.severity ?? item.impact) === 'high' ? 'bg-red-500' : 'bg-amber-500',
                  )}
                />
                <div>
                  <p className="font-medium text-[var(--text)]">{String(item.area ?? item.process ?? 'Obszar')}</p>
                  <p className="text-sm text-[var(--text-secondary)] mt-0.5">{String(item.description ?? '')}</p>
                  {item.recommendation && (
                    <p className="text-sm text-[var(--accent)] mt-1">{String(item.recommendation)}</p>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function DecisionsTab() {
  const { data, isLoading } = useQuery({
    queryKey: ['decision-patterns'],
    queryFn: fetchDecisionPatterns,
  });

  if (isLoading) return <Skeleton />;
  const patterns = data as Record<string, unknown> | undefined;
  const items = (patterns?.patterns ?? []) as Array<Record<string, unknown>>;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Wzorce decyzyjne" value={items.length} />
      </div>
      {items.length === 0 ? (
        <p className="text-sm text-[var(--text-secondary)]">Brak zidentyfikowanych wzorcow decyzyjnych.</p>
      ) : (
        <div className="space-y-3">
          {items.map((p, i) => (
            <div key={i} className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
              <p className="font-medium text-[var(--text)]">{String(p.pattern ?? p.area ?? 'Wzorzec')}</p>
              {p.description && (
                <p className="text-sm text-[var(--text-secondary)] mt-1">{String(p.description)}</p>
              )}
              {p.frequency && (
                <span className="inline-block mt-2 text-xs font-medium px-2 py-0.5 rounded-full bg-[var(--accent)]/10 text-[var(--accent)]">
                  {String(p.frequency)}x
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function BusinessIntelligenceContent() {
  const [activeTab, setActiveTab] = useState<BizTab>('opportunities');
  const orgHealth = useOrgHealth();
  const assessMutation = useAssessOrgHealth();

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/intelligence" className="text-[var(--text-secondary)] hover:text-[var(--text)] transition-colors">
          Wywiad
        </Link>
        <span className="text-[var(--text-secondary)]">/</span>
        <h1 className="text-2xl font-bold text-[var(--text)]">Wywiad biznesowy</h1>
      </div>

      <OrgHealthBanner
        data={orgHealth.data}
        isLoading={orgHealth.isLoading}
        onAssess={() => assessMutation.mutate()}
        isAssessing={assessMutation.isPending}
      />

      {/* Tab bar */}
      <div className="flex items-center gap-1 border-b border-[var(--border)]">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              'px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px',
              activeTab === tab.id
                ? 'border-[var(--accent)] text-[var(--accent)]'
                : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text)] hover:border-[var(--border)]',
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'opportunities' && <OpportunitiesTab />}
      {activeTab === 'correlations' && <CorrelationsTab />}
      {activeTab === 'inefficiencies' && <InefficiencyTab />}
      {activeTab === 'decisions' && <DecisionsTab />}
    </div>
  );
}

export default function BusinessIntelligencePage() {
  return (
    <RbacGate
      roles={['owner', 'ceo', 'board', 'gilbertus_admin']}
      fallback={
        <div className="flex items-center justify-center h-64 text-[var(--text-secondary)]">
          Brak dostepu do wywiadu biznesowego
        </div>
      }
    >
      <BusinessIntelligenceContent />
    </RbacGate>
  );
}
