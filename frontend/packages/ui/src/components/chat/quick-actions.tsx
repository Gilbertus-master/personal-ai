'use client';

import { Sun, Clock, CalendarCheck, Bell, CheckSquare, type LucideIcon } from 'lucide-react';

interface QuickAction {
  id: string;
  label: string;
  description: string;
  icon: LucideIcon;
  command: string;
}

export const QUICK_ACTIONS: QuickAction[] = [
  { id: 'brief', label: 'Poranny brief', description: 'Podsumowanie dnia', icon: Sun, command: '/brief' },
  { id: 'timeline', label: 'Timeline', description: 'Ostatnie wydarzenia', icon: Clock, command: '/timeline' },
  { id: 'meeting-prep', label: 'Meeting prep', description: 'Przygotowanie na spotkanie', icon: CalendarCheck, command: '/meeting-prep' },
  { id: 'alerts', label: 'Alerty', description: 'Aktywne powiadomienia', icon: Bell, command: '/alerts' },
  { id: 'commitments', label: 'Zobowiązania', description: 'Otwarte commitments', icon: CheckSquare, command: '/commitments' },
];

interface QuickActionsProps {
  onAction: (action: string) => void;
  variant: 'grid' | 'menu';
}

export function QuickActions({ onAction, variant }: QuickActionsProps) {
  if (variant === 'menu') {
    return (
      <div className="flex flex-col py-1">
        {QUICK_ACTIONS.map((action) => {
          const Icon = action.icon;
          return (
            <button
              key={action.id}
              onClick={() => onAction(action.command)}
              className="flex items-center gap-3 px-3 py-2 text-left hover:bg-[var(--surface-hover)] rounded-lg transition-colors"
            >
              <Icon size={16} className="text-[var(--text-secondary)] shrink-0" />
              <span className="text-sm text-[var(--text)]">{action.label}</span>
              <span className="ml-auto text-xs text-[var(--text-secondary)] font-mono">
                {action.command}
              </span>
            </button>
          );
        })}
      </div>
    );
  }

  // Grid variant (empty state)
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 w-full">
      {QUICK_ACTIONS.map((action) => {
        const Icon = action.icon;
        return (
          <button
            key={action.id}
            onClick={() => onAction(action.command)}
            className="flex flex-col items-start gap-2 p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-hover)] hover:border-[var(--accent)]/30 transition-all text-left"
          >
            <Icon size={20} className="text-[var(--accent)]" />
            <div>
              <p className="text-sm font-medium text-[var(--text)]">{action.label}</p>
              <p className="text-xs text-[var(--text-secondary)]">{action.description}</p>
            </div>
          </button>
        );
      })}
    </div>
  );
}
