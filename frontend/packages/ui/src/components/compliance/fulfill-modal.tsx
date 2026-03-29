'use client';

import { useState, useEffect, useCallback } from 'react';
import { X, Loader2 } from 'lucide-react';

export interface FulfillModalProps {
  obligationId: number;
  obligationTitle: string;
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (id: number, evidence?: string) => void;
  isSubmitting?: boolean;
}

export function FulfillModal({
  obligationId,
  obligationTitle,
  isOpen,
  onClose,
  onSubmit,
  isSubmitting = false,
}: FulfillModalProps) {
  const [evidence, setEvidence] = useState('');

  useEffect(() => {
    if (isOpen) setEvidence('');
  }, [isOpen]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    },
    [onClose],
  );

  useEffect(() => {
    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
      return () => document.removeEventListener('keydown', handleKeyDown);
    }
  }, [isOpen, handleKeyDown]);

  if (!isOpen) return null;

  const handleSubmit = () => {
    onSubmit(obligationId, evidence.trim() || undefined);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      style={{ backgroundColor: 'rgba(0, 0, 0, 0.6)' }}
    >
      <div
        className="relative w-full max-w-lg rounded-lg p-6 shadow-xl"
        style={{ backgroundColor: 'var(--bg)', border: '1px solid var(--border)' }}
      >
        {/* Header */}
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold" style={{ color: 'var(--text)' }}>
            Realizacja obowiązku
          </h2>
          <button
            onClick={onClose}
            className="rounded-md p-1 transition-colors"
            style={{ color: 'var(--text-secondary)' }}
          >
            <X size={18} />
          </button>
        </div>

        <p className="mb-4 text-sm" style={{ color: 'var(--text-secondary)' }}>
          {obligationTitle}
        </p>

        <div className="space-y-3">
          <label className="space-y-1">
            <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              Opis realizacji (opcjonalnie)
            </span>
            <textarea
              value={evidence}
              onChange={(e) => setEvidence(e.target.value)}
              rows={4}
              placeholder="Opisz co zostało zrobione w ramach realizacji tego obowiązku..."
              className="block w-full rounded-md border px-3 py-1.5 text-sm"
              style={{
                backgroundColor: 'var(--surface)',
                borderColor: 'var(--border)',
                color: 'var(--text)',
              }}
            />
          </label>
        </div>

        <div className="mt-6 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="rounded-md px-4 py-1.5 text-sm transition-colors"
            style={{ color: 'var(--text-secondary)' }}
          >
            Anuluj
          </button>
          <button
            onClick={handleSubmit}
            disabled={isSubmitting}
            className="flex items-center gap-2 rounded-md px-4 py-1.5 text-sm font-medium transition-colors disabled:opacity-50"
            style={{ backgroundColor: 'var(--accent)', color: '#fff' }}
          >
            {isSubmitting && <Loader2 size={14} className="animate-spin" />}
            Potwierdź realizację
          </button>
        </div>
      </div>
    </div>
  );
}
