'use client';

import { useState, useEffect, useCallback } from 'react';
import { X, Loader2, Plus, Trash2 } from 'lucide-react';
import type { ComplianceMatter, DocType, GenerateDocRequest } from '@gilbertus/api-client';

export interface GenerateDocModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: GenerateDocRequest) => void;
  isSubmitting?: boolean;
  matters?: ComplianceMatter[];
}

const DOC_TYPES: { value: DocType; label: string }[] = [
  { value: 'policy', label: 'Polityka' },
  { value: 'procedure', label: 'Procedura' },
  { value: 'form', label: 'Formularz' },
  { value: 'template', label: 'Szablon' },
  { value: 'register', label: 'Rejestr' },
  { value: 'report', label: 'Raport' },
  { value: 'certificate', label: 'Certyfikat' },
  { value: 'license', label: 'Licencja' },
  { value: 'contract_annex', label: 'Aneks umowy' },
  { value: 'training_material', label: 'Materiał szkoleniowy' },
  { value: 'communication', label: 'Komunikacja' },
  { value: 'regulation_text', label: 'Tekst regulacji' },
  { value: 'internal_regulation', label: 'Regulacja wewnętrzna' },
  { value: 'risk_assessment', label: 'Ocena ryzyka' },
  { value: 'audit_report', label: 'Raport audytu' },
  { value: 'other', label: 'Inne' },
];

interface Signer {
  name: string;
  role: string;
}

