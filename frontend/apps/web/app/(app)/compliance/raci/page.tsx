'use client';

import { RbacGate } from '@gilbertus/ui';
import { RaciMatrix } from '@gilbertus/ui/compliance';
import { useRaci, useUpsertRaci } from '@/lib/hooks/use-compliance';
import { useComplianceStore } from '@/lib/stores/compliance-store';

export default function RaciPage() {
  const store = useComplianceStore();
  const raci = useRaci();
  const upsertRaci = useUpsertRaci();

  return (
    <RbacGate roles={['ceo', 'board', 'gilbertus_admin']}>
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-[var(--text)]">Matryca RACI</h1>

        <RaciMatrix
          entries={raci.data?.raci ?? []}
          isLoading={raci.isLoading}
          areaFilter={store.raciArea}
          onAreaChange={store.setRaciArea}
          onUpsert={(data) => upsertRaci.mutate(data)}
          isUpserting={upsertRaci.isPending}
        />
      </div>
    </RbacGate>
  );
}
