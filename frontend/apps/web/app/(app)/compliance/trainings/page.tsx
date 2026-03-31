'use client';

import { useState } from 'react';
import { Plus } from 'lucide-react';
import { RbacGate } from '@gilbertus/ui';
import { TrainingsTable, CreateTrainingModal } from '@gilbertus/ui/compliance';
import { useTrainings, useCreateTraining } from '@/lib/hooks/use-compliance';
import { useComplianceStore } from '@/lib/stores/compliance-store';

export default function TrainingsPage() {
  const [showCreate, setShowCreate] = useState(false);
  const trainings = useTrainings();
  const createTraining = useCreateTraining();
  const store = useComplianceStore();

  return (
    <RbacGate roles={['owner', 'ceo', 'board', 'director', 'gilbertus_admin']}>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-[var(--text)]">Szkolenia compliance</h1>
          <RbacGate roles={['owner', 'ceo', 'board', 'gilbertus_admin']}>
            <button
              onClick={() => setShowCreate(true)}
              className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium text-white transition-colors"
              style={{ backgroundColor: 'var(--accent)' }}
            >
              <Plus size={16} />
              Nowe szkolenie
            </button>
          </RbacGate>
        </div>

        {/* Table */}
        <TrainingsTable
          trainings={trainings.data?.trainings ?? []}
          isLoading={trainings.isLoading}
          areaFilter={store.trainingArea}
          statusFilter={store.trainingStatus}
          onAreaChange={store.setTrainingArea}
          onStatusChange={store.setTrainingStatus}
        />

        {/* Create Modal */}
        <CreateTrainingModal
          isOpen={showCreate}
          onClose={() => setShowCreate(false)}
          onSubmit={(data) => {
            createTraining.mutate(data, {
              onSuccess: () => setShowCreate(false),
            });
          }}
          isSubmitting={createTraining.isPending}
        />
      </div>
    </RbacGate>
  );
}
