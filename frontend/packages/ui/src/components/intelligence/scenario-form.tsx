'use client';

import { useState } from 'react';
import { X } from 'lucide-react';
import { cn } from '../../lib/utils';

interface ScenarioFormProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (params: { title: string; description: string; scenario_type: 'risk' | 'opportunity' | 'strategic' }) => void;
  isSubmitting?: boolean;
}

const SCENARIO_TYPES: Array<{
  value: 'risk' | 'opportunity' | 'strategic';
  label: string;
  className: string;
  activeClassName: string;
}> = [
  { value: 'risk', label: 'Ryzyko', className: 'text-red-400', activeClassName: 'bg-red-400/10 border-red-400 text-red-400' },
  { value: 'opportunity', label: 'Szansa', className: 'text-emerald-400', activeClassName: 'bg-emerald-400/10 border-emerald-400 text-emerald-400' },
  { value: 'strategic', label: 'Strategiczny', className: 'text-blue-400', activeClassName: 'bg-blue-400/10 border-blue-400 text-blue-400' },
];

export function ScenarioForm({ isOpen, onClose, onSubmit, isSubmitting }: ScenarioFormProps) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [scenarioType, setScenarioType] = useState<'risk' | 'opportunity' | 'strategic'>('risk');

  if (!isOpen) return null;

  const isValid = title.trim().length > 0 && description.trim().length > 0;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!isValid || isSubmitting) return;
    onSubmit({ title: title.trim(), description: description.trim(), scenario_type: scenarioType });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Overlay */}
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />

      {/* Modal */}
      <div className="relative z-10 w-full max-w-lg rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6 shadow-xl mx-4">
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold text-[var(--text)]">Nowy scenariusz</h2>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--surface-hover)] transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Title */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-[var(--text-secondary)]">Tytuł</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Nazwa scenariusza"
              required
              className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-muted)] focus:border-[var(--accent)] focus:outline-none"
            />
          </div>

          {/* Description */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-[var(--text-secondary)]">Opis</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Opisz scenariusz..."
              required
              rows={4}
              className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-muted)] focus:border-[var(--accent)] focus:outline-none resize-none"
            />
          </div>

          {/* Type toggle */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-[var(--text-secondary)]">Typ</label>
            <div className="flex gap-2">
              {SCENARIO_TYPES.map((t) => (
                <button
                  key={t.value}
                  type="button"
                  onClick={() => setScenarioType(t.value)}
                  className={cn(
                    'rounded-lg border px-4 py-2 text-sm font-medium transition-colors',
                    scenarioType === t.value
                      ? t.activeClassName
                      : 'border-[var(--border)] text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]',
                  )}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={!isValid || isSubmitting}
            className={cn(
              'w-full rounded-lg px-4 py-2.5 text-sm font-medium transition-colors',
              'bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)]',
              'disabled:opacity-50 disabled:cursor-not-allowed',
            )}
          >
            {isSubmitting ? 'Tworzę...' : 'Utwórz scenariusz'}
          </button>
        </form>
      </div>
    </div>
  );
}
