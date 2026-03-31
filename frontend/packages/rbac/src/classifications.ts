import type { RoleName } from './roles';

export type Classification =
  | 'public'
  | 'internal'
  | 'confidential'
  | 'ceo_only'
  | 'personal';

export const ROLE_CLASSIFICATIONS: Record<RoleName, Classification[]> = {
  owner: ['public', 'internal', 'confidential', 'ceo_only', 'personal'],
  gilbertus_admin: ['public', 'internal', 'confidential', 'ceo_only', 'personal'],
  ceo: ['public', 'internal', 'confidential', 'ceo_only', 'personal'],
  board: ['public', 'internal', 'confidential', 'personal'],
  director: ['public', 'internal', 'personal'],
  manager: ['public', 'internal', 'personal'],
  specialist: ['public', 'personal'],
  operator: [],
};

export function allowedClassifications(role: RoleName): Classification[] {
  return ROLE_CLASSIFICATIONS[role] ?? [];
}
