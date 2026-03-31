'use client';

import { RbacGate, ComplianceDashboard } from '@gilbertus/ui';
import { useComplianceDashboard, useComplianceAreas } from '@/lib/hooks/use-compliance';

export default function CompliancePage() {
  const dashboard = useComplianceDashboard();
  const areas = useComplianceAreas();

  const isLoading = dashboard.isLoading || areas.isLoading;

  return (
    <RbacGate roles={['owner', 'ceo', 'board', 'director', 'gilbertus_admin']}>
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-[var(--text)]">Compliance</h1>
        <ComplianceDashboard
          dashboard={dashboard.data}
          areas={areas.data?.areas}
          isLoading={isLoading}
        />
      </div>
    </RbacGate>
  );
}
