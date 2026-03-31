'use client';

import { useState } from 'react';
import { useRole } from '@gilbertus/rbac';
import { useIntelligenceStore } from '@/lib/stores/intelligence-store';
import {
  useOrgHealth,
  useAssessOrgHealth,
  useOpportunities,
  useScanOpportunities,
  useInefficiency,
  useCorrelation,
  useScenarios,
  useCreateScenario,
  useAnalyzeScenario,
  usePredictions,
} from '@/lib/hooks/use-intelligence';
import {
  RbacGate,
  OrgHealthBanner,
  OpportunitiesTable,
  InefficiencyReport,
  CorrelationExplorer,
  ScenariosList,
  ScenarioForm,
  PredictiveAlerts,
} from '@gilbertus/ui';
import { cn } from '@gilbertus/ui';
import type { CorrelationRequest, CorrelationResult } from '@gilbertus/api-client';

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
  const isCeo = role === 'ceo' || role === 'gilbertus_admin' || role === 'owner';

  const orgHealth = useOrgHealth();
  const assessMutation = useAssessOrgHealth();
  const opportunities = useOpportunities();
  const scanMutation = useScanOpportunities();
  const inefficiency = useInefficiency();

  // Correlations
  const correlationMutation = useCorrelation();
  const [correlationResult, setCorrelationResult] = useState<CorrelationResult | null>(null);

  // Scenarios
  const scenarios = useScenarios();
  const createScenarioMutation = useCreateScenario();
  const analyzeScenarioMutation = useAnalyzeScenario();
  const [showScenarioForm, setShowScenarioForm] = useState(false);

  // Predictions
  const predictions = usePredictions();

  const tabs = isCeo
    ? [...BASE_TABS.slice(0, 3), { id: 'scenarios' as IntelTab, label: 'Scenariusze' }, BASE_TABS[3]]
    : BASE_TABS;

  const handleRunCorrelation = (request: CorrelationRequest) => {
    correlationMutation.mutate(request, {
      onSuccess: (data) => setCorrelationResult(data),
    });
  };

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
        <CorrelationExplorer
          correlationType={store.correlationType}
          onTypeChange={store.setCorrelationType}
          params={store.correlationParams}
          onParamChange={store.setCorrelationParam}
          onReset={store.resetCorrelationParams}
          onRun={handleRunCorrelation}
          result={correlationResult}
          isRunning={correlationMutation.isPending}
        />
      )}

      {store.activeTab === 'scenarios' && isCeo && (
        <>
          <ScenariosList
            scenarios={scenarios.data ?? []}
            isLoading={scenarios.isLoading}
            statusFilter={store.scenarioStatus}
            onStatusFilterChange={store.setScenarioStatus}
            onCreateNew={() => setShowScenarioForm(true)}
            onAnalyze={(id) => analyzeScenarioMutation.mutate(id)}
            onCompare={() => {/* compare handled inline */}}
            isAnalyzing={analyzeScenarioMutation.isPending}
            isCeo={isCeo}
          />
          <ScenarioForm
            isOpen={showScenarioForm}
            onClose={() => setShowScenarioForm(false)}
            onSubmit={(params) => {
              createScenarioMutation.mutate(params, {
                onSuccess: () => setShowScenarioForm(false),
              });
            }}
            isSubmitting={createScenarioMutation.isPending}
          />
        </>
      )}

      {store.activeTab === 'predictions' && (
        <PredictiveAlerts
          data={predictions.data}
          isLoading={predictions.isLoading}
        />
      )}
    </div>
  );
}

export default function IntelligencePage() {
  return (
    <RbacGate
      roles={['owner', 'ceo', 'board', 'gilbertus_admin']}
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
