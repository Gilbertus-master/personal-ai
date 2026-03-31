'use client';

import { RbacGate } from '@gilbertus/ui';
import { RisksTable, RiskHeatmap } from '@gilbertus/ui/compliance';
import { useRisks, useRiskHeatmap } from '@/lib/hooks/use-compliance';
import { useComplianceStore } from '@/lib/stores/compliance-store';
import { cn } from '@gilbertus/ui';

const TABS = [
  { key: 'register' as const, label: 'Rejestr' },
  { key: 'heatmap' as const, label: 'Heatmap' },
] as const;

export default function RisksPage() {
  const store = useComplianceStore();
  const risks = useRisks();
  const heatmap = useRiskHeatmap();

  return (
    <RbacGate roles={['owner', 'ceo', 'board', 'gilbertus_admin']}>
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-[var(--text)]">Ryzyka compliance</h1>

        {/* Tab Navigation */}
        <div className="flex gap-0 border-b border-[var(--border)]">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => store.setRiskActiveTab(tab.key)}
              className={cn(
                'px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px',
                store.riskActiveTab === tab.key
                  ? 'border-[var(--accent)] text-[var(--text)]'
                  : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text)]',
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Register Tab */}
        {store.riskActiveTab === 'register' && (
          <RisksTable
            risks={risks.data?.risks ?? []}
            isLoading={risks.isLoading}
            areaFilter={store.riskArea}
            statusFilter={store.riskStatus}
            onAreaChange={store.setRiskArea}
            onStatusChange={store.setRiskStatus}
          />
        )}

        {/* Heatmap Tab */}
        {store.riskActiveTab === 'heatmap' && (
          <RiskHeatmap
            risks={risks.data?.risks ?? []}
            heatmapAreas={heatmap.data?.areas ?? []}
            totalRisks={heatmap.data?.total_risks ?? 0}
            overallAvg={heatmap.data?.overall_avg ?? 0}
            isLoading={risks.isLoading || heatmap.isLoading}
            onCellClick={(likelihood, impact) => {
              // Switch to register tab filtered by the clicked cell
              store.setRiskActiveTab('register');
            }}
          />
        )}
      </div>
    </RbacGate>
  );
}
