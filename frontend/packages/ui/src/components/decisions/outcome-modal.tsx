'use client';

import { useState, useEffect, useCallback } from 'react';
import { X, Loader2 } from 'lucide-react';
import type { OutcomeCreate } from '@gilbertus/api-client';
import { StarRating } from './star-rating';

export interface OutcomeModalProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: OutcomeCreate) => void;
  decisionText: string;
  isLoading?: boolean;
}

export function OutcomeModal({
  open,
  onClose,
  onSubmit,
  decisionText,
  isLoading = false,
}: OutcomeModalProps) {
  const [actualOutcome, setActualOutcome] = useState('');
  const [rating, setRating] = useState(3);
  const [outcomeDate, setOutcomeDate] = useState('');

  useEffect(() => {
    if (open) {
      setActualOutcome('');
      setRating(3);
      setOutcomeDate('');
    }
  }, [open]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    },
    [onClose],
  );

  useEffect(() => {
    if (open) {
      document.addEventListener('keydown', handleKeyDown);
      return () => document.removeEventListener('keydown', handleKeyDown);
    }
  }, [open, handleKeyDown]);

  if (!open) return null;

  const canSubmit = actualOutcome.trim().length > 0;

  const handleSubmit = () => {
    if (!canSubmit) return;
    const data: OutcomeCreate = {
      actual_outcome: actualOutcome.trim(),
      rating,
      outcome_date: outcomeDate || undefined,
    };
    onSubmit(data);
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
            Zapisz wynik
          </h2>
          <button
            onClick={onClose}
            className="rounded-md p-1 transition-colors"
            style={{ color: 'var(--text-secondary)' }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Decision reference */}
        <div
          className="mb-4 rounded-md p-3 text-sm"
          style={{ backgroundColor: 'var(--surface)', color: 'var(--text-secondary)' }}
        >
          {decisionText}
        </div>

        <div className="space-y-3">
          {/* Actual outcome */}
          <label className="space-y-1">
            <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              Rzeczywisty wynik *
            </span>
            <textarea
              value={actualOutcome}
              onChange={(e) => setActualOutcome(e.target.value)}
              rows={3}
              className="block w-full rounded-md border px-3 py-1.5 text-sm"
              style={{
                backgroundColor: 'var(--surface)',
                borderColor: 'var(--border)',
                color: 'var(--text)',
              }}
            />
          </label>

          {/* Rating + Date */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                Ocena
              </span>
              <div>
                <StarRating value={rating} onChange={setRating} size="md" />
              </div>
            </div>
            <label className="space-y-1">
              <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                Data wyniku
              </span>
              <input
                type="date"
                value={outcomeDate}
                onChange={(e) => setOutcomeDate(e.target.value)}
                className="block w-full rounded-md border px-3 py-1.5 text-sm"
                style={{
                  backgroundColor: 'var(--surface)',
                  borderColor: 'var(--border)',
                  color: 'var(--text)',
                }}
              />
            </label>
          </div>
        </div>

        {/* Submit */}
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
            disabled={!canSubmit || isLoading}
            className="flex items-center gap-2 rounded-md px-4 py-1.5 text-sm font-medium transition-colors disabled:opacity-50"
            style={{ backgroundColor: 'var(--accent)', color: '#fff' }}
          >
            {isLoading && <Loader2 size={14} className="animate-spin" />}
            Zapisz wynik
          </button>
        </div>
      </div>
    </div>
  );
}
