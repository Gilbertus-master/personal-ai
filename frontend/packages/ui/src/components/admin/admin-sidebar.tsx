'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { useRole } from '@gilbertus/rbac';
import {
  Clock,
  Activity,
  DollarSign,
  Code,
  Users,
  FileSearch,
  Bot,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { cn } from '../../lib/utils';

interface NavItem {
  path: string;
  label: string;
  icon: LucideIcon;
  adminOnly?: boolean;
}

const ADMIN_NAV: NavItem[] = [
  { path: '/admin/crons', label: 'Cron Manager', icon: Clock },
  { path: '/admin/status', label: 'Status systemu', icon: Activity },
  { path: '/admin/costs', label: 'Koszty API', icon: DollarSign },
  { path: '/admin/code-review', label: 'Code Review', icon: Code },
  { path: '/admin/users', label: 'Użytkownicy', icon: Users },
  { path: '/admin/audit', label: 'Audit Log', icon: FileSearch, adminOnly: true },
  { path: '/admin/omnius', label: 'Omnius Bridge', icon: Bot, adminOnly: true },
];

export function AdminSidebar() {
  const pathname = usePathname();
  const { role } = useRole();

  const items = ADMIN_NAV.filter(
    (item) => !item.adminOnly || role === 'gilbertus_admin',
  );

  return (
    <aside className="flex h-full w-56 shrink-0 flex-col border-r border-[var(--border)] bg-[var(--surface)]">
      <div className="px-4 py-4">
        <h2 className="text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">
          Administracja
        </h2>
      </div>
      <nav className="flex-1 overflow-y-auto px-2 space-y-0.5">
        {items.map((item) => {
          const Icon = item.icon;
          const isActive = pathname?.startsWith(item.path);
          return (
            <Link
              key={item.path}
              href={item.path}
              className={cn(
                'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'border-l-2 border-[var(--accent)] bg-[var(--accent)]/10 text-[var(--accent)] pl-[10px]'
                  : 'text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text)]',
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span className="truncate">{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
