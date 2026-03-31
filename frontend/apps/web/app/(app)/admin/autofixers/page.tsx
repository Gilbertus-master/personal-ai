'use client';

import { AutofixerDashboard } from '@gilbertus/ui';
import { useAutofixerDashboard } from '@/lib/hooks/use-admin';

export default function AutofixersPage() {
  const { data, isLoading, error } = useAutofixerDashboard();
  return <AutofixerDashboard data={data} isLoading={isLoading} error={error} />;
}
