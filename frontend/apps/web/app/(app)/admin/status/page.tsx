'use client';

import { useSystemStatus } from '@/lib/hooks/use-admin';
import { SystemStatusDashboard } from '@gilbertus/ui';

export default function StatusPage() {
  const { data, isLoading } = useSystemStatus();
  return <SystemStatusDashboard status={data} isLoading={isLoading} />;
}
