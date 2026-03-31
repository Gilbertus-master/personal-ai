import type { RoleName } from './roles';

export const ROLE_PERMISSIONS: Record<RoleName, string[]> = {
  owner: [],
  gilbertus_admin: [],
  operator: [
    'config:write:system',
    'sync:manage',
    'sync:credentials',
    'infra:manage',
    'dev:execute',
    'commands:task',
  ],
  ceo: [
    'data:read:all',
    'financials:read',
    'evaluations:read:all',
    'communications:read:all',
    'config:write:system',
    'users:manage:all',
    'queries:create',
    'prompts:manage',
    'rbac:manage',
    'commands:email',
    'commands:ticket',
    'commands:meeting',
    'commands:task',
    'commands:sync',
    'views:configure:own',
  ],
  board: [
    'data:read:all',
    'financials:read',
    'evaluations:read:reports',
    'config:write:system',
    'users:manage:below',
    'queries:create',
    'commands:email',
    'commands:ticket',
    'commands:meeting',
    'commands:task',
    'commands:sync',
    'views:configure:own',
  ],
  director: [
    'data:read:department',
    'evaluations:read:reports',
    'communications:read:department',
    'config:write:department',
    'queries:create',
    'commands:email',
    'commands:ticket',
    'commands:meeting',
    'commands:task',
    'commands:sync',
    'views:configure:own',
  ],
  manager: [
    'data:read:team',
    'config:write:own',
    'queries:create:department',
    'commands:ticket',
    'commands:meeting',
    'commands:task',
    'views:configure:own',
  ],
  specialist: [
    'data:read:own',
    'config:write:own',
    'commands:task',
    'views:configure:own',
  ],
};

export function hasPermission(
  role: RoleName,
  roleLevel: number,
  permission: string,
): boolean {
  if (roleLevel >= 99) return true;
  const perms = ROLE_PERMISSIONS[role] ?? [];
  if (perms.includes(permission)) return true;
  // Hierarchy: data:read:all covers data:read:department, data:read:team, etc.
  const parts = permission.split(':');
  if (parts.length >= 3) {
    const wildcard = parts.slice(0, -1).join(':') + ':all';
    if (perms.includes(wildcard)) return true;
  }
  return false;
}
