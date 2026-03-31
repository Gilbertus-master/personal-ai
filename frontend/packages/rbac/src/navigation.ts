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
  { id: 'brief', icon: 'Sunrise', roles: ['ceo', 'board'], label: { pl: 'Poranny Brief', en: 'Morning Brief' }, path: '/brief' },
  { id: 'chat', icon: 'MessageSquare', roles: ['*'], label: { pl: 'Chat', en: 'Chat' }, path: '/chat' },
  { id: 'people', icon: 'Users', roles: ['ceo', 'board', 'director'], label: { pl: 'Ludzie', en: 'People' }, path: '/people' },
  { id: 'intelligence', icon: 'Brain', roles: ['ceo', 'board'], label: { pl: 'Wywiad', en: 'Intelligence' }, path: '/intelligence' },
  { id: 'compliance', icon: 'Shield', roles: ['ceo', 'board', 'director'], label: { pl: 'Compliance', en: 'Compliance' }, path: '/compliance' },
  { id: 'market', icon: 'TrendingUp', roles: ['ceo', 'board', 'director'], label: { pl: 'Rynek', en: 'Market' }, path: '/market' },
  { id: 'finance', icon: 'DollarSign', roles: ['ceo', 'board'], label: { pl: 'Finanse', en: 'Finance' }, path: '/finance' },
  { id: 'process', icon: 'Workflow', roles: ['ceo', 'board', 'director'], label: { pl: 'Procesy', en: 'Processes' }, path: '/process' },
  { id: 'decisions', icon: 'Scale', roles: ['ceo'], label: { pl: 'Decyzje', en: 'Decisions' }, path: '/decisions' },
  { id: 'calendar', icon: 'Calendar', roles: ['ceo', 'board', 'director', 'manager'], label: { pl: 'Kalendarz', en: 'Calendar' }, path: '/calendar' },
  { id: 'documents', icon: 'FileText', roles: ['ceo', 'board', 'director'], label: { pl: 'Dokumenty', en: 'Documents' }, path: '/documents' },
  { id: 'voice', icon: 'Mic', roles: ['ceo', 'board'], label: { pl: 'Głos', en: 'Voice' }, path: '/voice' },
  { id: 'admin', icon: 'ShieldCheck', roles: ['gilbertus_admin', 'operator'], label: { pl: 'Admin', en: 'Admin' }, path: '/admin' },
  { id: 'settings', icon: 'Settings', roles: ['*'], label: { pl: 'Ustawienia', en: 'Settings' }, path: '/settings' },
  { id: 'omnius', icon: 'Bot', roles: ['gilbertus_admin'], label: { pl: 'Omnius', en: 'Omnius' }, path: '/admin/omnius' },
  { id: 'admin-autofixers', icon: 'Wrench', roles: ['gilbertus_admin', 'operator'], label: { pl: 'Autofixery', en: 'Autofixers' }, path: '/admin/autofixers' },
];

export function getNavigationModules(role: RoleName): ModuleConfig[] {
  const isAdmin = ROLES[role].level >= 99;

  return MODULES.filter((mod) => {
    if (isAdmin) return true;
    if (mod.roles[0] === '*') return true;
    return (mod.roles as RoleName[]).includes(role);
  });
}
