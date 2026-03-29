'use client';

import { useState, useEffect, useCallback } from 'react';
import { X, Loader2, Plus } from 'lucide-react';
import type { CreateTrainingRequest, TrainingType } from '@gilbertus/api-client';
import { AreaFilter } from './area-filter';

export interface CreateTrainingModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: CreateTrainingRequest) => void;
  isSubmitting?: boolean;
}

const TRAINING_TYPES: { value: TrainingType; label: string }[] = [
  { value: 'mandatory', label: 'Obowiązkowe' },
  { value: 'awareness', label: 'Świadomość' },
  { value: 'certification', label: 'Certyfikacja' },
  { value: 'refresher', label: 'Odświeżenie' },
  { value: 'onboarding', label: 'Onboarding' },
];

export function CreateTrainingModal({
  isOpen,
  onClose,
  onSubmit,
  isSubmitting = false,
}: CreateTrainingModalProps) {
  const [title, setTitle] = useState('');
  const [areaCode, setAreaCode] = useState<string | null>(null);
  const [trainingType, setTrainingType] = useState<TrainingType>('mandatory');
  const [contentSummary, setContentSummary] = useState('');
  const [audienceInput, setAudienceInput] = useState('');
  const [targetAudience, setTargetAudience] = useState<string[]>([]);
  const [deadline, setDeadline] = useState('');
  const [generateMaterial, setGenerateMaterial] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setTitle('');
      setAreaCode(null);
      setTrainingType('mandatory');
      setContentSummary('');
      setAudienceInput('');
      setTargetAudience([]);
      setDeadline('');
      setGenerateMaterial(false);
    }
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

  const addAudience = () => {
    const trimmed = audienceInput.trim();
    if (trimmed && !targetAudience.includes(trimmed)) {
      setTargetAudience([...targetAudience, trimmed]);
      setAudienceInput('');
    }
  };

  const removeAudience = (item: string) => {
    setTargetAudience(targetAudience.filter((a) => a !== item));
  };

  const handleAudienceKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      addAudience();
    }
  };

  const canSubmit = title.trim().length > 0 && areaCode !== null;

  const handleSubmit = () => {
    if (!canSubmit || !areaCode) return;
    const data: CreateTrainingRequest = {
      title: title.trim(),
      area_code: areaCode as CreateTrainingRequest['area_code'],
      training_type: trainingType,
      content_summary: contentSummary.trim() || undefined,
      target_audience: targetAudience.length > 0 ? targetAudience : undefined,
      deadline: deadline || undefined,
      generate_material: generateMaterial || undefined,
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
        className="relative w-full max-w-lg rounded-lg p-6 shadow-xl max-h-[90vh] overflow-y-auto"
        style={{ backgroundColor: 'var(--bg)', border: '1px solid var(--border)' }}
      >
        {/* Header */}
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold" style={{ color: 'var(--text)' }}>
            Nowe szkolenie compliance
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
          {/* Title */}
          <label className="space-y-1">
            <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              Tytuł *
            </span>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="block w-full rounded-md border px-3 py-1.5 text-sm"
              style={{
                backgroundColor: 'var(--surface)',
                borderColor: 'var(--border)',
                color: 'var(--text)',
              }}
            />
          </label>

          {/* Area + Type */}
          <div className="grid grid-cols-2 gap-3">
            <label className="space-y-1">
              <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                Obszar compliance *
              </span>
              <AreaFilter value={areaCode} onChange={setAreaCode} />
            </label>
            <label className="space-y-1">
              <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                Typ szkolenia
              </span>
              <select
                value={trainingType}
                onChange={(e) => setTrainingType(e.target.value as TrainingType)}
                className="block w-full rounded-md border px-3 py-1.5 text-sm"
                style={{
                  backgroundColor: 'var(--surface)',
                  borderColor: 'var(--border)',
                  color: 'var(--text)',
                }}
              >
                {TRAINING_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {/* Target audience */}
          <label className="space-y-1">
            <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              Grupa docelowa
            </span>
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={audienceInput}
                onChange={(e) => setAudienceInput(e.target.value)}
                onKeyDown={handleAudienceKeyDown}
                placeholder='np. "zarząd", "pracownicy", "IT"'
                className="block flex-1 rounded-md border px-3 py-1.5 text-sm"
                style={{
                  backgroundColor: 'var(--surface)',
                  borderColor: 'var(--border)',
                  color: 'var(--text)',
                }}
              />
              <button
                type="button"
                onClick={addAudience}
                className="flex items-center justify-center rounded-md p-1.5 transition-colors"
                style={{ backgroundColor: 'var(--surface)', color: 'var(--text-secondary)' }}
              >
                <Plus size={16} />
              </button>
            </div>
            {targetAudience.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-1.5">
                {targetAudience.map((a) => (
                  <span
                    key={a}
                    className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs bg-[var(--surface)] text-[var(--text-secondary)]"
                  >
                    {a}
                    <button
                      type="button"
                      onClick={() => removeAudience(a)}
                      className="hover:text-[var(--text)]"
                    >
                      <X size={12} />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </label>

          {/* Deadline */}
          <label className="space-y-1">
            <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              Termin
            </span>
            <input
              type="date"
              value={deadline}
              onChange={(e) => setDeadline(e.target.value)}
              className="block w-full rounded-md border px-3 py-1.5 text-sm"
              style={{
                backgroundColor: 'var(--surface)',
                borderColor: 'var(--border)',
                color: 'var(--text)',
              }}
            />
          </label>

          {/* Content summary */}
          <label className="space-y-1">
            <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              Opis treści
            </span>
            <textarea
              value={contentSummary}
              onChange={(e) => setContentSummary(e.target.value)}
              rows={3}
              className="block w-full rounded-md border px-3 py-1.5 text-sm"
              style={{
                backgroundColor: 'var(--surface)',
                borderColor: 'var(--border)',
                color: 'var(--text)',
              }}
            />
          </label>

          {/* Generate material checkbox */}
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={generateMaterial}
              onChange={(e) => setGenerateMaterial(e.target.checked)}
              className="rounded"
            />
            <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>
              Generuj materiał szkoleniowy via AI
            </span>
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
            disabled={!canSubmit || isSubmitting}
            className="flex items-center gap-2 rounded-md px-4 py-1.5 text-sm font-medium transition-colors disabled:opacity-50"
            style={{ backgroundColor: 'var(--accent)', color: '#fff' }}
          >
            {isSubmitting && <Loader2 size={14} className="animate-spin" />}
            Utwórz szkolenie
          </button>
        </div>
      </div>
    </div>
  );
}
