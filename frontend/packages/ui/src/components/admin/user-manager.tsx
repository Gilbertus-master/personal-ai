'use client';

import { useState } from 'react';
import { Plus, X } from 'lucide-react';
import type { AdminUser, CreateUserRequest } from '@gilbertus/api-client';

interface UserManagerProps {
  users: AdminUser[];
  isLoading: boolean;
  onCreateUser: (data: CreateUserRequest) => void;
  isCreating: boolean;
}

const roleColors: Record<string, string> = {
  gilbertus_admin: 'bg-purple-600/20 text-purple-400',
  operator: 'bg-blue-600/20 text-blue-400',
  ceo: 'bg-yellow-600/20 text-yellow-300',
  board: 'bg-indigo-600/20 text-indigo-400',
  director: 'bg-teal-600/20 text-teal-400',
  manager: 'bg-green-600/20 text-green-400',
  specialist: 'bg-gray-600/20 text-gray-400',
};

const roleOptions = ['specialist', 'manager', 'director', 'board', 'ceo', 'operator'] as const;

export function UserManager({ users, isLoading, onCreateUser, isCreating }: UserManagerProps) {
  const [showDialog, setShowDialog] = useState(false);
  const [form, setForm] = useState<CreateUserRequest>({ email: '', name: '', role: 'specialist' });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.email || !form.name) return;
    onCreateUser({ ...form, department: form.department || undefined });
    setShowDialog(false);
    setForm({ email: '', name: '', role: 'specialist' });
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 animate-pulse rounded bg-[var(--surface)]" />
        <div className="h-64 animate-pulse rounded bg-[var(--surface)]" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold text-[var(--text)]">Użytkownicy</h2>
          <span className="rounded-full bg-[var(--surface)] px-2 py-0.5 text-xs text-[var(--text-secondary)]">
            {users.length}
          </span>
        </div>
        <button
          onClick={() => setShowDialog(true)}
          className="inline-flex items-center gap-1.5 rounded-md bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-white hover:opacity-90"
        >
          <Plus className="h-4 w-4" />
          Dodaj użytkownika
        </button>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] bg-[var(--surface)]">
              {['Imię', 'Email', 'Rola', 'Dział', 'Aktywny', 'Utworzony'].map((h) => (
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
            {users.map((u) => (
              <tr
                key={u.id}
                className="border-b border-[var(--border)] hover:bg-[var(--bg-hover)]"
              >
                <td className="px-4 py-2.5 text-[var(--text)]">{u.name}</td>
                <td className="px-4 py-2.5 text-[var(--text-secondary)]">{u.email}</td>
                <td className="px-4 py-2.5">
                  <span
                    className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${roleColors[u.role] ?? 'bg-gray-600/20 text-gray-400'}`}
                  >
                    {u.role}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-[var(--text-secondary)]">
                  {u.department ?? '\u2014'}
                </td>
                <td className="px-4 py-2.5">
                  <span
                    className={`inline-block h-2.5 w-2.5 rounded-full ${u.active ? 'bg-green-500' : 'bg-gray-500'}`}
                  />
                </td>
                <td className="px-4 py-2.5 text-[var(--text-secondary)]">
                  {new Date(u.created).toLocaleDateString('pl-PL')}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Create user dialog */}
      {showDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-md rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-base font-semibold text-[var(--text)]">Dodaj użytkownika</h3>
              <button
                onClick={() => setShowDialog(false)}
                className="text-[var(--text-secondary)] hover:text-[var(--text)]"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <form onSubmit={handleSubmit} className="space-y-3">
              <div>
                <label className="mb-1 block text-xs text-[var(--text-secondary)]">Imię</label>
                <input
                  type="text"
                  required
                  value={form.name}
                  onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                  className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-1.5 text-sm text-[var(--text)]"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-[var(--text-secondary)]">Email</label>
                <input
                  type="email"
                  required
                  value={form.email}
                  onChange={(e) => setForm((p) => ({ ...p, email: e.target.value }))}
                  className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-1.5 text-sm text-[var(--text)]"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-[var(--text-secondary)]">Rola</label>
                <select
                  value={form.role}
                  onChange={(e) => setForm((p) => ({ ...p, role: e.target.value }))}
                  className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-1.5 text-sm text-[var(--text)]"
                >
                  {roleOptions.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs text-[var(--text-secondary)]">
                  Dział (opcjonalny)
                </label>
                <input
                  type="text"
                  value={form.department ?? ''}
                  onChange={(e) => setForm((p) => ({ ...p, department: e.target.value }))}
                  className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-1.5 text-sm text-[var(--text)]"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowDialog(false)}
                  className="rounded-md border border-[var(--border)] px-3 py-1.5 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
                >
                  Anuluj
                </button>
                <button
                  type="submit"
                  disabled={isCreating}
                  className="rounded-md bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
                >
                  {isCreating ? 'Zapisywanie...' : 'Zapisz'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
