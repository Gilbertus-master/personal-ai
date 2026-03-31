'use client';

import { useState, useMemo, useCallback } from 'react';
import { RbacGate, cn } from '@gilbertus/ui';
import {
  WeekView,
  MeetingPrepCard,
  MinutesCard,
  CalendarAnalyticsPanel,
  DeepWorkModal,
  EventDetailPopover,
} from '@gilbertus/ui/calendar';
import type { CalendarEvent, CalendarSuggestion } from '@gilbertus/api-client';
import {
  useCalendarEvents,
  useCalendarConflicts,
  useCalendarAnalytics,
  useMeetingPrep,
  useMeetingMinutes,
  useMeetingROI,
  useMeetingSuggestions,
  useBlockDeepWork,
  useGenerateMinutes,
} from '@/lib/hooks/use-calendar';
import { useCalendarStore } from '@/lib/stores/calendar-store';

const TABS = [
  { key: 'week' as const, label: 'Tydzien' },
  { key: 'prep' as const, label: 'Przygotowanie' },
  { key: 'minutes' as const, label: 'Protokoly' },
  { key: 'analytics' as const, label: 'Analityka' },
] as const;

/** Format week label from offset, e.g. "25.03 – 31.03.2026" */
function getWeekLabel(weekOffset: number): string {
  const now = new Date();
  const day = now.getDay();
  const monday = new Date(now);
  monday.setDate(now.getDate() - ((day + 6) % 7) + weekOffset * 7);
  monday.setHours(0, 0, 0, 0);

  const sunday = new Date(monday);
  sunday.setDate(monday.getDate() + 6);

  const fmt = (d: Date) =>
    d.toLocaleDateString('pl-PL', { day: '2-digit', month: '2-digit' });

  return `${fmt(monday)} \u2013 ${fmt(sunday)}.${sunday.getFullYear()}`;
}

