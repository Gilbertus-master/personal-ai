'use client';

import { useState, useMemo } from 'react';
import { Plus, ChevronDown, ChevronRight, ListTodo } from 'lucide-react';
import type {
  OperatorTask,
  OmniusTenant,
  CreateTaskRequest,
  UpdateTaskRequest,
} from '@gilbertus/api-client';

interface OperatorTasksProps {
  activeTenant: OmniusTenant;
  onTenantChange: (t: OmniusTenant) => void;
  tasks: OperatorTask[];
  isLoading: boolean;
  onCreate: (data: CreateTaskRequest) => void;
  isCreating: boolean;
  onUpdateStatus: (taskId: number, data: UpdateTaskRequest) => void;
}

const statusConfig: Record<string, { label: string; className: string }> = {
  pending: { label: 'Oczekuje', className: 'bg-gray-600/20 text-gray-400' },
  in_progress: { label: 'W toku', className: 'bg-blue-600/20 text-blue-400' },
  done: { label: 'Gotowe', className: 'bg-green-600/20 text-green-400' },
  blocked: { label: 'Zablokowane', className: 'bg-red-600/20 text-red-400' },
};

const statusOptions: Array<OperatorTask['status']> = ['pending', 'in_progress', 'done', 'blocked'];

function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString('pl-PL', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function TenantTabs({
  active,
  onChange,
}: {
  active: OmniusTenant;
  onChange: (t: OmniusTenant) => void;
}) {
  const tenants: { id: OmniusTenant; label: string }[] = [
    { id: 'reh', label: 'REH' },
    { id: 'ref', label: 'REF' },
  ];
  return (
    <div className="flex gap-1 rounded-lg bg-[var(--bg)] p-1">
      {tenants.map((t) => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
            active === t.id
              ? 'bg-[var(--accent)] text-white'
              : 'text-[var(--text-secondary)] hover:text-[var(--text)]'
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function OperatorTasks({
  activeTenant,
  onTenantChange,
  tasks,
  isLoading,
  onCreate,
  isCreating,
  onUpdateStatus,
}: OperatorTasksProps) {
  const [showCreate, setShowCreate] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [form, setForm] = useState({ title: '', description: '', assigned_to: '' });

  const sorted = useMemo(
    () => [...tasks].sort((a, b) => new Date(b.created).getTime() - new Date(a.created).getTime()),
    [tasks],
  );

  function handleCreate() {
    if (!form.title.trim()) return;
    onCreate({
      title: form.title,
      description: form.description,
      assigned_to: form.assigned_to || undefined,
    });
    setForm({ title: '', description: '', assigned_to: '' });
    setShowCreate(false);
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-10 w-32 animate-pulse rounded bg-[var(--surface)]" />
        <div className="h-64 animate-pulse rounded bg-[var(--surface)]" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <TenantTabs active={activeTenant} onChange={onTenantChange} />
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 rounded-md bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-white hover:opacity-90"
        >
          <Plus className="h-4 w-4" />
          Nowe zadanie
        </button>
      </div>

      {/* Create dialog */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-md rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 shadow-xl">
            <h3 className="mb-4 text-lg font-semibold text-[var(--text)]">Nowe zadanie</h3>
            <div className="space-y-3">
              <input
                type="text"
                placeholder="Tytuł"
                value={form.title}
                onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-muted)]"
              />
              <textarea
                placeholder="Opis"
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                rows={3}
                className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-muted)]"
              />
              <input
                type="text"
                placeholder="Przypisz do (opcjonalnie)"
                value={form.assigned_to}
                onChange={(e) => setForm((f) => ({ ...f, assigned_to: e.target.value }))}
                className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-muted)]"
              />
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={() => setShowCreate(false)}
                className="rounded-md px-3 py-1.5 text-sm text-[var(--text-secondary)] hover:text-[var(--text)]"
              >
                Anuluj
              </button>
              <button
                onClick={handleCreate}
                disabled={isCreating || !form.title.trim()}
                className="rounded-md bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
              >
                {isCreating ? 'Tworzenie...' : 'Utwórz'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Table */}
      {sorted.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-[var(--border)] py-16 text-[var(--text-secondary)]">
          <ListTodo className="h-8 w-8" />
          <p className="text-sm">Brak zadań</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] bg-[var(--surface)]">
                <th className="w-8 px-2 py-2.5" />
                {['ID', 'Tytuł', 'Status', 'Przypisany', 'Utworzony', 'Ukończony'].map((h) => (
                  <th
                    key={h}
                    className="px-4 py-2.5 text-left text-xs font-semibold uppercase text-[var(--text-secondary)]"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.map((task) => {
                const expanded = expandedId === task.id;
                const cfg = statusConfig[task.status];
                return (
                  <>
                    <tr
                      key={task.id}
                      className="border-b border-[var(--border)] hover:bg-[var(--bg-hover)]"
                    >
                      <td className="px-2 py-2.5">
                        <button
                          onClick={() => setExpandedId(expanded ? null : task.id)}
                          className="text-[var(--text-secondary)] hover:text-[var(--text)]"
                        >
                          {expanded ? (
                            <ChevronDown className="h-4 w-4" />
                          ) : (
                            <ChevronRight className="h-4 w-4" />
                          )}
                        </button>
                      </td>
                      <td className="px-4 py-2.5 font-mono text-[var(--text-secondary)]">
                        {task.id}
                      </td>
                      <td className="px-4 py-2.5 text-[var(--text)]">{task.title}</td>
                      <td className="px-4 py-2.5">
                        <select
                          value={task.status}
                          onChange={(e) =>
                            onUpdateStatus(task.id, {
                              status: e.target.value as OperatorTask['status'],
                            })
                          }
                          className={`rounded-full border-0 px-2 py-0.5 text-xs font-medium ${cfg.className}`}
                        >
                          {statusOptions.map((s) => (
                            <option key={s} value={s}>
                              {statusConfig[s].label}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="px-4 py-2.5 text-[var(--text)]">{task.assigned_to}</td>
                      <td className="whitespace-nowrap px-4 py-2.5 text-[var(--text-secondary)]">
                        {formatTimestamp(task.created)}
                      </td>
                      <td className="whitespace-nowrap px-4 py-2.5 text-[var(--text-secondary)]">
                        {task.completed ? formatTimestamp(task.completed) : '—'}
                      </td>
                    </tr>
                    {expanded && (
                      <tr key={`${task.id}-detail`} className="border-b border-[var(--border)]">
                        <td colSpan={7} className="bg-[var(--bg)] px-6 py-4">
                          <div className="space-y-2 text-sm">
                            <div>
                              <span className="font-medium text-[var(--text-secondary)]">
                                Opis:{' '}
                              </span>
                              <span className="text-[var(--text)]">
                                {task.description || '—'}
                              </span>
                            </div>
                            {task.result && (
                              <div>
                                <span className="font-medium text-[var(--text-secondary)]">
                                  Wynik:{' '}
                                </span>
                                <span className="text-[var(--text)]">{task.result}</span>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
