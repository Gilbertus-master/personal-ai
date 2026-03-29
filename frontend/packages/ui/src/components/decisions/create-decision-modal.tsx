'use client';

import { useState, useEffect, useCallback } from 'react';
import { X, Loader2 } from 'lucide-react';
import type { DecisionCreate, DecisionArea } from '@gilbertus/api-client';
import { ConfidenceSlider } from './confidence-slider';

export interface CreateDecisionModalProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: DecisionCreate) => void;
  isLoading?: boolean;
}

const DECISION_AREAS: { value: DecisionArea; label: string }[] = [
  { value: 'business', label: 'Biznes' },
  { value: 'trading', label: 'Trading' },
  { value: 'relationships', label: 'Relacje' },
  { value: 'wellbeing', label: 'Wellbeing' },
  { value: 'general', label: 'Ogólne' },
];

export function CreateDecisionModal({
  open,
  onClose,
  onSubmit,
  isLoading = false,
}: CreateDecisionModalProps) {
  const [decisionText, setDecisionText] = useState('');
  const [area, setArea] = useState<DecisionArea>('business');
  const [confidence, setConfidence] = useState(50);
  const [context, setContext] = useState('');
  const [expectedOutcome, setExpectedOutcome] = useState('');
  const [decidedAt, setDecidedAt] = useState('');

  useEffect(() => {
    if (open) {
      setDecisionText('');
      setArea('business');
      setConfidence(50);
      setContext('');
      setExpectedOutcome('');
      setDecidedAt('');
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

  const canSubmit = decisionText.trim().length > 0;

  const handleSubmit = () => {
    if (!canSubmit) return;
    const data: DecisionCreate = {
      decision_text: decisionText.trim(),
      area,
      confidence: confidence / 100,
      context: context.trim() || undefined,
      expected_outcome: expectedOutcome.trim() || undefined,
      decided_at: decidedAt || undefined,
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
            Nowa decyzja
          </h2>
          <button
            onClick={onClose}
            className="rounded-md p-1 transition-colors"
            style={{ color: 'var(--text-secondary)' }}
          >
            <X size={18} />
          </button>
        </div>

        <div className="space-y-3">
          {/* Decision text */}
          <label className="space-y-1">
            <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              Treść decyzji *
            </span>
            <textarea
              value={decisionText}
              onChange={(e) => setDecisionText(e.target.value)}
              rows={3}
              className="block w-full rounded-md border px-3 py-1.5 text-sm"
              style={{
                backgroundColor: 'var(--surface)',
                borderColor: 'var(--border)',
                color: 'var(--text)',
              }}
            />
          </label>

          {/* Area + Date */}
          <div className="grid grid-cols-2 gap-3">
            <label className="space-y-1">
              <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                Obszar *
              </span>
              <select
                value={area}
                onChange={(e) => setArea(e.target.value as DecisionArea)}
                className="block w-full rounded-md border px-3 py-1.5 text-sm"
                style={{
                  backgroundColor: 'var(--surface)',
                  borderColor: 'var(--border)',
                  color: 'var(--text)',
                }}
              >
                {DECISION_AREAS.map((a) => (
                  <option key={a.value} value={a.value}>
                    {a.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1">
              <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                Data decyzji
              </span>
              <input
                type="date"
                value={decidedAt}
                onChange={(e) => setDecidedAt(e.target.value)}
                className="block w-full rounded-md border px-3 py-1.5 text-sm"
                style={{
                  backgroundColor: 'var(--surface)',
                  borderColor: 'var(--border)',
                  color: 'var(--text)',
                }}
              />
            </label>
          </div>

          {/* Confidence */}
          <ConfidenceSlider value={confidence} onChange={setConfidence} />

          {/* Context */}
          <label className="space-y-1">
            <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              Kontekst
            </span>
            <textarea
              value={context}
              onChange={(e) => setContext(e.target.value)}
              rows={2}
              className="block w-full rounded-md border px-3 py-1.5 text-sm"
              style={{
                backgroundColor: 'var(--surface)',
                borderColor: 'var(--border)',
                color: 'var(--text)',
              }}
            />
          </label>

          {/* Expected outcome */}
          <label className="space-y-1">
            <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              Oczekiwany wynik
            </span>
            <textarea
              value={expectedOutcome}
              onChange={(e) => setExpectedOutcome(e.target.value)}
              rows={2}
              className="block w-full rounded-md border px-3 py-1.5 text-sm"
              style={{
                backgroundColor: 'var(--surface)',
                borderColor: 'var(--border)',
                color: 'var(--text)',
              }}
            />
          </label>
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
            Zapisz decyzję
          </button>
        </div>
      </div>
    </div>
  );
}