export function GenerateDocModal({
  isOpen,
  onClose,
  onSubmit,
  isSubmitting = false,
  matters = [],
}: GenerateDocModalProps) {
  const [matterId, setMatterId] = useState<number | ''>('');
  const [docType, setDocType] = useState<DocType>('policy');
  const [title, setTitle] = useState('');
  const [templateHint, setTemplateHint] = useState('');
  const [signers, setSigners] = useState<Signer[]>([{ name: '', role: '' }]);
  const [validMonths, setValidMonths] = useState(12);

  useEffect(() => {
    if (isOpen) {
      setMatterId('');
      setDocType('policy');
      setTitle('');
      setTemplateHint('');
      setSigners([{ name: '', role: '' }]);
      setValidMonths(12);
    }
  }, [isOpen]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isSubmitting) onClose();
    },
    [onClose, isSubmitting],
  );

  useEffect(() => {
    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
      return () => document.removeEventListener('keydown', handleKeyDown);
    }
  }, [isOpen, handleKeyDown]);

  if (!isOpen) return null;

  const canSubmit = matterId !== '' && !isSubmitting;

  const handleSubmit = () => {
    if (!canSubmit) return;
    const validSigners = signers.filter((s) => s.name.trim() && s.role.trim());
    const data: GenerateDocRequest = {
      matter_id: matterId as number,
      doc_type: docType,
      title: title.trim() || undefined,
      template_hint: templateHint.trim() || undefined,
      signers: validSigners.length > 0 ? validSigners : undefined,
      valid_months: validMonths,
    };
    onSubmit(data);
  };

  const addSigner = () => setSigners([...signers, { name: '', role: '' }]);
  const removeSigner = (idx: number) => setSigners(signers.filter((_, i) => i !== idx));
  const updateSigner = (idx: number, field: keyof Signer, value: string) => {
    const updated = [...signers];
    updated[idx] = { ...updated[idx], [field]: value };
    setSigners(updated);
  };

  const inputStyle = {
    backgroundColor: 'var(--surface)',
    borderColor: 'var(--border)',
    color: 'var(--text)',
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto py-8"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isSubmitting) onClose();
      }}
      style={{ backgroundColor: 'rgba(0, 0, 0, 0.6)' }}
    >
      <div
        className="relative w-full max-w-lg rounded-lg p-6 shadow-xl"
        style={{ backgroundColor: 'var(--bg)', border: '1px solid var(--border)' }}
      >
        {/* Generating overlay */}
        {isSubmitting && (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 rounded-lg bg-[var(--bg)]/90">
            <Loader2 size={32} className="animate-spin" style={{ color: 'var(--accent)' }} />
            <span className="text-sm font-medium" style={{ color: 'var(--text)' }}>
              Generuję dokument...
            </span>
          </div>
        )}

        {/* Header */}
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold" style={{ color: 'var(--text)' }}>
            Generuj dokument AI
          </h2>
          <button
            onClick={onClose}
            disabled={isSubmitting}
            className="rounded-md p-1 transition-colors disabled:opacity-50"
            style={{ color: 'var(--text-secondary)' }}
          >
            <X size={18} />
          </button>
        </div>

        <div className="space-y-3">
          {/* Matter select */}
          <label className="space-y-1">
            <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              Sprawa *
            </span>
            <select
              value={matterId}
              onChange={(e) => setMatterId(e.target.value ? Number(e.target.value) : '')}
              className="block w-full rounded-md border px-3 py-1.5 text-sm"
              style={inputStyle}
            >
              <option value="">Wybierz sprawę...</option>
              {matters.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.title}
                </option>
              ))}
            </select>
          </label>

          {/* Doc type + valid months */}
          <div className="grid grid-cols-3 gap-3">
            <label className="col-span-2 space-y-1">
              <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                Typ dokumentu
              </span>
              <select
                value={docType}
                onChange={(e) => setDocType(e.target.value as DocType)}
                className="block w-full rounded-md border px-3 py-1.5 text-sm"
                style={inputStyle}
              >
                {DOC_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1">
              <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                Ważność (mies.)
              </span>
              <input
                type="number"
                min={1}
                max={120}
                value={validMonths}
                onChange={(e) => setValidMonths(Number(e.target.value) || 12)}
                className="block w-full rounded-md border px-3 py-1.5 text-sm"
                style={inputStyle}
              />
            </label>
          </div>

          {/* Title */}
          <label className="space-y-1">
            <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              Tytuł dokumentu (opcjonalnie)
            </span>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="block w-full rounded-md border px-3 py-1.5 text-sm"
              style={inputStyle}
            />
          </label>

          {/* Template hint */}
          <label className="space-y-1">
            <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              Wskazówki dla AI (opcjonalnie)
            </span>
            <textarea
              value={templateHint}
              onChange={(e) => setTemplateHint(e.target.value)}
              rows={2}
              placeholder="Opisz czego oczekujesz w dokumencie..."
              className="block w-full rounded-md border px-3 py-1.5 text-sm"
              style={inputStyle}
            />
          </label>

          {/* Signers */}
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                Sygnatariusze
              </span>
              <button
                onClick={addSigner}
                className="flex items-center gap-1 text-xs transition-colors"
                style={{ color: 'var(--accent)' }}
              >
                <Plus size={12} />
                Dodaj
              </button>
            </div>
            {signers.map((s, idx) => (
              <div key={idx} className="flex items-center gap-2">
                <input
                  type="text"
                  value={s.name}
                  onChange={(e) => updateSigner(idx, 'name', e.target.value)}
                  placeholder="Imię i nazwisko"
                  className="block flex-1 rounded-md border px-3 py-1.5 text-sm"
                  style={inputStyle}
                />
                <input
                  type="text"
                  value={s.role}
                  onChange={(e) => updateSigner(idx, 'role', e.target.value)}
                  placeholder="Rola"
                  className="block flex-1 rounded-md border px-3 py-1.5 text-sm"
                  style={inputStyle}
                />
                {signers.length > 1 && (
                  <button
                    onClick={() => removeSigner(idx)}
                    className="p-1 transition-colors"
                    style={{ color: 'var(--text-secondary)' }}
                  >
                    <Trash2 size={14} />
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Submit */}
        <div className="mt-6 flex justify-end gap-3">
          <button
            onClick={onClose}
            disabled={isSubmitting}
            className="rounded-md px-4 py-1.5 text-sm transition-colors disabled:opacity-50"
            style={{ color: 'var(--text-secondary)' }}
          >
            Anuluj
          </button>
          <button
            onClick={handleSubmit}
            disabled={!canSubmit}
            className="flex items-center gap-2 rounded-md px-4 py-1.5 text-sm font-medium transition-colors disabled:opacity-50"
            style={{ backgroundColor: 'var(--accent)', color: '#fff' }}
          >
            Generuj dokument
          </button>
        </div>
      </div>
    </div>
  );
}
