'use client';

import { Newspaper, Activity, TrendingUp, Users, GitBranch, Bell } from 'lucide-react';
import { cn } from '../../lib/utils';

export interface VoiceCommandBarProps {
  onCommand: (command: string) => void;
  disabled?: boolean;
}

const commands = [
  { id: 'brief', label: 'Brief', icon: Newspaper },
  { id: 'status', label: 'Status', icon: Activity },
  { id: 'rynek', label: 'Rynek', icon: TrendingUp },
  { id: 'konkurencja', label: 'Konkurencja', icon: Users },
  { id: 'scenariusze', label: 'Scenariusze', icon: GitBranch },
  { id: 'alerty', label: 'Alerty', icon: Bell },
] as const;

export function VoiceCommandBar({ onCommand, disabled = false }: VoiceCommandBarProps) {
  return (
    <div className="flex gap-2 overflow-x-auto py-2 scrollbar-none">
      {commands.map(({ id, label, icon: Icon }) => (
        <button
          key={id}
          type="button"
          disabled={disabled}
          onClick={() => onCommand(id)}
          className={cn(
            'flex shrink-0 items-center gap-2 rounded-full border border-[var(--border)] bg-[var(--surface)] px-4 py-2 text-sm text-[var(--text-secondary)] transition-colors',
            'hover:border-[var(--accent)] hover:text-[var(--text)]',
            disabled && 'opacity-50 pointer-events-none',
          )}
        >
          <Icon size={16} />
          {label}
        </button>
      ))}
    </div>
  );
}
