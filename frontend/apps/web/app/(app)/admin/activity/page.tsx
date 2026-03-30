'use client';

import { useState, useEffect, useMemo } from 'react';
import {
  Activity,
  Search,
  MessageSquare,
  Star,
  Ban,
  ArrowRight,
  ClipboardList,
  Eye,
  Filter,
  Loader2,
} from 'lucide-react';
import { cn } from '@gilbertus/ui';
import { getActivityLog } from '@gilbertus/api-client';
import type { ActivityLogRecord } from '@gilbertus/api-client';

const ACTION_META: Record<string, { icon: typeof Activity; label: string; color: string }> = {
  research: { icon: Search, label: 'Badanie', color: 'text-blue-400 bg-blue-400/10' },
  comment: { icon: MessageSquare, label: 'Komentarz', color: 'text-emerald-400 bg-emerald-400/10' },
  rate: { icon: Star, label: 'Ocena', color: 'text-amber-400 bg-amber-400/10' },
  task: { icon: ClipboardList, label: 'Zadanie', color: 'text-purple-400 bg-purple-400/10' },
  flag: { icon: Ban, label: 'Flaga', color: 'text-red-400 bg-red-400/10' },
  forward: { icon: ArrowRight, label: 'Przekazanie', color: 'text-cyan-400 bg-cyan-400/10' },
  view: { icon: Eye, label: 'Podgląd', color: 'text-[var(--text-muted)] bg-[var(--surface-hover)]' },
};

const FILTERS = [
  { value: null, label: 'Wszystkie' },
  { value: 'research', label: 'Badania' },
  { value: 'comment', label: 'Komentarze' },
  { value: 'flag', label: 'Flagi' },
  { value: 'task', label: 'Zadania' },
] as const;

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' });
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('pl-PL', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

function groupByDay(entries: ActivityLogRecord[]): Record<string, ActivityLogRecord[]> {
  const groups: Record<string, ActivityLogRecord[]> = {};
  for (const e of entries) {
    const day = e.created_at.slice(0, 10);
    (groups[day] ??= []).push(e);
  }
  return groups;
}

export default function AdminActivityPage() {
  const [entries, setEntries] = useState<ActivityLogRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getActivityLog({ limit: 200, action_type: filter ?? undefined })
      .then(setEntries)
      .catch(() => setEntries([]))
      .finally(() => setLoading(false));
  }, [filter]);

  const grouped = useMemo(() => groupByDay(entries), [entries]);
  const days = useMemo(() => Object.keys(grouped).sort().reverse(), [grouped]);

  const todayKey = new Date().toISOString().slice(0, 10);
  const todayCount = grouped[todayKey]?.length ?? 0;
  const flagCount = entries.filter((e) => e.action_type === 'flag').length;
  const taskCount = entries.filter((e) => e.action_type === 'task').length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-[var(--text)]">Aktywność</h1>
          <p className="text-sm text-[var(--text-secondary)]">
            Historia interakcji z insightami i alertami
          </p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
          <p className="text-2xl font-bold text-[var(--text)]">{todayCount}</p>
          <p className="text-xs text-[var(--text-secondary)]">Akcji dzisiaj</p>
        </div>
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
          <p className="text-2xl font-bold text-red-400">{flagCount}</p>
          <p className="text-xs text-[var(--text-secondary)]">Flagowań</p>
        </div>
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
          <p className="text-2xl font-bold text-purple-400">{taskCount}</p>
          <p className="text-xs text-[var(--text-secondary)]">Zadań</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2">
        <Filter className="h-4 w-4 text-[var(--text-secondary)]" />
        {FILTERS.map((f) => (
          <button
            key={f.value ?? 'all'}
            onClick={() => setFilter(f.value)}
            className={cn(
              'rounded-full px-3 py-1 text-xs font-medium transition-colors',
              filter === f.value
                ? 'bg-[var(--accent)] text-white'
                : 'bg-[var(--surface)] text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]',
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Timeline */}
      {loading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin text-[var(--accent)]" />
        </div>
      ) : entries.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-[var(--border)] bg-[var(--surface)] py-16">
          <Activity className="h-10 w-10 text-[var(--text-secondary)] opacity-40" />
          <p className="text-sm text-[var(--text-secondary)]">Brak aktywności do wyświetlenia</p>
        </div>
      ) : (
        <div className="space-y-6">
          {days.map((day) => (
            <div key={day}>
              <h3 className="mb-3 text-sm font-medium text-[var(--text-secondary)]">
                {day === todayKey ? 'Dzisiaj' : formatDate(grouped[day]![0]!.created_at)}
              </h3>
              <div className="space-y-1">
                {grouped[day]!.map((entry) => {
                  const meta = ACTION_META[entry.action_type] ?? ACTION_META.view!;
                  const Icon = meta.icon;
                  return (
                    <div
                      key={entry.id}
                      className="flex items-center gap-3 rounded-lg px-3 py-2 transition-colors hover:bg-[var(--surface-hover)]"
                    >
                      <span
                        className={cn(
                          'flex h-8 w-8 shrink-0 items-center justify-center rounded-full',
                          meta.color,
                        )}
                      >
                        <Icon className="h-4 w-4" />
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm text-[var(--text)]">
                          <span className="font-medium">{meta.label}</span>
                          {entry.item_title && (
                            <>
                              {' — '}
                              <span className="text-[var(--text-secondary)]">{entry.item_title}</span>
                            </>
                          )}
                        </p>
                        <p className="text-[10px] text-[var(--text-muted)]">
                          {entry.item_type}
                          {entry.item_context && ` · ${entry.item_context}`}
                        </p>
                      </div>
                      <span className="shrink-0 text-xs text-[var(--text-muted)]">
                        {formatTime(entry.created_at)}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
