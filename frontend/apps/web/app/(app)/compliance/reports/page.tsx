'use client';

import { RbacGate } from '@gilbertus/ui';
import { ReportViewer } from '@gilbertus/ui/compliance';
import { useDailyReport, useWeeklyReport, useAreaReport } from '@/lib/hooks/use-compliance';
import { useComplianceStore } from '@/lib/stores/compliance-store';

export default function ReportsPage() {
  const store = useComplianceStore();
  const daily = useDailyReport();
  const weekly = useWeeklyReport();
  const areaReport = useAreaReport(store.reportAreaCode ?? '');

  return (
    <RbacGate roles={['ceo', 'board', 'director', 'gilbertus_admin']}>
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-[var(--text)]">Raporty compliance</h1>

        <ReportViewer
          activeTab={store.reportActiveTab}
          onTabChange={store.setReportActiveTab}
          dailyReport={daily.data?.report ?? null}
          isDailyLoading={daily.isLoading}
          weeklyReport={weekly.data ?? null}
          isWeeklyLoading={weekly.isLoading}
          areaCode={store.reportAreaCode}
          onAreaCodeChange={store.setReportAreaCode}
          areaReport={typeof areaReport.data === 'object' ? JSON.stringify(areaReport.data, null, 2) : null}
          isAreaLoading={areaReport.isLoading}
        />
      </div>
    </RbacGate>
  );
}
