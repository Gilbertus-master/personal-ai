'use client';

import { RoleManager } from '@gilbertus/ui';
import { useAdminRoles } from '@/lib/hooks/use-admin';

export default function RolesPage() {
  const { data, isLoading } = useAdminRoles();
  return <RoleManager roles={data ?? []} isLoading={isLoading} />;
}
