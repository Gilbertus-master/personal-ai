'use client';

import { useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import {
  ChevronLeft,
  ChevronRight,
  Calendar as CalendarIcon,
  RefreshCw,
  Clock,
  CheckCircle2,
  Circle,
  MessageSquare,
  Sunrise,
} from 'lucide-react';
import { useRole } from '@gilbertus/rbac';
import { RbacGate } from '@gilbertus/ui';
import { MarkdownRenderer } from '@gilbertus/ui';
import { useBrief } from '@/lib/hooks/use-dashboard';
import { useQueryClient } from '@tanstack/react-query';
import { cn } from '@gilbertus/ui';

function formatDatePl(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('pl-PL', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

function formatDateShort(date: Date): string {
  return date.toISOString().split('T')[0];
}

function addDays(dateStr: string, days: number): string {
  const d = new Date(dateStr + 'T00:00:00');
  d.setDate(d.getDate() + days);
  return formatDateShort(d);
}

function isToday(dateStr: string): boolean {
  return dateStr === formatDateShort(new Date());
}

interface BriefTask {
  id: string;
  title: string;
  description: string;
  priority: 'HIGH' | 'MEDIUM' | 'LOW';
}

function extractTasks(text: string): BriefTask[] {
  const tasks: BriefTask[] = [];
  // Match "→ **Akcja:**" patterns from brief text
  const actionPattern = /\*\*(\d+)\.\s*(.+?)(?:\s*\(([^)]*)\))?\*\*\n([\s\S]*?)→\s*\*\*Akcja:\*\*\s*(.+?)(?:\n|$)/g;
  let match;
  while ((match = actionPattern.exec(text)) !== null) {
    const priority = match[3]?.includes('HIGH') ? 'HIGH' as const
      : match[3]?.includes('DEADLINE') ? 'HIGH' as const
      : 'MEDIUM' as const;
    tasks.push({
      id: `task-${match[1]}`,
      title: match[2].trim(),
      description: match[5].trim(),
      priority,
    });
  }

  // Fallback: also match simpler "→ **Akcja:**" blocks
  if (tasks.length === 0) {
    const simplePattern = /→\s*\*\*Akcja:\*\*\s*(.+?)(?:\n|$)/g;
    let idx = 0;
    while ((match = simplePattern.exec(text)) !== null) {
      idx++;
      tasks.push({
        id: `task-${idx}`,
        title: `Zadanie ${idx}`,
        description: match[1].trim(),
        priority: 'MEDIUM',
      });
    }
  }
  return tasks;
}

const PRIORITY_STYLE: Record<string, string> = {
  HIGH: 'border-l-red-500 bg-red-500/5',
  MEDIUM: 'border-l-amber-500 bg-amber-500/5',
  LOW: 'border-l-blue-500 bg-blue-500/5',
};

const PRIORITY_LABEL: Record<string, string> = {
  HIGH: 'Pilne',
  MEDIUM: 'Ważne',
  LOW: 'Normalne',
};

function BriefContent() {
  const today = formatDateShort(new Date());
  const [selectedDate, setSelectedDate] = useState(today);
  const [completedTasks, setCompletedTasks] = useState<Set<string>>(new Set());
  const queryClient = useQueryClient();
  const router = useRouter();

  const brief = useBrief({ date: isToday(selectedDate) ? undefined : selectedDate });

  const tasks = useMemo(() => {
    if (!brief.data?.text) return [];
    return extractTasks(brief.data.text);
  }, [brief.data?.text]);

  const handlePrevDay = () => setSelectedDate((d) => addDays(d, -1));
  const handleNextDay = () => {
    if (!isToday(selectedDate)) setSelectedDate((d) => addDays(d, 1));
  };
  const handleToday = () => setSelectedDate(today);
  const handleRefresh = () => queryClient.invalidateQueries({ queryKey: ['brief', isToday(selectedDate) ? 'today' : selectedDate] });

  const toggleTask = (taskId: string) => {
    setCompletedTasks((prev) => {
      const next = new Set(prev);
      if (next.has(taskId)) next.delete(taskId);
      else next.add(taskId);
      return next;
    });
  };

  const handleAskAboutBrief = () => {
    router.push('/chat');
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <Sunrise className="h-7 w-7 text-amber-400" />
          <h1 className="text-2xl font-bold text-[var(--text)]">Poranny Brief</h1>
        </div>

        {/* Date navigator */}
        <div className="flex items-center gap-2">
          <button
            onClick={handlePrevDay}
            className="rounded-md p-2 text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] transition-colors"
            aria-label="Poprzedni dzień"
          >
            <ChevronLeft className="h-5 w-5" />
          </button>

          <button
            onClick={handleToday}
            className={cn(
              'flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors',
              isToday(selectedDate)
                ? 'bg-[var(--accent)] text-white'
                : 'bg-[var(--surface)] text-[var(--text)] border border-[var(--border)] hover:bg-[var(--surface-hover)]',
            )}
          >
            <CalendarIcon className="h-4 w-4" />
            {isToday(selectedDate) ? 'Dziś' : formatDatePl(selectedDate)}
          </button>

          <button
            onClick={handleNextDay}
            disabled={isToday(selectedDate)}
            className="rounded-md p-2 text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] transition-colors disabled:opacity-30"
            aria-label="Następny dzień"
          >
            <ChevronRight className="h-5 w-5" />
          </button>

          <div className="ml-2 flex items-center gap-1">
            <button
              onClick={handleRefresh}
              disabled={brief.isLoading}
              className="rounded-md p-2 text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] transition-colors disabled:opacity-50"
              aria-label="Odśwież"
            >
              <RefreshCw className={cn('h-4 w-4', brief.isLoading && 'animate-spin')} />
            </button>
            <button
              onClick={handleAskAboutBrief}
              className="rounded-md p-2 text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] transition-colors"
              aria-label="Zapytaj Gilbertusa o brief"
            >
              <MessageSquare className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Date display for non-today */}
      {!isToday(selectedDate) && (
        <p className="text-sm text-[var(--text-secondary)]">
          Przeglądasz brief z: <span className="font-medium text-[var(--text)]">{formatDatePl(selectedDate)}</span>
        </p>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Main brief content */}
        <div className="xl:col-span-2">
          <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)]">
            {/* Meta header */}
            {brief.data && !brief.isLoading && (
              <div className="flex items-center gap-4 border-b border-[var(--border)] px-5 py-3">
                <span className={cn(
                  'inline-block h-2 w-2 rounded-full',
                  brief.data.status === 'generated' ? 'bg-green-500' : 'bg-gray-400',
                )} />
                <span className="text-xs text-[var(--text-secondary)]">
                  {brief.data.events_count ?? 0} wydarzeń
                </span>
                <span className="text-xs text-[var(--text-secondary)]">
                  {brief.data.entities_count ?? 0} encji
                </span>
                <span className="text-xs text-[var(--text-secondary)]">
                  {brief.data.open_loops_count ?? 0} otwartych wątków
                </span>
                {brief.data.meta?.latency_ms != null && (
                  <span className="text-xs text-[var(--text-secondary)] ml-auto">
                    <Clock className="inline h-3 w-3 mr-1" />
                    {brief.data.meta.latency_ms.toFixed(0)} ms
                  </span>
                )}
              </div>
            )}

            {/* Content */}
            {brief.isLoading ? (
              <div className="space-y-3 p-5">
                {Array.from({ length: 8 }).map((_, i) => (
                  <div
                    key={i}
                    className="h-4 animate-pulse rounded bg-[var(--surface-hover)]"
                    style={{ width: `${60 + Math.random() * 40}%` }}
                  />
                ))}
              </div>
            ) : brief.error ? (
              <div className="p-5">
                <p className="text-sm text-red-400">Nie udało się załadować briefu: {brief.error.message}</p>
                <button
                  onClick={handleRefresh}
                  className="mt-2 text-sm text-[var(--accent)] hover:underline"
                >
                  Spróbuj ponownie
                </button>
              </div>
            ) : brief.data?.text ? (
              <div className="max-h-[75vh] overflow-y-auto p-5">
                <MarkdownRenderer content={brief.data.text} />
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center gap-3 p-12 text-[var(--text-secondary)]">
                <Sunrise className="h-8 w-8" />
                <p className="text-sm">Brief na ten dzień nie został jeszcze wygenerowany</p>
              </div>
            )}
          </div>
        </div>

        {/* Right sidebar: Tasks */}
        <div className="space-y-4">
          <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
            <h2 className="mb-4 text-sm font-semibold text-[var(--text)]">
              Zadania na dziś
              {tasks.length > 0 && (
                <span className="ml-2 text-xs text-[var(--text-secondary)]">
                  {completedTasks.size}/{tasks.length}
                </span>
              )}
            </h2>

            {tasks.length === 0 ? (
              <p className="text-xs text-[var(--text-secondary)]">
                {brief.isLoading ? 'Ładowanie...' : 'Brak wyodrębnionych zadań'}
              </p>
            ) : (
              <div className="space-y-3">
                {tasks.map((task) => {
                  const done = completedTasks.has(task.id);
                  return (
                    <div
                      key={task.id}
                      className={cn(
                        'rounded-md border-l-4 p-3 transition-all',
                        PRIORITY_STYLE[task.priority],
                        done && 'opacity-50',
                      )}
                    >
                      <div className="flex items-start gap-2">
                        <button
                          onClick={() => toggleTask(task.id)}
                          className="mt-0.5 shrink-0"
                        >
                          {done ? (
                            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                          ) : (
                            <Circle className="h-4 w-4 text-[var(--text-secondary)]" />
                          )}
                        </button>
                        <div className="min-w-0">
                          <p className={cn(
                            'text-xs font-semibold text-[var(--text)]',
                            done && 'line-through',
                          )}>
                            {task.title}
                          </p>
                          <p className="mt-1 text-xs text-[var(--text-secondary)]">
                            {task.description}
                          </p>
                          <span className={cn(
                            'mt-1.5 inline-block rounded-full px-2 py-0.5 text-[10px] font-medium',
                            task.priority === 'HIGH' ? 'bg-red-500/10 text-red-400'
                              : task.priority === 'MEDIUM' ? 'bg-amber-500/10 text-amber-400'
                              : 'bg-blue-500/10 text-blue-400',
                          )}>
                            {PRIORITY_LABEL[task.priority]}
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Quick date picker */}
          <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
            <h2 className="mb-3 text-sm font-semibold text-[var(--text)]">Historia briefów</h2>
            <div className="space-y-1">
              {Array.from({ length: 7 }).map((_, i) => {
                const date = addDays(today, -i);
                const active = date === selectedDate;
                return (
                  <button
                    key={date}
                    onClick={() => setSelectedDate(date)}
                    className={cn(
                      'flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors',
                      active
                        ? 'bg-[var(--accent)] bg-opacity-15 text-[var(--accent)] font-medium'
                        : 'text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text)]',
                    )}
                  >
                    <CalendarIcon className="h-3.5 w-3.5 shrink-0" />
                    {i === 0 ? 'Dziś' : i === 1 ? 'Wczoraj' : formatDatePl(date)}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function BriefPage() {
  return (
    <RbacGate
      roles={['owner', 'ceo', 'board', 'gilbertus_admin']}
      fallback={
        <div className="flex items-center justify-center h-full">
          <p className="text-[var(--text-secondary)]">Brak dostępu do briefu</p>
        </div>
      }
    >
      <BriefContent />
    </RbacGate>
  );
}
