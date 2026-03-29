'use client';

import { useState } from 'react';
import { Plus, X } from 'lucide-react';
import type { PersonTimelineEvent } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';

interface PersonTimelineProps {
  events: PersonTimelineEvent[];
  canAdd?: boolean;
  onAdd?: (data: { event_date: string; event_type?: string; description: string; source?: string }) => void;
}

const EVENT_TYPE_COLORS: Record<string, string> = {
  meeting: 'bg-blue-500/20 text-blue-400',
  email: 'bg-purple-500/20 text-purple-400',
  call: 'bg-green-500/20 text-green-400',
  decision: 'bg-amber-500/20 text-amber-400',
  note: 'bg-zinc-500/20 text-zinc-400',
};

const VISIBLE_LIMIT = 20;

export function PersonTimeline({ events, canAdd = false, onAdd }: PersonTimelineProps) {
  const [showForm, setShowForm] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const [formData, setFormData] = useState({
    event_date: new Date().toISOString().slice(0, 10),
    event_type: '',
    description: '',
    source: '',
  });

  const sorted = [...events].sort(
    (a, b) => new Date(b.event_date).getTime() - new Date(a.event_date).getTime(),
  );
  const visible = showAll ? sorted : sorted.slice(0, VISIBLE_LIMIT);

  const handleSubmit = () => {
    if (!formData.description.trim() || !formData.event_date) return;
    onAdd?.({
      event_date: formData.event_date,
      event_type: formData.event_type || undefined,
      description: formData.description.trim(),
      source: formData.source || undefined,
    });
    setFormData({ event_date: new Date().toISOString().slice(0, 10), event_type: '', description: '', source: '' });
    setShowForm(false);
  };

  return (
    <div className="space-y-4">
      {canAdd && !showForm && (
        <button
          onClick={() => setShowForm(true)}
          className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] transition-colors"
        >
          <Plus className="h-4 w-4" />
          Dodaj wydarzenie
        </button>
      )}

      {showForm && (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-[var(--text)]">Nowe wydarzenie</span>
            <button onClick={() => setShowForm(false)} className="text-[var(--text-muted)] hover:text-[var(--text)]">
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <input
              type="date"
              value={formData.event_date}
              onChange={(e) => setFormData((f) => ({ ...f, event_date: e.target.value }))}
              className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-1.5 text-sm text-[var(--text)]"
            />
            <select
              value={formData.event_type}
              onChange={(e) => setFormData((f) => ({ ...f, event_type: e.target.value }))}
              className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-1.5 text-sm text-[var(--text)]"
            >
              <option value="">Typ (opcjonalnie)</option>
              <option value="meeting">Spotkanie</option>
              <option value="email">Email</option>
              <option value="call">Telefon</option>
              <option value="decision">Decyzja</option>
              <option value="note">Notatka</option>
            </select>
          </div>
          <textarea
            placeholder="Opis wydarzenia..."
            value={formData.description}
            onChange={(e) => setFormData((f) => ({ ...f, description: e.target.value }))}
            rows={2}
            className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-1.5 text-sm text-[var(--text)] resize-none"
          />
          <div className="flex items-center gap-2">
            <button
              onClick={handleSubmit}
              className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
            >
              Zapisz
            </button>
            <button
              onClick={() => setShowForm(false)}
              className="rounded-md border border-[var(--border)] px-3 py-1.5 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] transition-colors"
            >
              Anuluj
            </button>
          </div>
        </div>
      )}

      {visible.length === 0 && (
        <p className="text-sm text-[var(--text-muted)]">Brak wydarze\u0144 w historii.</p>
      )}

      <div className="relative space-y-0">
        {visible.map((event, idx) => {
          const typeColor = event.event_type
            ? EVENT_TYPE_COLORS[event.event_type] ?? 'bg-zinc-500/20 text-zinc-400'
            : null;

          return (
            <div key={event.id} className="relative flex gap-4 pb-6 last:pb-0">
              {/* Connector line */}
              {idx < visible.length - 1 && (
                <div className="absolute left-[7px] top-5 bottom-0 w-px bg-[var(--border)]" />
              )}

              {/* Dot */}
              <div className="relative mt-1.5 h-3.5 w-3.5 shrink-0 rounded-full border-2 border-[var(--border)] bg-[var(--surface)]" />

              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs font-medium text-[var(--text-muted)]">
                    {event.event_date}
                  </span>
                  {typeColor && (
                    <span className={cn('inline-flex rounded-full px-2 py-0.5 text-xs font-medium', typeColor)}>
                      {event.event_type}
                    </span>
                  )}
                  {event.source && (
                    <span className="inline-flex rounded bg-[var(--bg-hover)] px-1.5 py-0.5 text-xs text-[var(--text-muted)]">
                      {event.source}
                    </span>
                  )}
                </div>
                <p className="text-sm text-[var(--text)]">{event.description}</p>
              </div>
            </div>
          );
        })}
      </div>

      {!showAll && sorted.length > VISIBLE_LIMIT && (
        <button
          onClick={() => setShowAll(true)}
          className="text-sm text-blue-400 hover:text-blue-300 transition-colors"
        >
          Poka\u017c wi\u0119cej ({sorted.length - VISIBLE_LIMIT})
        </button>
      )}
    </div>
  );
}
