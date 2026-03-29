'use client';

import { usePathname } from 'next/navigation';
import { useSession } from 'next-auth/react';
import Link from 'next/link';
import { getNavigationModules } from '@gilbertus/rbac';
import type { RoleName } from '@gilbertus/rbac';
import {
  LayoutDashboard,
  MessageSquare,
  Users,
  Brain,
  Shield,
  TrendingUp,
  DollarSign,
  Workflow,
  Scale,
  Calendar,
  FileText,
  Mic,
  Settings,
  Bot,
  PanelLeftClose,
  PanelLeft,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { cn } from '../lib/utils';

const ICON_MAP: Record<string, LucideIcon> = {
  LayoutDashboard,
  MessageSquare,
  Users,
  Brain,
  Shield,
  TrendingUp,
  DollarSign,
  Workflow,
  Scale,
  Calendar,
  FileText,
  Mic,
  Settings,
  Bot,
};

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  onMobileClose?: () => void;
  mobileOpen?: boolean;
}

export function Sidebar({ collapsed, onToggle, onMobileClose, mobileOpen }: SidebarProps) {
  const pathname = usePathname();
  const { data: session } = useSession();
  const role = (session?.user as { role?: RoleName } | undefined)?.role ?? 'specialist';
  const modules = getNavigationModules(role);

  const nav = (
    <aside
      className={cn(
        'flex h-screen flex-col border-r border-[var(--border)] bg-[var(--surface)] transition-[width] duration-200',
        collapsed ? 'w-16' : 'w-[260px]',
        // mobile: full overlay
        mobileOpen !== undefined && 'max-md:fixed max-md:inset-y-0 max-md:left-0 max-md:z-40 max-md:w-[260px]',
      )}
    >
      {/* Logo */}
      <div className="flex h-14 items-center gap-2 border-b border-[var(--border)] px-4">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--accent)] text-white font-bold text-sm">
          G
        </div>
        {!collapsed && (
          <span className="text-sm font-semibold text-[var(--text)] truncate">
            Gilbertus
          </span>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-2 py-2 space-y-0.5">
        {modules.map((mod) => {
          const Icon = ICON_MAP[mod.icon] ?? LayoutDashboard;
          const isActive = pathname === mod.path || pathname?.startsWith(mod.path + '/');
          return (
            <Link
              key={mod.id}
              href={mod.path}
              onClick={onMobileClose}
              className={cn(
                'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-[var(--accent)] bg-opacity-15 text-[var(--accent)]'
                  : 'text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text)]',
                collapsed && 'justify-center px-0',
              )}
              title={collapsed ? mod.label.pl : undefined}
            >
              <Icon className="h-5 w-5 shrink-0" />
              {!collapsed && <span className="truncate">{mod.label.pl}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Footer: Collapse toggle */}
      <div className="border-t border-[var(--border)] p-2">
        <button
          onClick={onToggle}
          className="flex w-full items-center justify-center gap-2 rounded-md p-2 text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text)] transition-colors"
          aria-label={collapsed ? 'Rozwiń' : 'Zwiń'}
        >
          {collapsed ? (
            <PanelLeft className="h-5 w-5" />
          ) : (
            <>
              <PanelLeftClose className="h-5 w-5" />
              <span className="text-sm">Zwiń</span>
            </>
          )}
        </button>
      </div>
    </aside>
  );

  // Mobile: backdrop overlay
  if (mobileOpen) {
    return (
      <>
        <div
          className="fixed inset-0 z-30 bg-black/50 md:hidden"
          onClick={onMobileClose}
        />
        {nav}
      </>
    );
  }

  return nav;
}
