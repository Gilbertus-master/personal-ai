'use client';

import type { ReactNode } from 'react';
import { usePermissions, useRole } from '@gilbertus/rbac';
import type { RoleName } from '@gilbertus/rbac';

interface RbacGateProps {
  permission?: string;
  roles?: RoleName[];
  children: ReactNode;
  fallback?: ReactNode;
}

export function RbacGate({
  permission,
  roles,
  children,
  fallback = null,
}: RbacGateProps) {
  const { hasPermission } = usePermissions();
  const { role } = useRole();

  const permissionOk = !permission || hasPermission(permission);
  const roleOk = !roles || roles.includes(role);

  if (permissionOk && roleOk) {
    return <>{children}</>;
  }

  return <>{fallback}</>;
}
