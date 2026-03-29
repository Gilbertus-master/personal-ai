'use client';

import { useAdminUsers, useCreateAdminUser } from '@/lib/hooks/use-admin';
import { UserManager } from '@gilbertus/ui';

export default function UsersPage() {
  const { data, isLoading } = useAdminUsers();
  const createUser = useCreateAdminUser();
  return (
    <UserManager
      users={data ?? []}
      isLoading={isLoading}
      onCreateUser={(data) => createUser.mutate(data)}
      isCreating={createUser.isPending}
    />
  );
}
