'use client';

import { useRole } from '@gilbertus/rbac';
import { useIntelligenceStore } from '@/lib/stores/intelligence-store';
import {
  useOrgHealth,
  useAssessOrgHealth,
  useOpportunities,
  useScanOpportunities,
  useInefficiency,
} from '@/lib/hooks/use-intelligence';
import {
  RbacGate,
  OrgHealthBanner,
  OpportunitiesTable,
  InefficiencyReport,
} from '@gilbertus/ui';
import { cn } from '@gilbertus/ui';

type IntelTab = 'opportunities' | 'inefficiencies' | 'correlations' | 'scenarios' | 'predictions';

const BASE_TABS: { id: IntelTab; label: string }[] = [
  { id: 'opportunities', label: 'Szanse' },
  { id: 'inefficiencies', label: 'Nieefektywnosci' },
  { id: 'correlations', label: 'Korelacje' },
  { id: 'predictions', label: 'Predykcje' },
];

function IntelligenceContent() {
  const { role } = useRole();
  const store = useIntelligenceStore();
  const isCeo = role === 'ceo' || role === 'gilbertus_admin';

  const orgHealth = useOrgHealth();
  const assessMutation = useAssessOrgHealth();
  const opportunities = useOpportunities();
  const scanMutation = useScanOpportunities();
  const inefficiency = useInefficiency();

  const tabs = isCeo
    ? [...BASE_TABS.slice(0, 3), { id: 'scenarios' as IntelTab, label: 'Scenariusze' }, BASE_TABS[3]]
    : BASE_TABS;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-[var(--text)]">Wywiad biznesowy</h1>

      <OrgHealthBanner
        data={orgHealth.data}
        isLoading={orgHealth.isLoading}
        onAssess={() => assessMutation.mutate()}
        isAssessing={assessMutation.isPending}
      />

      {/* Tab bar */}
      <div className="flex items-center gap-1 border-b border-[var(--border)]">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => store.setActiveTab(tab.id)}
            className={cn(
              'px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px',
              store.activeTab === tab.id
                ? 'border-[var(--accent)] text-[var(--accent)]'
                : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text)] hover:border-[var(--border)]',
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Active tab content */}
      {store.activeTab === 'opportunities' && (
        <OpportunitiesTable
          opportunities={opportunities.data ?? []}
          isLoading={opportunities.isLoading}
          onScan={() => scanMutation.mutate(undefined)}
          isScanning={scanMutation.isPending}
          statusFilter={store.opportunityStatus}
          onStatusFilterChange={store.setOpportunityStatus}
        />
      )}

      {store.activeTab === 'inefficiencies' && (
        <InefficiencyReport
          data={inefficiency.data}
          isLoading={inefficiency.isLoading}
        />
      )}

      {store.activeTab === 'correlations' && (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-8 text-center text-sm text-[var(--text-secondary)]">
          Korelacje — w budowie
        </div>
      )}

      {store.activeTab === 'scenarios' && isCeo && (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-8 text-center text-sm text-[var(--text-secondary)]">
          Scenariusze — w budowie
        </div>
      )}

      {store.activeTab === 'predictions' && (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-8 text-center text-sm text-[var(--text-secondary)]">
          Predykcje — w budowie
        </div>
      )}
    </div>
  );
}

export default function IntelligencePage() {
  return (
    <RbacGate
      roles={['ceo', 'board', 'gilbertus_admin']}
      fallback={
        <div className="flex items-center justify-center h-full">
          <p className="text-[var(--text-secondary)]">Brak dostepu do wywiadu biznesowego</p>
        </div>
      }
    >
      <IntelligenceContent />
    </RbacGate>
  );
}
