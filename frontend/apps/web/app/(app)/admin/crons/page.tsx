'use client';

import { useCrons, useCronSummary, useToggleCron } from '@/lib/hooks/use-admin';
import { useAdminStore } from '@/lib/stores/admin-store';
import { CronManager } from '@gilbertus/ui';

export default function CronsPage() {
  const { data: cronsData, isLoading } = useCrons();
  const { data: summary } = useCronSummary();
  const toggleCron = useToggleCron();
  const store = useAdminStore();

  return (
    <CronManager
      jobs={cronsData?.jobs ?? []}
      summary={summary}
      isLoading={isLoading}
      filters={{
        category: store.cronCategoryFilter,
        user: store.cronUserFilter,
        enabled: store.cronEnabledFilter,
      }}
      onFilterChange={(f) => {
        if ('category' in f) store.setCronCategoryFilter(f.category ?? null);
        if ('user' in f) store.setCronUserFilter(f.user ?? null);
        if ('enabled' in f) store.setCronEnabledFilter(f.enabled ?? null);
      }}
      onToggle={(name, enable) => toggleCron.mutate({ jobName: name, enable })}
      isToggling={toggleCron.isPending}
    />
  );
}
