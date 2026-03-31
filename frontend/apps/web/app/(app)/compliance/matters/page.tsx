'use client';

import { useState } from 'react';
import { Plus } from 'lucide-react';
import { RbacGate } from '@gilbertus/ui';
import { MattersTable, CreateMatterModal } from '@gilbertus/ui/compliance';
import { useMatters, useCreateMatter } from '@/lib/hooks/use-compliance';
import { useComplianceStore } from '@/lib/stores/compliance-store';

export default function MattersPage() {
  const [showCreate, setShowCreate] = useState(false);
  const matters = useMatters();
  const createMatter = useCreateMatter();
  const store = useComplianceStore();

  return (
    <RbacGate roles={['owner', 'ceo', 'board', 'director', 'gilbertus_admin']}>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-[var(--text)]">Sprawy compliance</h1>
          <RbacGate roles={['owner', 'ceo', 'board', 'gilbertus_admin']}>
            <button
              onClick={() => setShowCreate(true)}
              className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium text-white transition-colors"
              style={{ backgroundColor: 'var(--accent)' }}
            >
              <Plus size={16} />
              Nowa sprawa
            </button>
          </RbacGate>
        </div>

        {/* Table */}
        <MattersTable
          matters={matters.data?.matters ?? []}
          isLoading={matters.isLoading}
          statusFilter={store.matterStatus}
          areaFilter={store.matterArea}
          priorityFilter={store.matterPriority}
          onStatusChange={store.setMatterStatus}
          onAreaChange={store.setMatterArea}
          onPriorityChange={store.setMatterPriority}
        />

        {/* Create Modal */}
        <CreateMatterModal
          isOpen={showCreate}
          onClose={() => setShowCreate(false)}
          onSubmit={(data) => {
            createMatter.mutate(data, {
              onSuccess: () => setShowCreate(false),
            });
          }}
          isSubmitting={createMatter.isPending}
        />
      </div>
    </RbacGate>
  );
}
