'use client';

import { usePathname } from 'next/navigation';
import { Menu, Search, Bell } from 'lucide-react';
import { MODULES } from '@gilbertus/rbac';
import type { AlertItem } from '@gilbertus/api-client';
import { ThemeToggle } from './theme-toggle';
import { NotificationBell } from './dashboard/notification-bell';
import { cn } from '../lib/utils';

interface TopbarProps {
  onMobileMenuOpen?: () => void;
  onCommandPaletteOpen?: () => void;
  notificationAlerts?: AlertItem[];
  notificationDismissedIds?: number[];
  onNotificationDismiss?: (alertId: number) => void;
  onNotificationViewAll?: () => void;
}

export function Topbar({
  onMobileMenuOpen,
  onCommandPaletteOpen,
  notificationAlerts,
  notificationDismissedIds,
  onNotificationDismiss,
  onNotificationViewAll,
}: TopbarProps) {
  const pathname = usePathname();

  // Derive current module label from pathname
  const currentModule = MODULES.find(
    (m) => pathname === m.path || pathname?.startsWith(m.path + '/'),
  );
  const breadcrumb = currentModule?.label.pl ?? 'Panel główny';

  return (
    <header
      className={cn(
        'sticky top-0 z-20 flex h-14 items-center justify-between border-b border-[var(--border)] bg-[var(--surface)] px-4',
      )}
    >
      {/* Left: mobile menu + breadcrumb */}
      <div className="flex items-center gap-3">
        <button
          onClick={onMobileMenuOpen}
          className="inline-flex items-center justify-center rounded-md p-2 text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] md:hidden"
          aria-label="Menu"
        >
          <Menu className="h-5 w-5" />
        </button>
        <span className="text-sm font-medium text-[var(--text)]">
          {breadcrumb}
        </span>
      </div>

      {/* Right: Cmd+K, theme, notifications */}
      <div className="flex items-center gap-1">
        <button
          onClick={onCommandPaletteOpen}
          className="inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] transition-colors"
          aria-label="Otwórz paletę komend"
        >
          <Search className="h-4 w-4" />
          <span className="hidden sm:inline">Szukaj...</span>
          <kbd className="hidden rounded border border-[var(--border)] px-1.5 py-0.5 text-xs font-mono text-[var(--text-secondary)] sm:inline">
            Ctrl+K
          </kbd>
        </button>
        <ThemeToggle />
        {notificationAlerts ? (
          <NotificationBell
            alerts={notificationAlerts}
            dismissedIds={notificationDismissedIds}
            onDismiss={onNotificationDismiss}
            onViewAll={onNotificationViewAll}
          />
        ) : (
          <button
            className="relative inline-flex items-center justify-center rounded-md p-2 text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] transition-colors"
            aria-label="Powiadomienia"
          >
            <Bell className="h-5 w-5" />
          </button>
        )}
      </div>
    </header>
  );
}
