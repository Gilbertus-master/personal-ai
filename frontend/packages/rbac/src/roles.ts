export type RoleName =
  | 'owner'
  | 'gilbertus_admin'
  | 'operator'
  | 'ceo'
  | 'board'
  | 'director'
  | 'manager'
  | 'specialist';

export const ROLES: Record<RoleName, { level: number; label: string }> = {
  owner: { level: 100, label: 'Owner' },
  gilbertus_admin: { level: 99, label: 'System Admin' },
  operator: { level: 70, label: 'Operator' },
  ceo: { level: 60, label: 'CEO' },
  board: { level: 50, label: 'Board' },
  director: { level: 40, label: 'Director' },
  manager: { level: 30, label: 'Manager' },
  specialist: { level: 20, label: 'Specialist' },
};
