'use client';

import { useState } from 'react';
import { RbacGate } from '@gilbertus/ui';
import { ObligationsTable, FulfillModal } from '@gilbertus/ui/compliance';
import { useObligations, useOverdueObligations, useFulfillObligation } from '@/lib/hooks/use-compliance';
import { useComplianceStore } from '@/lib/stores/compliance-store';

export default function ObligationsPage() {
  const [fulfillTarget, setFulfillTarget] = useState<{ id: number; title: string } | null>(null);
  const obligations = useObligations();
  const overdueObligations = useOverdueObligations();
  const fulfillObligation = useFulfillObligation();
  const store = useComplianceStore();

  return (
    <RbacGate roles={['ceo', 'board', 'director', 'gilbertus_admin']}>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-[var(--text)]">Obowiązki compliance</h1>
        </div>

        <ObligationsTable
          obligations={obligations.data?.obligations ?? []}
          overdueObligations={overdueObligations.data ?? []}
          isLoading={obligations.isLoading}
          showOverdueOnly={store.showOverdueOnly}
          areaFilter={store.obligationArea}
          statusFilter={store.obligationStatus}
          onAreaChange={store.setObligationArea}
          onStatusChange={store.setObligationStatus}
          onOverdueToggle={store.setShowOverdueOnly}
          onFulfill={(id, title) => setFulfillTarget({ id, title })}
          canFulfill={true}
        />

        <FulfillModal
          obligationId={fulfillTarget?.id ?? 0}
          obligationTitle={fulfillTarget?.title ?? ''}
          isOpen={fulfillTarget !== null}
          onClose={() => setFulfillTarget(null)}
          onSubmit={(id, evidence) => {
            fulfillObligation.mutate(
              { id, evidence },
              { onSuccess: () => setFulfillTarget(null) },
            );
          }}
          isSubmitting={fulfillObligation.isPending}
        />
      </div>
    </RbacGate>
  );
}
