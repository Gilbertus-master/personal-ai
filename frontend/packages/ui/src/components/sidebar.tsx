'use client';

import { usePathname, useRouter } from 'next/navigation';
import { useSession } from 'next-auth/react';
import Link from 'next/link';
import { useState, useRef, useCallback, useEffect } from 'react';
import { getNavigationModules } from '@gilbertus/rbac';
import type { RoleName } from '@gilbertus/rbac';
import {
  LayoutDashboard, Sunrise, MessageSquare, Users, Brain, Shield,
  TrendingUp, DollarSign, Workflow, Scale, Calendar, FileText,
  Mic, Settings, Bot, PanelLeftClose, PanelLeft, Send, GripVertical,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { cn } from '../lib/utils';

const ICON_MAP: Record<string, LucideIcon> = {
  LayoutDashboard, Sunrise, MessageSquare, Users, Brain, Shield,
  TrendingUp, DollarSign, Workflow, Scale, Calendar, FileText,
  Mic, Settings, Bot,
};

const ORDER_KEY = 'gilbertus-nav-order';

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  onMobileClose?: () => void;
  mobileOpen?: boolean;
}

export function Sidebar({ collapsed, onToggle, onMobileClose, mobileOpen }: SidebarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { data: session } = useSession();
  const role = (session?.user as { role?: RoleName } | undefined)?.role ?? 'ceo';
  const baseModules = getNavigationModules(role);

  // ── Drag-and-drop order ─────────────────────────────────────────────────
  // Initialize with default order (same on server + client → no hydration mismatch)
  // Then read localStorage only after mount
  const [order, setOrder] = useState<string[]>(() => baseModules.map(m => m.id));

  useEffect(() => {
    try {
      const saved = localStorage.getItem(ORDER_KEY);
      if (saved) {
        const ids = JSON.parse(saved) as string[];
        const valid = ids.filter((id: string) => baseModules.some(m => m.id === id));
        const missing = baseModules.filter(m => !valid.includes(m.id)).map(m => m.id);
        setOrder([...valid, ...missing]);
      }
    } catch {}
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const modules = order
    .map(id => baseModules.find(m => m.id === id))
    .filter(Boolean) as typeof baseModules;

  const dragId = useRef<string | null>(null);
  const dragOver = useRef<string | null>(null);

  const handleDragStart = useCallback((id: string) => { dragId.current = id; }, []);
  const handleDragEnter = useCallback((id: string) => { dragOver.current = id; }, []);

  const handleDragEnd = useCallback(() => {
    if (!dragId.current || !dragOver.current || dragId.current === dragOver.current) {
      dragId.current = null; dragOver.current = null; return;
    }
    setOrder(prev => {
      const next = [...prev];
      const from = next.indexOf(dragId.current!);
      const to = next.indexOf(dragOver.current!);
      next.splice(from, 1);
      next.splice(to, 0, dragId.current!);
      try { localStorage.setItem(ORDER_KEY, JSON.stringify(next)); } catch {}
      return next;
    });
    dragId.current = null; dragOver.current = null;
  }, []);

  // ── Sidebar quick-send → przekieruj do /chat z pytaniem ─────────────────
  const [chatQ, setChatQ] = useState('');

  const sendChat = useCallback(() => {
    if (!chatQ.trim()) return;
    const q = encodeURIComponent(chatQ.trim());
    setChatQ('');
    router.push('/chat?q=' + q);
  }, [chatQ, router]);

  const nav = (
    <aside
      className={cn(
        'flex h-screen flex-col border-r border-[var(--border)] bg-[var(--surface)] transition-[width] duration-200',
        collapsed ? 'w-16' : 'w-[260px]',
        mobileOpen !== undefined && 'max-md:fixed max-md:inset-y-0 max-md:left-0 max-md:z-40 max-md:w-[260px]',
      )}
    >
      {/* Logo */}
      <div className="flex h-14 shrink-0 items-center gap-2 border-b border-[var(--border)] px-4">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--accent)] text-white font-bold text-sm">
          G
        </div>
        {!collapsed && (
          <span className="text-sm font-semibold text-[var(--text)] truncate">Gilbertus</span>
        )}
      </div>

      {/* Navigation — drag-and-drop */}
      <nav className="flex-1 overflow-y-auto px-2 py-2 space-y-0.5" suppressHydrationWarning>
        {modules.map((mod) => {
          const Icon = ICON_MAP[mod.icon] ?? LayoutDashboard;
          const isActive = pathname === mod.path || pathname?.startsWith(mod.path + '/');
          return (
            <div
              key={mod.id}
              draggable
              onDragStart={() => handleDragStart(mod.id)}
              onDragEnter={() => handleDragEnter(mod.id)}
              onDragEnd={handleDragEnd}
              onDragOver={(e) => e.preventDefault()}
              className="group relative"
            >
              <Link
                href={mod.path}
                onClick={onMobileClose}
                className={cn(
                  'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-[var(--surface-hover)] text-[var(--text)] border-l-2 border-[var(--accent)] pl-[10px]'
                    : 'text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text)] border-l-2 border-transparent',
                  collapsed ? 'justify-center px-0' : 'pr-7',
                )}
                title={collapsed ? mod.label.pl : undefined}
              >
                <Icon className="h-5 w-5 shrink-0" />
                {!collapsed && <span className="truncate">{mod.label.pl}</span>}
              </Link>
              {/* Drag handle (visible on hover, only when expanded) */}
              {!collapsed && (
                <GripVertical className="absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--text-secondary)] opacity-0 group-hover:opacity-40 cursor-grab active:cursor-grabbing transition-opacity" />
              )}
            </div>
          );
        })}
      </nav>

      {/* Inline Chat Gilbertusa */}
      {!collapsed && (
        <div className="shrink-0 border-t border-[var(--border)] px-3 py-3 space-y-2">
          <p className="text-[10px] uppercase tracking-widest text-[var(--text-secondary)] font-semibold px-1">
            Zapytaj Gilbertusa
          </p>

          {/* Input — Enter sends to /chat */}
          <div className="flex items-center gap-1.5">
            <input
              value={chatQ}
              onChange={e => setChatQ(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && sendChat()}
              placeholder="Zadaj pytanie…"
              className="flex-1 min-w-0 rounded-md border border-[var(--border)] bg-[var(--bg)] px-2.5 py-1.5 text-xs text-[var(--text)] placeholder:text-[var(--text-secondary)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
            />
            <button
              onClick={sendChat}
              disabled={!chatQ.trim()}
              className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-[var(--accent)] text-white disabled:opacity-40 hover:opacity-90 transition-opacity"
            >
              <Send className="h-3 w-3" />
            </button>
          </div>
        </div>
      )}

      {/* Footer: Collapse toggle */}
      <div className="shrink-0 border-t border-[var(--border)] p-2">
        <button
          onClick={onToggle}
          className="flex w-full items-center justify-center gap-2 rounded-md p-2 text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text)] transition-colors"
          aria-label={collapsed ? 'Rozwiń' : 'Zwiń'}
        >
          {collapsed
            ? <PanelLeft className="h-5 w-5" />
            : <><PanelLeftClose className="h-5 w-5" /><span className="text-sm">Zwiń</span></>}
        </button>
      </div>
    </aside>
  );

  if (mobileOpen) {
    return (
      <>
        <div className="fixed inset-0 z-30 bg-black/50 md:hidden" onClick={onMobileClose} />
        {nav}
      </>
    );
  }
  return nav;
}
