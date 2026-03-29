'use client';

import { useCodeFindings } from '@/lib/hooks/use-admin';
import { useAdminStore } from '@/lib/stores/admin-store';
import { CodeReviewQueue } from '@gilbertus/ui';

export default function CodeReviewPage() {
  const { data, isLoading } = useCodeFindings();
  const store = useAdminStore();
  return (
    <CodeReviewQueue
      findings={data ?? []}
      isLoading={isLoading}
      severityFilter={store.codeReviewSeverityFilter}
      categoryFilter={store.codeReviewCategoryFilter}
      onSeverityFilterChange={store.setCodeReviewSeverityFilter}
      onCategoryFilterChange={store.setCodeReviewCategoryFilter}
    />
  );
}
