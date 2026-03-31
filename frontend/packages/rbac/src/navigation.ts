import type { RoleName } from './roles';
import { ROLES } from './roles';

export interface ModuleConfig {
  id: string;
  icon: string;
  roles: RoleName[] | ['*'];
  label: { pl: string; en: string };
  path: string;
}

export const MODULES: ModuleConfig[] = [
  { id: 'dashboard', icon: 'LayoutDashboard', roles: ['*'], label: { pl: 'Pulpit', en: 'Dashboard' }, path: '/dashboard' },
  { id: 'brief', icon: 'Sunrise', roles: ['owner', 'ceo', 'board'], label: { pl: 'Poranny Brief', en: 'Morning Brief' }, path: '/brief' },
  { id: 'chat', icon: 'MessageSquare', roles: ['*'], label: { pl: 'Chat', en: 'Chat' }, path: '/chat' },
  { id: 'people', icon: 'Users', roles: ['owner', 'ceo', 'board', 'director'], label: { pl: 'Ludzie', en: 'People' }, path: '/people' },
  { id: 'intelligence', icon: 'Brain', roles: ['owner', 'ceo', 'board'], label: { pl: 'Wywiad', en: 'Intelligence' }, path: '/intelligence' },
  { id: 'compliance', icon: 'Shield', roles: ['owner', 'ceo', 'board', 'director'], label: { pl: 'Compliance', en: 'Compliance' }, path: '/compliance' },
  { id: 'market', icon: 'TrendingUp', roles: ['owner', 'ceo', 'board', 'director'], label: { pl: 'Rynek', en: 'Market' }, path: '/market' },
  { id: 'finance', icon: 'DollarSign', roles: ['owner', 'ceo', 'board'], label: { pl: 'Finanse', en: 'Finance' }, path: '/finance' },
  { id: 'process', icon: 'Workflow', roles: ['owner', 'ceo', 'board', 'director'], label: { pl: 'Procesy', en: 'Processes' }, path: '/process' },
  { id: 'decisions', icon: 'Scale', roles: ['owner', 'ceo'], label: { pl: 'Decyzje', en: 'Decisions' }, path: '/decisions' },
  { id: 'calendar', icon: 'Calendar', roles: ['owner', 'ceo', 'board', 'director', 'manager'], label: { pl: 'Kalendarz', en: 'Calendar' }, path: '/calendar' },
  { id: 'documents', icon: 'FileText', roles: ['owner', 'ceo', 'board', 'director'], label: { pl: 'Dokumenty', en: 'Documents' }, path: '/documents' },
  { id: 'voice', icon: 'Mic', roles: ['owner', 'ceo', 'board'], label: { pl: 'Głos', en: 'Voice' }, path: '/voice' },
  { id: 'admin', icon: 'ShieldCheck', roles: ['owner', 'gilbertus_admin', 'operator'], label: { pl: 'Admin', en: 'Admin' }, path: '/admin' },
  { id: 'settings', icon: 'Settings', roles: ['*'], label: { pl: 'Ustawienia', en: 'Settings' }, path: '/settings' },
];

export function getNavigationModules(role: RoleName): ModuleConfig[] {
  const isOwner = ROLES[role].level >= 100;

  return MODULES.filter((mod) => {
    if (isOwner) return true;
    if (mod.roles[0] === '*') return true;
    return (mod.roles as RoleName[]).includes(role);
  });
}