export default function CalendarPage() {
  const store = useCalendarStore();
  const { weekOffset, activeTab, selectedEventId } = store;

  // Data hooks
  const events = useCalendarEvents();
  const conflicts = useCalendarConflicts();
  const analytics = useCalendarAnalytics();
  const prep = useMeetingPrep();
  const minutes = useMeetingMinutes();
  const roi = useMeetingROI();
  const suggestions = useMeetingSuggestions();

  // Mutations
  const deepWorkMutation = useBlockDeepWork();
  const generateMinutesMutation = useGenerateMinutes();

  // Local UI state
  const [deepWorkOpen, setDeepWorkOpen] = useState(false);
  const [expandedMinutesId, setExpandedMinutesId] = useState<number | null>(null);

  const weekLabel = useMemo(() => getWeekLabel(weekOffset), [weekOffset]);

  const selectedEvent = useMemo<CalendarEvent | null>(() => {
    if (!selectedEventId || !events.data?.events) return null;
    return events.data.events.find((e) => e.id === selectedEventId) ?? null;
  }, [selectedEventId, events.data]);

  const handleDeepWork = useCallback(
    (data: Parameters<typeof deepWorkMutation.mutate>[0]) => {
      deepWorkMutation.mutate(data, {
        onSuccess: () => setDeepWorkOpen(false),
      });
    },
    [deepWorkMutation],
  );

  const handleGenerateMinutes = useCallback(() => {
    generateMinutesMutation.mutate();
  }, [generateMinutesMutation]);

  return (
    <RbacGate permission="calendar">
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <h1 className="text-2xl font-bold text-[var(--text)]">Kalendarz</h1>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={store.prevWeek}
              className="rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors hover:brightness-110"
              style={{
                backgroundColor: 'var(--surface)',
                borderColor: 'var(--border)',
                color: 'var(--text)',
              }}
            >
              &larr;
            </button>
            <span
              className="text-sm font-medium min-w-[180px] text-center"
              style={{ color: 'var(--text)' }}
            >
              {weekLabel}
            </span>
            <button
              type="button"
              onClick={store.nextWeek}
              className="rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors hover:brightness-110"
              style={{
                backgroundColor: 'var(--surface)',
                borderColor: 'var(--border)',
                color: 'var(--text)',
              }}
            >
              &rarr;
            </button>
            <button
              type="button"
              onClick={() => store.setWeekOffset(0)}
              className="rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors hover:brightness-110"
              style={{
                backgroundColor: 'var(--surface)',
                borderColor: 'var(--border)',
                color: 'var(--text)',
              }}
            >
              Dzis
            </button>
            <RbacGate roles={['owner', 'ceo']}>
              <button
                type="button"
                onClick={() => setDeepWorkOpen(true)}
                className="rounded-lg px-4 py-1.5 text-sm font-medium transition-opacity hover:opacity-90"
                style={{ backgroundColor: 'var(--accent)', color: '#fff' }}
              >
                Deep Work
              </button>
            </RbacGate>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex gap-0 border-b border-[var(--border)]">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => store.setActiveTab(tab.key)}
              className={cn(
                'px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px',
                activeTab === tab.key
                  ? 'border-[var(--accent)] text-[var(--text)]'
                  : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text)]',
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Deep work success toast */}
        {deepWorkMutation.isSuccess && (
          <div className="rounded-lg border border-green-500/30 bg-green-500/10 px-4 py-2.5 text-sm text-green-400">
            Czas zablokowany
          </div>
        )}

        {/* Generate minutes success toast */}
        {generateMinutesMutation.isSuccess && (
          <div className="rounded-lg border border-green-500/30 bg-green-500/10 px-4 py-2.5 text-sm text-green-400">
            Protokoly wygenerowane
          </div>
        )}

        {/* Week Tab */}
        {activeTab === 'week' && (
          <WeekView
            events={events.data?.events ?? []}
            conflicts={conflicts.data?.conflicts ?? []}
            weekOffset={weekOffset}
            onEventClick={store.setSelectedEventId}
            isLoading={events.isLoading}
          />
        )}

        {/* Prep Tab */}
        {activeTab === 'prep' && (
          <RbacGate roles={['owner', 'ceo', 'board', 'director']}>
            <div className="space-y-4">
              {prep.isLoading && (
                <div className="space-y-3 animate-pulse">
                  {[1, 2, 3].map((i) => (
                    <div
                      key={i}
                      className="h-32 rounded-lg"
                      style={{ backgroundColor: 'var(--surface)' }}
                    />
                  ))}
                </div>
              )}
              {prep.data && Array.isArray(prep.data) && prep.data.length === 0 && (
                <div
                  className="text-center py-12 text-sm"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  Brak nadchodzacych spotkan z przygotowaniem
                </div>
              )}
              {prep.data &&
                Array.isArray(prep.data) &&
                prep.data.map((p: import('@gilbertus/api-client').MeetingPrep) => (
                  <MeetingPrepCard key={p.meeting.id} prep={p} />
                ))}
            </div>
          </RbacGate>
        )}

        {/* Minutes Tab */}
        {activeTab === 'minutes' && (
          <div className="space-y-4">
            <div className="flex justify-end">
              <button
                type="button"
                onClick={handleGenerateMinutes}
                disabled={generateMinutesMutation.isPending}
                className="rounded-lg px-4 py-2 text-sm font-medium transition-opacity hover:opacity-90 disabled:opacity-50"
                style={{ backgroundColor: 'var(--accent)', color: '#fff' }}
              >
                {generateMinutesMutation.isPending
                  ? 'Generowanie...'
                  : 'Generuj protokoly'}
              </button>
            </div>
            {minutes.isLoading && (
              <div className="space-y-3 animate-pulse">
                {[1, 2, 3].map((i) => (
                  <div
                    key={i}
                    className="h-16 rounded-lg"
                    style={{ backgroundColor: 'var(--surface)' }}
                  />
                ))}
              </div>
            )}
            {minutes.data &&
              Array.isArray(minutes.data) &&
              minutes.data.length === 0 && (
                <div
                  className="text-center py-12 text-sm"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  Brak protokolow
                </div>
              )}
            {minutes.data &&
              Array.isArray(minutes.data) &&
              minutes.data.map((m: import('@gilbertus/api-client').MeetingMinutes) => (
                <MinutesCard
                  key={m.id}
                  minutes={m}
                  expanded={expandedMinutesId === m.id}
                  onToggle={() =>
                    setExpandedMinutesId(
                      expandedMinutesId === m.id ? null : m.id,
                    )
                  }
                />
              ))}
          </div>
        )}

        {/* Analytics Tab */}
        {activeTab === 'analytics' && (
          <CalendarAnalyticsPanel
            analytics={analytics.data}
            roi={roi.data}
            isLoading={analytics.isLoading}
          />
        )}

        {/* Meeting Suggestions */}
        {suggestions.data?.suggestions &&
          suggestions.data.suggestions?.length > 0 && (
            <div
              className="rounded-lg border p-4"
              style={{
                backgroundColor: 'var(--surface)',
                borderColor: 'var(--border)',
              }}
            >
              <h3
                className="text-sm font-semibold mb-3"
                style={{ color: 'var(--text)' }}
              >
                Sugestie spotkan
              </h3>
              <div className="space-y-2">
                {suggestions.data.suggestions.map(
                  (s: CalendarSuggestion, i: number) => (
                    <div
                      key={i}
                      className="flex items-start gap-3 rounded-lg p-3"
                      style={{ backgroundColor: 'var(--surface-hover)' }}
                    >
                      <div className="flex-1">
                        <div
                          className="text-sm font-medium"
                          style={{ color: 'var(--text)' }}
                        >
                          {s.subject}
                        </div>
                        <div
                          className="text-xs mt-0.5"
                          style={{ color: 'var(--text-secondary)' }}
                        >
                          {s.reason}
                        </div>
                        {s.suggested_attendees?.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-1">
                            {s.suggested_attendees.map((name) => (
                              <span
                                key={name}
                                className="rounded-full px-2 py-0.5 text-[10px]"
                                style={{
                                  backgroundColor: 'var(--bg)',
                                  color: 'var(--text-secondary)',
                                }}
                              >
                                {name}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                      {s.priority && (
                        <span
                          className="text-[10px] font-medium px-2 py-0.5 rounded-full shrink-0"
                          style={{
                            backgroundColor: 'var(--accent)',
                            color: '#fff',
                          }}
                        >
                          {s.priority}
                        </span>
                      )}
                    </div>
                  ),
                )}
              </div>
            </div>
          )}

        {/* Deep Work Modal */}
        <DeepWorkModal
          open={deepWorkOpen}
          onClose={() => setDeepWorkOpen(false)}
          onSubmit={handleDeepWork}
          isLoading={deepWorkMutation.isPending}
        />

        {/* Event Detail Popover */}
        <EventDetailPopover
          event={selectedEvent}
          onClose={() => store.setSelectedEventId(null)}
        />
      </div>
    </RbacGate>
  );
}
