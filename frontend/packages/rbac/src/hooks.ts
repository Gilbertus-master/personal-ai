'use client';

import { useMemo } from 'react';
import { useSession } from 'next-auth/react';
import type { RoleName } from './roles';
import { ROLES } from './roles';
import { hasPermission, ROLE_PERMISSIONS } from './permissions';
import { allowedClassifications } from './classifications';
import type { Classification } from './classifications';

interface UseRoleResult {
  role: RoleName;
  roleLevel: number;
}

export function useRole(): UseRoleResult {
  const { data: session } = useSession();
  const role = (session?.user as { role?: RoleName } | undefined)?.role ?? 'specialist';
  const roleLevel = ROLES[role]?.level ?? 0;
  return { role, roleLevel };
}

interface UsePermissionsResult {
  hasPermission: (permission: string) => boolean;
  permissions: string[];
}

export function usePermissions(): UsePermissionsResult {
  const { role, roleLevel } = useRole();

  return useMemo(() => {
    const permissions = ROLE_PERMISSIONS[role] ?? [];
    return {
      hasPermission: (permission: string) => hasPermission(role, roleLevel, permission),
      permissions,
    };
  }, [role, roleLevel]);
}

export function useClassifications(): Classification[] {
  const { role } = useRole();
  return useMemo(() => allowedClassifications(role), [role]);
}
