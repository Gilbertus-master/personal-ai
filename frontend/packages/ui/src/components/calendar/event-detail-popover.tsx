'use client';

import { useEffect, useRef } from 'react';
import { X, MapPin, Video, Users, User } from 'lucide-react';
import type { CalendarEvent } from '@gilbertus/api-client';

export interface EventDetailPopoverProps {
  event: CalendarEvent | null;
  onClose: () => void;
  anchorEl?: HTMLElement;
}

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('pl-PL', {
    weekday: 'short',
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Europe/Warsaw',
  });
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('pl-PL', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Europe/Warsaw',
  });
}

export function EventDetailPopover({
  event,
  onClose,
  anchorEl,
}: EventDetailPopoverProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onClose();
      }
    }
    if (event) {
      document.addEventListener('mousedown', handleClick);
      return () => document.removeEventListener('mousedown', handleClick);
    }
  }, [event, onClose]);

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    if (event) {
      document.addEventListener('keydown', handleKey);
      return () => document.removeEventListener('keydown', handleKey);
    }
  }, [event, onClose]);

  if (!event) return null;

  // Position relative to anchor if available
  const style: React.CSSProperties = {
    backgroundColor: 'var(--bg)',
    borderColor: 'var(--border)',
    color: 'var(--text)',
  };

  if (anchorEl) {
    const rect = anchorEl.getBoundingClientRect();
    style.position = 'fixed';
    style.top = rect.bottom + 8;
    style.left = Math.min(rect.left, window.innerWidth - 320);
    style.zIndex = 60;
  } else {
    style.position = 'fixed';
    style.top = '50%';
    style.left = '50%';
    style.transform = 'translate(-50%, -50%)';
    style.zIndex = 60;
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-50"
        style={{ backgroundColor: 'rgba(0,0,0,0.3)' }}
      />
      <div
        ref={ref}
        className="w-80 rounded-xl border shadow-xl p-4 space-y-3"
        style={style}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-2">
          <h3 className="text-sm font-semibold leading-tight">
            {event.subject}
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="p-0.5 rounded shrink-0"
            style={{ color: 'var(--text-secondary)' }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Time */}
        <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>
          {formatDateTime(event.start)} – {formatTime(event.end)}
        </div>

        {/* Organizer */}
        {event.organizer && (
          <div className="flex items-center gap-2 text-xs">
            <User size={14} style={{ color: 'var(--accent)' }} />
            <span>{event.organizer}</span>
          </div>
        )}

        {/* Location / Online */}
        {(event.location || event.is_online) && (
          <div className="flex items-center gap-2 text-xs">
            {event.is_online ? (
              <Video size={14} style={{ color: 'var(--accent)' }} />
            ) : (
              <MapPin size={14} style={{ color: 'var(--accent)' }} />
            )}
            <span>{event.location ?? 'Spotkanie online'}</span>
          </div>
        )}

        {/* Attendees */}
        {event.attendees && event.attendees.length > 0 && (
          <div>
            <div
              className="flex items-center gap-1 text-xs font-medium mb-1"
              style={{ color: 'var(--text-secondary)' }}
            >
              <Users size={12} />
              Uczestnicy ({event.attendees.length})
            </div>
            <div className="flex flex-wrap gap-1">
              {event.attendees.map((name) => (
                <span
                  key={name}
                  className="rounded-full px-2 py-0.5 text-[10px]"
                  style={{
                    backgroundColor: 'var(--surface-hover)',
                    color: 'var(--text-secondary)',
                  }}
                >
                  {name}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </>
  );
}
