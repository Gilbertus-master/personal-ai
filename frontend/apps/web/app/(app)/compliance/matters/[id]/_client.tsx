'use client';

import { useParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import { RbacGate } from '@gilbertus/ui';
import { MatterDetail } from '@gilbertus/ui/compliance';
import {
  useMatter,
  useResearchMatter,
  useAdvanceMatter,
  useMatterReport,
  useCommPlan,
  useExecuteComm,
} from '@/lib/hooks/use-compliance';
import { useComplianceStore } from '@/lib/stores/compliance-store';

export function PageClient() {
  const { id } = useParams<{ id: string }>();
  const matterId = Number(id);

  const matter = useMatter(matterId);
  const research = useResearchMatter();
  const advance = useAdvanceMatter();
  const report = useMatterReport();
  const commPlan = useCommPlan();
  const execComm = useExecuteComm();
  const store = useComplianceStore();

  return (
    <RbacGate roles={['ceo', 'board', 'director', 'gilbertus_admin']}>
      <div className="space-y-6">
        {/* Back link */}
        <Link
          href="/compliance/matters"
          className="inline-flex items-center gap-1 text-sm text-[var(--text-secondary)] hover:text-[var(--text)] transition-colors"
        >
          <ArrowLeft size={14} />
          Sprawy compliance
        </Link>

        <MatterDetail
          matter={matter.data}
          isLoading={matter.isLoading}
          activeTab={store.matterDetailTab}
          onTabChange={store.setMatterDetailTab}
          onResearch={(mid) => research.mutate({ matterId: mid })}
          onAdvance={(mid) => advance.mutate({ matterId: mid })}
          onReport={(mid) => report.mutate(mid)}
          onCommPlan={(mid) => commPlan.mutate(mid)}
          onExecuteComm={(mid) => execComm.mutate(mid)}
          isResearching={research.isPending}
          isAdvancing={advance.isPending}
          isReporting={report.isPending}
          isCommPlanning={commPlan.isPending}
          isExecutingComm={execComm.isPending}
        />
      </div>
    </RbacGate>
  );
}
