'use client';

import { useAdminCostBudget } from '@/lib/hooks/use-admin';
import { CostsDashboard } from '@gilbertus/ui';

export default function CostsPage() {
  const { data, isLoading } = useAdminCostBudget();
  return <CostsDashboard budget={data} isLoading={isLoading} />;
}
