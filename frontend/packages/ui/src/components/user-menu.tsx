'use client';

import { useSession, signOut } from 'next-auth/react';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import * as Avatar from '@radix-ui/react-avatar';
import { LogOut, Settings } from 'lucide-react';
import { useRouter } from 'next/navigation';
import type { RoleName } from '@gilbertus/rbac';
import { ROLES } from '@gilbertus/rbac';
import { cn } from '../lib/utils';

interface UserMenuProps {
  collapsed?: boolean;
}

export function UserMenu({ collapsed }: UserMenuProps) {
  const { data: session } = useSession();
  const router = useRouter();

  const name = session?.user?.name ?? 'User';
  const role = (session?.user as { role?: RoleName } | undefined)?.role ?? 'specialist';
  const roleLabel = ROLES[role]?.label ?? role;
  const initials = name
    .split(' ')
    .map((w) => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          className={cn(
            'flex w-full items-center gap-3 rounded-md p-2 text-left transition-colors hover:bg-[var(--surface-hover)]',
            collapsed && 'justify-center',
          )}
        >
          <Avatar.Root className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--accent)] text-white text-xs font-medium">
            <Avatar.Fallback>{initials}</Avatar.Fallback>
          </Avatar.Root>
          {!collapsed && (
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-[var(--text)]">
                {name}
              </p>
              <p className="truncate text-xs text-[var(--text-secondary)]">
                {roleLabel}
              </p>
            </div>
          )}
        </button>
      </DropdownMenu.Trigger>

      <DropdownMenu.Portal>
        <DropdownMenu.Content
          side="top"
          align="start"
          sideOffset={8}
          className="z-50 min-w-[180px] rounded-lg border border-[var(--border)] bg-[var(--surface)] p-1 shadow-lg"
        >
          <DropdownMenu.Item
            className="flex cursor-pointer items-center gap-2 rounded-md px-3 py-2 text-sm text-[var(--text)] outline-none hover:bg-[var(--surface-hover)]"
            onSelect={() => router.push('/settings')}
          >
            <Settings className="h-4 w-4 text-[var(--text-secondary)]" />
            Ustawienia
          </DropdownMenu.Item>
          <DropdownMenu.Separator className="my-1 h-px bg-[var(--border)]" />
          <DropdownMenu.Item
            className="flex cursor-pointer items-center gap-2 rounded-md px-3 py-2 text-sm text-[var(--danger)] outline-none hover:bg-[var(--surface-hover)]"
            onSelect={() => signOut({ callbackUrl: '/login' })}
          >
            <LogOut className="h-4 w-4" />
            Wyloguj
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
