'use client';

import { useState } from 'react';
import { CheckCircle, Plus, X } from 'lucide-react';
import type { OpenLoop } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';

interface OpenLoopsProps {
  loops: OpenLoop[];
  canAdd?: boolean;
  canClose?: boolean;
  onAdd?: (description: string) => void;
  onClose?: (loopId: number) => void;
}

export function OpenLoops({ loops, canAdd = false, canClose = false, onAdd, onClose }: OpenLoopsProps) {
  const [showInput, setShowInput] = useState(false);
  const [newDescription, setNewDescription] = useState('');

  const openLoops = loops.filter((l) => l.status !== 'closed');
  const closedLoops = loops.filter((l) => l.status === 'closed');

  const handleAdd = () => {
    if (!newDescription.trim()) return;
    onAdd?.(newDescription.trim());
    setNewDescription('');
    setShowInput(false);
  };

  return (
    <div className="space-y-4">
      {canAdd && !showInput && (
        <button
          onClick={() => setShowInput(true)}
          className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] transition-colors"
        >
          <Plus className="h-4 w-4" />
          Dodaj w\u0105tek
        </button>
      )}

      {showInput && (
        <div className="flex items-center gap-2">
          <input
            type="text"
            placeholder="Opis w\u0105tku..."
            value={newDescription}
            onChange={(e) => setNewDescription(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
            className="flex-1 rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-1.5 text-sm text-[var(--text)]"
            autoFocus
          />
          <button
            onClick={handleAdd}
            className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
          >
            Dodaj
          </button>
          <button
            onClick={() => { setShowInput(false); setNewDescription(''); }}
            className="text-[var(--text-muted)] hover:text-[var(--text)]"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {openLoops.length === 0 && closedLoops.length === 0 && (
        <p className="text-sm text-[var(--text-muted)]">Brak otwartych w\u0105tk\u00f3w.</p>
      )}

      {openLoops.length > 0 && (
        <ul className="space-y-2">
          {openLoops.map((loop) => (
            <li
              key={loop.id}
              className="flex items-start justify-between gap-3 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3"
            >
              <div className="min-w-0 flex-1">
                <p className="text-sm text-[var(--text)]">{loop.description}</p>
                <p className="mt-1 text-xs text-[var(--text-muted)]">
                  Utworzono: {loop.created_at.slice(0, 10)}
                </p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className="inline-flex rounded-full bg-amber-500/20 px-2 py-0.5 text-xs font-medium text-amber-400">
                  {loop.status}
                </span>
                {canClose && loop.status !== 'closed' && onClose && (
                  <button
                    onClick={() => onClose(loop.id)}
                    className="text-[var(--text-muted)] hover:text-emerald-400 transition-colors"
                    title="Zamknij"
                  >
                    <CheckCircle className="h-4 w-4" />
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {closedLoops.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]">
            Zamkni\u0119te
          </h4>
          <ul className="space-y-2">
            {closedLoops.map((loop) => (
              <li
                key={loop.id}
                className="flex items-start justify-between gap-3 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3 opacity-60"
              >
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-[var(--text)] line-through">{loop.description}</p>
                  <p className="mt-1 text-xs text-[var(--text-muted)]">
                    Zamkni\u0119to: {loop.closed_at?.slice(0, 10) ?? '-'}
                  </p>
                </div>
                <span className="inline-flex rounded-full bg-emerald-500/20 px-2 py-0.5 text-xs font-medium text-emerald-400">
                  zamkni\u0119ty
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
