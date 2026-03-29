'use client';

import { useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Command } from 'cmdk';
import { useSession, signOut } from 'next-auth/react';
import { useTheme } from 'next-themes';
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
  LogOut,
  Palette,
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

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const router = useRouter();
  const { data: session } = useSession();
  const { setTheme, theme } = useTheme();
  const role = (session?.user as { role?: RoleName } | undefined)?.role ?? 'specialist';
  const modules = getNavigationModules(role);

  // Global keyboard shortcut
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        onOpenChange(!open);
      }
    },
    [open, onOpenChange],
  );

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh]">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 backdrop-blur-sm"
        onClick={() => onOpenChange(false)}
      />

      {/* Palette */}
      <Command
        className={cn(
          'relative w-full max-w-lg rounded-xl border border-[var(--border)] bg-[var(--surface)] shadow-2xl',
          'overflow-hidden',
        )}
        onKeyDown={(e: React.KeyboardEvent) => {
          if (e.key === 'Escape') onOpenChange(false);
        }}
      >
        <Command.Input
          placeholder="Wpisz komendę lub szukaj..."
          className="w-full border-b border-[var(--border)] bg-transparent px-4 py-3 text-sm text-[var(--text)] outline-none placeholder:text-[var(--text-secondary)]"
          autoFocus
        />

        <Command.List className="max-h-80 overflow-y-auto p-2">
          <Command.Empty className="py-6 text-center text-sm text-[var(--text-secondary)]">
            Brak wyników
          </Command.Empty>

          {/* Navigation group */}
          <Command.Group
            heading="Nawigacja"
            className="[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:text-[var(--text-secondary)]"
          >
            {modules.map((mod) => {
              const Icon = ICON_MAP[mod.icon] ?? LayoutDashboard;
              return (
                <Command.Item
                  key={mod.id}
                  value={`${mod.label.pl} ${mod.label.en}`}
                  onSelect={() => {
                    router.push(mod.path);
                    onOpenChange(false);
                  }}
                  className="flex cursor-pointer items-center gap-3 rounded-md px-2 py-2 text-sm text-[var(--text)] aria-selected:bg-[var(--surface-hover)]"
                >
                  <Icon className="h-4 w-4 shrink-0 text-[var(--text-secondary)]" />
                  <span>{mod.label.pl}</span>
                </Command.Item>
              );
            })}
          </Command.Group>

          {/* Actions group */}
          <Command.Group
            heading="Akcje"
            className="[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:text-[var(--text-secondary)]"
          >
            <Command.Item
              value="Zmień motyw Change theme"
              onSelect={() => {
                const CYCLE = ['dark', 'light', 'system'] as const;
                const idx = CYCLE.indexOf(theme as (typeof CYCLE)[number]);
                setTheme(CYCLE[(idx + 1) % CYCLE.length]);
                onOpenChange(false);
              }}
              className="flex cursor-pointer items-center gap-3 rounded-md px-2 py-2 text-sm text-[var(--text)] aria-selected:bg-[var(--surface-hover)]"
            >
              <Palette className="h-4 w-4 shrink-0 text-[var(--text-secondary)]" />
              <span>Zmień motyw</span>
            </Command.Item>
            <Command.Item
              value="Wyloguj Logout"
              onSelect={() => {
                signOut({ callbackUrl: '/login' });
                onOpenChange(false);
              }}
              className="flex cursor-pointer items-center gap-3 rounded-md px-2 py-2 text-sm text-[var(--text)] aria-selected:bg-[var(--surface-hover)]"
            >
              <LogOut className="h-4 w-4 shrink-0 text-[var(--text-secondary)]" />
              <span>Wyloguj</span>
            </Command.Item>
          </Command.Group>
        </Command.List>
      </Command>
    </div>
  );
}
