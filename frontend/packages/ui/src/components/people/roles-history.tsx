'use client';

import { useState } from 'react';
import { Plus, X } from 'lucide-react';
import type { RoleHistory } from '@gilbertus/api-client';

interface RolesHistoryProps {
  roles: RoleHistory[];
  canAdd?: boolean;
  onAdd?: (data: { role: string; organization?: string; date_from?: string; date_to?: string; notes?: string }) => void;
}

export function RolesHistory({ roles, canAdd = false, onAdd }: RolesHistoryProps) {
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    role: '',
    organization: '',
    date_from: '',
    date_to: '',
    notes: '',
  });

  const handleSubmit = () => {
    if (!formData.role.trim()) return;
    onAdd?.({
      role: formData.role.trim(),
      organization: formData.organization || undefined,
      date_from: formData.date_from || undefined,
      date_to: formData.date_to || undefined,
      notes: formData.notes || undefined,
    });
    setFormData({ role: '', organization: '', date_from: '', date_to: '', notes: '' });
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
          Dodaj rol\u0119
        </button>
      )}

      {showForm && (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-[var(--text)]">Nowa rola</span>
            <button onClick={() => setShowForm(false)} className="text-[var(--text-muted)] hover:text-[var(--text)]">
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <input
              type="text"
              placeholder="Rola *"
              value={formData.role}
              onChange={(e) => setFormData((f) => ({ ...f, role: e.target.value }))}
              className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-1.5 text-sm text-[var(--text)]"
            />
            <input
              type="text"
              placeholder="Organizacja"
              value={formData.organization}
              onChange={(e) => setFormData((f) => ({ ...f, organization: e.target.value }))}
              className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-1.5 text-sm text-[var(--text)]"
            />
            <input
              type="date"
              value={formData.date_from}
              onChange={(e) => setFormData((f) => ({ ...f, date_from: e.target.value }))}
              className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-1.5 text-sm text-[var(--text)]"
              placeholder="Od"
            />
            <input
              type="date"
              value={formData.date_to}
              onChange={(e) => setFormData((f) => ({ ...f, date_to: e.target.value }))}
              className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-1.5 text-sm text-[var(--text)]"
              placeholder="Do"
            />
          </div>
          <input
            type="text"
            placeholder="Notatki"
            value={formData.notes}
            onChange={(e) => setFormData((f) => ({ ...f, notes: e.target.value }))}
            className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-1.5 text-sm text-[var(--text)]"
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

      {roles.length === 0 && (
        <p className="text-sm text-[var(--text-muted)]">Brak historii r\u00f3l.</p>
      )}

      <ul className="space-y-3">
        {roles.map((role) => (
          <li
            key={role.id}
            className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3 space-y-1"
          >
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-[var(--text)]">{role.role}</span>
              {role.organization && (
                <span className="text-xs text-[var(--text-secondary)]">{role.organization}</span>
              )}
            </div>
            <p className="text-xs text-[var(--text-muted)]">
              {role.date_from ?? '?'} — {role.date_to ?? 'obecnie'}
            </p>
            {role.notes && (
              <p className="text-xs text-[var(--text-secondary)]">{role.notes}</p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
