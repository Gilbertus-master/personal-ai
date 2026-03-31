'use client';

import { useParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import { RbacGate } from '@gilbertus/ui';
import { TrainingStatusGrid } from '@gilbertus/ui/compliance';
import { useTrainingStatus, useCompleteTraining } from '@/lib/hooks/use-compliance';
import { useRole } from '@gilbertus/rbac';
export function PageClient() {
  const { id } = useParams<{ id: string }>();
  const trainingId = Number(id);

  const trainingStatus = useTrainingStatus(trainingId);
  const completeTraining = useCompleteTraining();
  const { role } = useRole();

  const canComplete = ['ceo', 'board', 'director', 'gilbertus_admin', 'owner'].includes(role);

  return (
    <RbacGate roles={['owner', 'ceo', 'board', 'director', 'gilbertus_admin']}>
      <div className="space-y-6">
        {/* Back link */}
        <Link
          href="/compliance/trainings"
          className="inline-flex items-center gap-1 text-sm text-[var(--text-secondary)] hover:text-[var(--text)] transition-colors"
        >
          <ArrowLeft size={14} />
          Szkolenia compliance
        </Link>

        <TrainingStatusGrid
          training={trainingStatus.data?.training}
          records={trainingStatus.data?.records ?? []}
          isLoading={trainingStatus.isLoading}
          canComplete={canComplete}
          onComplete={(personId, score) =>
            completeTraining.mutate({ trainingId, personId, score })
          }
          isCompleting={completeTraining.isPending}
        />
      </div>
    </RbacGate>
  );
}

export default PageClient;
