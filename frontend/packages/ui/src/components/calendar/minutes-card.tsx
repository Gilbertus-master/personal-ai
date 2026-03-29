'use client';

import { ChevronDown, ChevronUp, FileText } from 'lucide-react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { MeetingMinutes } from '@gilbertus/api-client';

export interface MinutesCardProps {
  minutes: MeetingMinutes;
  expanded?: boolean;
  onToggle?: () => void;
}

export function MinutesCard({ minutes, expanded = false, onToggle }: MinutesCardProps) {
  const createdDate = new Date(minutes.created).toLocaleDateString('pl-PL', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Europe/Warsaw',
  });

  return (
    <div
      className="rounded-lg border overflow-hidden"
      style={{
        backgroundColor: 'var(--surface)',
        borderColor: 'var(--border)',
        color: 'var(--text)',
      }}
    >
      {/* Header */}
      <button
        type="button"
        onClick={onToggle}
        className="w-full flex items-center justify-between p-4 text-left hover:brightness-110 transition-colors"
        style={{ backgroundColor: 'var(--surface)' }}
      >
        <div className="flex items-center gap-2 min-w-0">
          <FileText size={16} style={{ color: 'var(--accent)', flexShrink: 0 }} />
          <div className="min-w-0">
            <h3 className="font-semibold text-sm truncate">{minutes.title}</h3>
            <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--text-secondary)' }}>
              {minutes.date && <span>{minutes.date}</span>}
              {minutes.participants && (
                <span className="truncate">{minutes.participants}</span>
              )}
            </div>
          </div>
        </div>
        {expanded ? (
          <ChevronUp size={16} style={{ color: 'var(--text-secondary)', flexShrink: 0 }} />
        ) : (
          <ChevronDown size={16} style={{ color: 'var(--text-secondary)', flexShrink: 0 }} />
        )}
      </button>

      {/* Content */}
      {expanded && (
        <div className="px-4 pb-4 border-t" style={{ borderColor: 'var(--border)' }}>
          <div className="prose prose-sm prose-invert max-w-none text-xs mt-3" style={{ color: 'var(--text)' }}>
            <Markdown remarkPlugins={[remarkGfm]}>{minutes.summary}</Markdown>
          </div>
          <div className="mt-3 pt-2 border-t text-[10px]" style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }}>
            Utworzono: {createdDate}
          </div>
        </div>
      )}
    </div>
  );
}
