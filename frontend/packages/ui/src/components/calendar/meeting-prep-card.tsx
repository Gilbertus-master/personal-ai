'use client';

import { useState } from 'react';
import { Clock, Users, ChevronDown, ChevronUp } from 'lucide-react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { MeetingPrep } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';

export interface MeetingPrepCardProps {
  prep: MeetingPrep;
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('pl-PL', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Europe/Warsaw',
  });
}

export function MeetingPrepCard({ prep }: MeetingPrepCardProps) {
  const [briefExpanded, setBriefExpanded] = useState(true);
  const [contextExpanded, setContextExpanded] = useState(false);

  const { meeting, brief, participants_info, recent_context } = prep;

  return (
    <div
      className="rounded-lg border p-4 space-y-3"
      style={{
        backgroundColor: 'var(--surface)',
        borderColor: 'var(--border)',
        color: 'var(--text)',
      }}
    >
      {/* Header */}
      <div>
        <h3 className="font-semibold text-sm">{meeting.subject}</h3>
        <div
          className="flex items-center gap-3 mt-1 text-xs"
          style={{ color: 'var(--text-secondary)' }}
        >
          <span className="flex items-center gap-1">
            <Clock size={12} />
            {formatTime(meeting.start)} – {formatTime(meeting.end)}
          </span>
          {meeting.attendees && meeting.attendees.length > 0 && (
            <span className="flex items-center gap-1">
              <Users size={12} />
              {meeting.attendees.length} uczestników
            </span>
          )}
        </div>
      </div>

      {/* Participants */}
      {participants_info.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {participants_info.map((p) => (
            <div
              key={p.name}
              className="rounded-full px-2 py-0.5 text-xs"
              style={{
                backgroundColor: 'var(--surface-hover)',
                color: 'var(--text-secondary)',
              }}
            >
              {p.name}
              {p.role && (
                <span style={{ color: 'var(--accent)' }}> · {p.role}</span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Brief */}
      <div>
        <button
          type="button"
          onClick={() => setBriefExpanded(!briefExpanded)}
          className="flex items-center gap-1 text-xs font-medium mb-1"
          style={{ color: 'var(--accent)' }}
        >
          Brief
          {briefExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>
        {briefExpanded && (
          <div className="prose prose-sm prose-invert max-w-none text-xs" style={{ color: 'var(--text)' }}>
            <Markdown remarkPlugins={[remarkGfm]}>{brief}</Markdown>
          </div>
        )}
      </div>

      {/* Recent context */}
      {recent_context.length > 0 && (
        <div>
          <button
            type="button"
            onClick={() => setContextExpanded(!contextExpanded)}
            className="flex items-center gap-1 text-xs font-medium mb-1"
            style={{ color: 'var(--accent)' }}
          >
            Kontekst
            {contextExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
          {contextExpanded && (
            <ul className="list-disc list-inside space-y-1 text-xs" style={{ color: 'var(--text-secondary)' }}>
              {recent_context.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
