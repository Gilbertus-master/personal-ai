'use client';

import { useState, useEffect, useCallback } from 'react';
import { X, Loader2 } from 'lucide-react';
import type { PersonCreate, PersonUpdate, PersonFull } from '@gilbertus/api-client';

interface PersonFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: PersonCreate | PersonUpdate) => void;
  person?: PersonFull;
  isSubmitting?: boolean;
  mode: 'create' | 'edit';
}

function slugify(name: string): string {
  return name
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '');
}

const RELATIONSHIP_TYPES = ['employee', 'partner', 'client', 'advisor', 'contact', 'other'];
const STATUSES = ['active', 'inactive'];
const SENTIMENTS = ['positive', 'neutral', 'negative'];

export function PersonFormModal({
  isOpen,
  onClose,
  onSubmit,
  person,
  isSubmitting = false,
  mode,
}: PersonFormModalProps) {
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [slug, setSlug] = useState('');
  const [relType, setRelType] = useState('employee');
  const [role, setRole] = useState('');
  const [org, setOrg] = useState('');
  const [status, setStatus] = useState('active');
  const [channel, setChannel] = useState('');
  const [sentiment, setSentiment] = useState('neutral');

  // Populate form when editing
  useEffect(() => {
    if (mode === 'edit' && person) {
      setFirstName(person.first_name);
      setLastName(person.last_name ?? '');
      setSlug(person.slug);
      setRelType(person.relationship?.relationship_type ?? 'employee');
      setRole(person.relationship?.current_role ?? '');
      setOrg(person.relationship?.organization ?? '');
      setStatus(person.relationship?.status ?? 'active');
      setChannel(person.relationship?.contact_channel ?? '');
      setSentiment(person.relationship?.sentiment ?? 'neutral');
    } else if (mode === 'create') {
      setFirstName('');
      setLastName('');
      setSlug('');
      setRelType('employee');
      setRole('');
      setOrg('');
      setStatus('active');
      setChannel('');
      setSentiment('neutral');
    }
  }, [mode, person]);

  // Auto-generate slug in create mode
  useEffect(() => {
    if (mode === 'create') {
      setSlug(slugify(`${firstName} ${lastName}`.trim()));
    }
  }, [firstName, lastName, mode]);

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

  const canSubmit =
    firstName.trim().length > 0 && (mode === 'edit' || slug.trim().length > 0);

  const handleSubmit = () => {
    if (!canSubmit) return;
    if (mode === 'create') {
      const data: PersonCreate = {
        slug: slug.trim(),
        first_name: firstName.trim(),
        last_name: lastName.trim() || null,
        relationship: {
          relationship_type: relType,
          current_role: role || null,
          organization: org || null,
          status,
          contact_channel: channel || null,
          sentiment,
        },
      };
      onSubmit(data);
    } else {
      const data: PersonUpdate = {
        first_name: firstName.trim(),
        last_name: lastName.trim() || null,
      };
      onSubmit(data);
    }
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
            {mode === 'create' ? 'Dodaj osobę' : 'Edytuj osobę'}
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
          {/* Name fields */}
          <div className="grid grid-cols-2 gap-3">
            <label className="space-y-1">
              <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                Imię *
              </span>
              <input
                type="text"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                className="block w-full rounded-md border px-3 py-1.5 text-sm"
                style={{
                  backgroundColor: 'var(--surface)',
                  borderColor: 'var(--border)',
                  color: 'var(--text)',
                }}
              />
            </label>
            <label className="space-y-1">
              <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                Nazwisko
              </span>
              <input
                type="text"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                className="block w-full rounded-md border px-3 py-1.5 text-sm"
                style={{
                  backgroundColor: 'var(--surface)',
                  borderColor: 'var(--border)',
                  color: 'var(--text)',
                }}
              />
            </label>
          </div>

          {/* Slug (create only) */}
          {mode === 'create' && (
            <label className="space-y-1">
              <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                Slug *
              </span>
              <input
                type="text"
                value={slug}
                onChange={(e) => setSlug(e.target.value)}
                className="block w-full rounded-md border px-3 py-1.5 text-sm"
                style={{
                  backgroundColor: 'var(--surface)',
                  borderColor: 'var(--border)',
                  color: 'var(--text)',
                }}
              />
            </label>
          )}

          {/* Relationship fields (create only) */}
          {mode === 'create' && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <label className="space-y-1">
                  <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                    Typ relacji
                  </span>
                  <select
                    value={relType}
                    onChange={(e) => setRelType(e.target.value)}
                    className="block w-full rounded-md border px-3 py-1.5 text-sm"
                    style={{
                      backgroundColor: 'var(--surface)',
                      borderColor: 'var(--border)',
                      color: 'var(--text)',
                    }}
                  >
                    {RELATIONSHIP_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="space-y-1">
                  <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                    Status
                  </span>
                  <select
                    value={status}
                    onChange={(e) => setStatus(e.target.value)}
                    className="block w-full rounded-md border px-3 py-1.5 text-sm"
                    style={{
                      backgroundColor: 'var(--surface)',
                      borderColor: 'var(--border)',
                      color: 'var(--text)',
                    }}
                  >
                    {STATUSES.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <label className="space-y-1">
                  <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                    Rola
                  </span>
                  <input
                    type="text"
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                    className="block w-full rounded-md border px-3 py-1.5 text-sm"
                    style={{
                      backgroundColor: 'var(--surface)',
                      borderColor: 'var(--border)',
                      color: 'var(--text)',
                    }}
                  />
                </label>
                <label className="space-y-1">
                  <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                    Organizacja
                  </span>
                  <input
                    type="text"
                    value={org}
                    onChange={(e) => setOrg(e.target.value)}
                    className="block w-full rounded-md border px-3 py-1.5 text-sm"
                    style={{
                      backgroundColor: 'var(--surface)',
                      borderColor: 'var(--border)',
                      color: 'var(--text)',
                    }}
                  />
                </label>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <label className="space-y-1">
                  <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                    Kanał kontaktu
                  </span>
                  <input
                    type="text"
                    value={channel}
                    onChange={(e) => setChannel(e.target.value)}
                    placeholder="email, teams, whatsapp..."
                    className="block w-full rounded-md border px-3 py-1.5 text-sm"
                    style={{
                      backgroundColor: 'var(--surface)',
                      borderColor: 'var(--border)',
                      color: 'var(--text)',
                    }}
                  />
                </label>
                <label className="space-y-1">
                  <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                    Nastawienie
                  </span>
                  <select
                    value={sentiment}
                    onChange={(e) => setSentiment(e.target.value)}
                    className="block w-full rounded-md border px-3 py-1.5 text-sm"
                    style={{
                      backgroundColor: 'var(--surface)',
                      borderColor: 'var(--border)',
                      color: 'var(--text)',
                    }}
                  >
                    {SENTIMENTS.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </>
          )}
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
            {mode === 'create' ? 'Dodaj osobę' : 'Zapisz zmiany'}
          </button>
        </div>
      </div>
    </div>
  );
}
