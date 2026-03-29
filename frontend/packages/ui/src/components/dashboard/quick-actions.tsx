'use client';

import { useRouter } from 'next/navigation';
import { MessageSquare, Calendar, TrendingUp, Shield } from 'lucide-react';
import type { ReactNode } from 'react';

interface QuickActionsProps {
  className?: string;
}

interface ActionItem {
  label: string;
  icon: ReactNode;
  href: string;
}

const ACTIONS: ActionItem[] = [
  { label: 'Nowy czat', icon: <MessageSquare size={24} />, href: '/chat' },
  { label: 'Meeting Prep', icon: <Calendar size={24} />, href: '/chat?action=meeting-prep' },
  { label: 'Scan Market', icon: <TrendingUp size={24} />, href: '/chat?action=market-scan' },
  { label: 'Compliance', icon: <Shield size={24} />, href: '/chat?action=compliance-check' },
];

export function DashboardQuickActions({ className }: QuickActionsProps) {
  const router = useRouter();

  return (
    <div className={className}>
      <div className="grid grid-cols-2 gap-3">
        {ACTIONS.map((action) => (
          <button
            key={action.label}
            type="button"
            onClick={() => router.push(action.href)}
            className="flex flex-col items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 transition-all hover:border-[var(--accent)] hover:bg-[var(--surface-hover)] cursor-pointer"
          >
            <span className="text-[var(--accent)]">{action.icon}</span>
            <span className="text-sm text-[var(--text)]">{action.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
