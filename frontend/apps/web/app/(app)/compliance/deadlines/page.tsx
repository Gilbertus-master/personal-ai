'use client';

import { RbacGate } from '@gilbertus/ui';
import { DeadlineCalendar } from '@gilbertus/ui/compliance';
import { useDeadlines, useOverdueDeadlines } from '@/lib/hooks/use-compliance';
import { useComplianceStore } from '@/lib/stores/compliance-store';

export default function DeadlinesPage() {
  const deadlines = useDeadlines();
  const overdueDeadlines = useOverdueDeadlines();
  const store = useComplianceStore();

  return (
    <RbacGate roles={['ceo', 'board', 'director', 'gilbertus_admin']}>
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-[var(--text)]">Terminy compliance</h1>

        <DeadlineCalendar
          deadlines={deadlines.data?.deadlines ?? []}
          overdueDeadlines={overdueDeadlines.data ?? []}
          isLoading={deadlines.isLoading}
          daysAhead={store.daysAhead}
          areaFilter={store.deadlineArea}
          onDaysAheadChange={store.setDaysAhead}
          onAreaChange={store.setDeadlineArea}
        />
      </div>
    </RbacGate>
  );
}
