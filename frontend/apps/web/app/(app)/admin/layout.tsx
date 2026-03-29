'use client';

import type { ReactNode } from 'react';
import { RbacGate } from '@gilbertus/ui';

/* AdminSidebar will be built in P8T5 — inline placeholder for now */
function AdminSidebarPlaceholder() {
  return (
    <nav className="w-56 shrink-0 border-r border-[var(--border)] bg-[var(--surface)] p-4 space-y-1">
      {[
        { label: 'Cron Manager', href: '/admin/crons' },
        { label: 'System Status', href: '/admin/status' },
        { label: 'API Costs', href: '/admin/costs' },
        { label: 'Code Review', href: '/admin/code-review' },
        { label: 'Users', href: '/admin/users' },
        { label: 'Audit Log', href: '/admin/audit' },
        { label: 'Omnius Bridge', href: '/admin/omnius' },
      ].map((item) => (
        <a
          key={item.href}
          href={item.href}
          className="block rounded-md px-3 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text)]"
        >
          {item.label}
        </a>
      ))}
    </nav>
  );
}

function AccessDenied() {
  return (
    <div className="flex items-center justify-center h-full">
      <p className="text-[var(--text-secondary)]">Brak dostępu</p>
    </div>
  );
}

export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <RbacGate roles={['gilbertus_admin', 'operator']} fallback={<AccessDenied />}>
      <div className="flex h-full">
        <AdminSidebarPlaceholder />
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </RbacGate>
  );
}
