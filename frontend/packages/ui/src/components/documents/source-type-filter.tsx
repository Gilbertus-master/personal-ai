'use client';

import { Mail, Users, MessageCircle, FileText, Mic, Bot, Calendar } from 'lucide-react';
import type { SourceType } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';

export interface SourceTypeFilterProps {
  selected: string[];
  onChange: (types: string[]) => void;
  counts?: Record<string, number>;
}

const SOURCE_TYPES: { value: SourceType; label: string; icon: typeof Mail }[] = [
  { value: 'email', label: 'Email', icon: Mail },
  { value: 'teams', label: 'Teams', icon: Users },
  { value: 'whatsapp', label: 'WhatsApp', icon: MessageCircle },
  { value: 'document', label: 'Dokumenty', icon: FileText },
  { value: 'pdf', label: 'PDF', icon: FileText },
  { value: 'plaud', label: 'Plaud', icon: Mic },
  { value: 'chatgpt', label: 'ChatGPT', icon: Bot },
  { value: 'calendar', label: 'Kalendarz', icon: Calendar },
];

export function SourceTypeFilter({ selected, onChange, counts }: SourceTypeFilterProps) {
  const toggle = (value: string) => {
    if (selected.includes(value)) {
      onChange(selected.filter((s) => s !== value));
    } else {
      onChange([...selected, value]);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {SOURCE_TYPES.map(({ value, label, icon: Icon }) => {
        const active = selected.includes(value);
        const count = counts?.[value];
        return (
          <button
            key={value}
            onClick={() => toggle(value)}
            className={cn(
              'flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium transition-colors',
              active
                ? 'bg-[var(--accent)] text-white'
                : 'bg-[var(--surface)] text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]',
            )}
          >
            <Icon size={13} />
            <span>{label}</span>
            {count != null && (
              <span
                className={cn(
                  'ml-0.5 rounded-full px-1.5 text-[10px]',
                  active ? 'bg-white/20' : 'bg-[var(--border)]',
                )}
              >
                {count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
