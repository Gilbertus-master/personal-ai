'use client';

import {
  Calendar,
  CheckSquare,
  ListTodo,
  Mail,
  MessageSquare,
  AlertTriangle,
  Target,
  Clock,
} from 'lucide-react';
import type { ReactNode } from 'react';
import type { TimelineEvent as TimelineEventType } from '@gilbertus/api-client';

interface TimelineEventProps {
  event: TimelineEventType;
}

const EVENT_TYPE_ICONS: Record<string, ReactNode> = {
  meeting: <Calendar size={16} />,
  spotkanie: <Calendar size={16} />,
  decision: <CheckSquare size={16} />,
  decyzja: <CheckSquare size={16} />,
  task: <ListTodo size={16} />,
  zadanie: <ListTodo size={16} />,
  email: <Mail size={16} />,
  communication: <MessageSquare size={16} />,
  komunikacja: <MessageSquare size={16} />,
  conflict: <AlertTriangle size={16} />,
  konflikt: <AlertTriangle size={16} />,
  commitment: <Target size={16} />,
  zobowiązanie: <Target size={16} />,
};

function formatEventTime(dateStr: string | null): string {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffH = Math.floor(diffMs / 3_600_000);
  const diffD = Math.floor(diffMs / 86_400_000);

  if (diffH < 1) return 'przed chwilą';
  if (diffH < 24)
    return date.toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' });
  if (diffD === 1) return 'wczoraj';
  return date.toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' });
}

export function TimelineEvent({ event }: TimelineEventProps) {
  const icon = EVENT_TYPE_ICONS[event.event_type] ?? <Clock size={16} />;

  return (
    <div className="flex items-start gap-3 border-b border-[var(--border)] px-3 py-3 last:border-b-0">
      {/* Left: icon */}
      <div className="mt-0.5 shrink-0 text-[var(--text-secondary)]">{icon}</div>

      {/* Center: summary + entities */}
      <div className="min-w-0 flex-1">
        <p className="line-clamp-2 text-sm text-[var(--text)]">{event.summary}</p>
        {event.entities.length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1">
            {event.entities.map((entity) => (
              <span
                key={entity}
                className="rounded-full bg-[var(--accent)]/10 px-2 py-0.5 text-xs text-[var(--accent)]"
              >
                {entity}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Right: time */}
      <span className="shrink-0 whitespace-nowrap text-[10px] text-[var(--text-secondary)]">
        {formatEventTime(event.event_time)}
      </span>
    </div>
  );
}
