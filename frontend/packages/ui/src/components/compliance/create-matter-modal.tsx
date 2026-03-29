'use client';

import { useState, useEffect, useCallback } from 'react';
import { X, Loader2 } from 'lucide-react';
import type { CreateMatterRequest, MatterType, Priority } from '@gilbertus/api-client';
import { AreaFilter } from './area-filter';

export interface CreateMatterModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: CreateMatterRequest) => void;
  isSubmitting?: boolean;
}

const MATTER_TYPES: { value: MatterType; label: string }[] = [
  { value: 'new_regulation', label: 'Nowa regulacja' },
  { value: 'regulation_change', label: 'Zmiana regulacji' },
  { value: 'audit_finding', label: 'Wynik audytu' },
  { value: 'incident', label: 'Incydent' },
  { value: 'license_renewal', label: 'Odnowienie licencji' },
  { value: 'contract_review', label: 'Przegląd umowy' },
  { value: 'policy_update', label: 'Aktualizacja polityki' },
  { value: 'training_need', label: 'Potrzeba szkolenia' },
  { value: 'complaint', label: 'Skarga' },
  { value: 'inspection', label: 'Kontrola' },
  { value: 'risk_assessment', label: 'Ocena ryzyka' },
  { value: 'other', label: 'Inne' },
];

const PRIORITIES: { value: Priority; label: string }[] = [
  { value: 'low', label: 'Niski' },
  { value: 'medium', label: 'Średni' },
  { value: 'high', label: 'Wysoki' },
  { value: 'critical', label: 'Krytyczny' },
];

export function CreateMatterModal({
  isOpen,
  onClose,
  onSubmit,
  isSubmitting = false,
}: CreateMatterModalProps) {
  const [title, setTitle] = useState('');
  const [matterType, setMatterType] = useState<MatterType>('new_regulation');
  const [areaCode, setAreaCode] = useState<string | null>(null);
  const [priority, setPriority] = useState<Priority>('medium');
  const [description, setDescription] = useState('');
  const [sourceRegulation, setSourceRegulation] = useState('');

  useEffect(() => {
    if (isOpen) {
      setTitle('');
      setMatterType('new_regulation');
      setAreaCode(null);
      setPriority('medium');
      setDescription('');
      setSourceRegulation('');
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

  const canSubmit = title.trim().length > 0 && areaCode !== null;

  const handleSubmit = () => {
    if (!canSubmit || !areaCode) return;
    const data: CreateMatterRequest = {
      title: title.trim(),
      matter_type: matterType,
      area_code: areaCode as CreateMatterRequest['area_code'],
      priority,
      description: description.trim() || undefined,
      source_regulation: sourceRegulation.trim() || undefined,
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
            Nowa sprawa compliance
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

          {/* Type + Priority */}
          <div className="grid grid-cols-2 gap-3">
            <label className="space-y-1">
              <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                Typ sprawy
              </span>
              <select
                value={matterType}
                onChange={(e) => setMatterType(e.target.value as MatterType)}
                className="block w-full rounded-md border px-3 py-1.5 text-sm"
                style={{
                  backgroundColor: 'var(--surface)',
                  borderColor: 'var(--border)',
                  color: 'var(--text)',
                }}
              >
                {MATTER_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1">
              <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                Priorytet
              </span>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value as Priority)}
                className="block w-full rounded-md border px-3 py-1.5 text-sm"
                style={{
                  backgroundColor: 'var(--surface)',
                  borderColor: 'var(--border)',
                  color: 'var(--text)',
                }}
              >
                {PRIORITIES.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {/* Area */}
          <label className="space-y-1">
            <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              Obszar compliance *
            </span>
            <AreaFilter value={areaCode} onChange={setAreaCode} />
          </label>

          {/* Description */}
          <label className="space-y-1">
            <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              Opis
            </span>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="block w-full rounded-md border px-3 py-1.5 text-sm"
              style={{
                backgroundColor: 'var(--surface)',
                borderColor: 'var(--border)',
                color: 'var(--text)',
              }}
            />
          </label>

          {/* Source regulation */}
          <label className="space-y-1">
            <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              Regulacja źródłowa
            </span>
            <input
              type="text"
              value={sourceRegulation}
              onChange={(e) => setSourceRegulation(e.target.value)}
              placeholder="np. Ustawa o OZE art. 72"
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
            disabled={!canSubmit || isSubmitting}
            className="flex items-center gap-2 rounded-md px-4 py-1.5 text-sm font-medium transition-colors disabled:opacity-50"
            style={{ backgroundColor: 'var(--accent)', color: '#fff' }}
          >
            {isSubmitting && <Loader2 size={14} className="animate-spin" />}
            Utwórz sprawę
          </button>
        </div>
      </div>
    </div>
  );
}
