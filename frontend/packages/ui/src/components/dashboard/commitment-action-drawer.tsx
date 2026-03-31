'use client';

import { useState } from 'react';
import { CheckCircle2, Trash2, X, ChevronDown } from 'lucide-react';
import type { CommitmentItem } from '@gilbertus/api-client';
import { resolveCommitment } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';

interface CommitmentActionDrawerProps {
  commitment: CommitmentItem | null;
  isOpen: boolean;
  onClose: () => void;
  onResolved: (id: number) => void;
}

export function CommitmentActionDrawer({
  commitment,
  isOpen,
  onClose,
  onResolved,
}: CommitmentActionDrawerProps) {
  const [note, setNote] = useState('');
  const [delegateChannel, setDelegateChannel] = useState<
    'email' | 'teams' | 'whatsapp' | null
  >(null);
  const [delegateMessage, setDelegateMessage] = useState('');
  const [saving, setSaving] = useState(false);
  const [contextOpen, setContextOpen] = useState(false);

  if (!isOpen || !commitment) return null;

  const isOverdue =
    commitment.deadline && new Date(commitment.deadline) < new Date();

  const handleResolve = async (type: 'resolved' | 'dismissed') => {
    setSaving(true);
    try {
      await resolveCommitment(commitment.id, {
        resolution_type: type,
        note: note || undefined,
      });
      onResolved(commitment.id);
      onClose();
    } finally {
      setSaving(false);
    }
  };

  const handleDelegate = async () => {
    if (!delegateChannel) return;
    setSaving(true);
    try {
      await resolveCommitment(commitment.id, {
        resolution_type: 'delegated',
        delegate_channel: delegateChannel,
        delegate_to: commitment.person_name,
        note: delegateMessage || undefined,
      });
      onResolved(commitment.id);
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 z-40"
        onClick={onClose}
        role="presentation"
      />

      {/* Drawer */}
      <div className="fixed right-0 top-0 h-full w-[480px] max-w-full bg-[var(--surface)] border-l border-[var(--border)] z-50 overflow-y-auto shadow-2xl animate-in slide-in-from-right duration-200">
        {/* Header */}
        <div className="p-6 border-b border-[var(--border)]">
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <p className="text-base font-medium text-[var(--text)] leading-snug">
                {commitment.commitment_text}
              </p>
              <div className="flex items-center gap-3 mt-2 text-sm">
                <span className="text-[var(--text-secondary)]">
                  {commitment.person_name}
                </span>
                {commitment.deadline && (
                  <span
                    className={cn(
                      'font-medium',
                      isOverdue ? 'text-red-400' : 'text-amber-400',
                    )}
                  >
                    {isOverdue ? '⚠️ ' : '📅 '}
                    {new Date(commitment.deadline).toLocaleDateString('pl-PL')}
                    {isOverdue && ' — przeterminowane'}
                  </span>
                )}
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-1 rounded hover:bg-[var(--surface-hover)] shrink-0"
            >
              <X size={18} className="text-[var(--text-secondary)]" />
            </button>
          </div>
        </div>

        <div className="p-6 space-y-6">
          {/* Primary actions */}
          <div className="grid grid-cols-2 gap-3">
            <button
              onClick={() => handleResolve('resolved')}
              disabled={saving}
              className="flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-sm transition-colors disabled:opacity-50"
            >
              <CheckCircle2 size={16} />
              Rozwiązane
            </button>
            <button
              onClick={() => handleResolve('dismissed')}
              disabled={saving}
              className="flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-[var(--surface-secondary)] hover:bg-[var(--surface-hover)] text-[var(--text-secondary)] font-medium text-sm border border-[var(--border)] transition-colors disabled:opacity-50"
            >
              <Trash2 size={16} />
              Nieaktualne
            </button>
          </div>

          {/* Delegate section */}
          <div className="space-y-3">
            <p className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wide">
              Zlec wykonanie przez:
            </p>
            <div className="grid grid-cols-3 gap-2">
              {(['email', 'teams', 'whatsapp'] as const).map((ch) => {
                const labels = {
                  email: '📧 Email',
                  teams: '💬 Teams',
                  whatsapp: '📱 WhatsApp',
                };
                return (
                  <button
                    key={ch}
                    onClick={() =>
                      setDelegateChannel(delegateChannel === ch ? null : ch)
                    }
                    className={cn(
                      'px-3 py-2.5 rounded-lg text-sm font-medium border transition-all',
                      delegateChannel === ch
                        ? 'bg-[var(--accent)] text-white border-[var(--accent)]'
                        : 'bg-[var(--surface-secondary)] text-[var(--text-secondary)] border-[var(--border)] hover:border-[var(--accent)]/50',
                    )}
                  >
                    {labels[ch]}
                  </button>
                );
              })}
            </div>

            {delegateChannel && (
              <div className="space-y-2">
                <textarea
                  value={
                    delegateMessage ||
                    `Proszę o realizację: ${commitment.commitment_text}`
                  }
                  onChange={(e) => setDelegateMessage(e.target.value)}
                  rows={4}
                  className="w-full px-3 py-2 rounded-lg bg-[var(--surface-secondary)] border border-[var(--border)] text-sm text-[var(--text)] resize-none focus:outline-none focus:border-[var(--accent)]"
                  placeholder="Treść wiadomości..."
                />
                <button
                  onClick={handleDelegate}
                  disabled={saving}
                  className="w-full py-2.5 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white text-sm font-medium transition-colors disabled:opacity-50"
                >
                  Wyślij przez{' '}
                  {delegateChannel === 'whatsapp'
                    ? 'WhatsApp'
                    : delegateChannel === 'teams'
                      ? 'Teams'
                      : 'email'}
                </button>
              </div>
            )}
          </div>

          {/* Note */}
          <div className="space-y-2">
            <p className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wide">
              Notatka (opcjonalnie)
            </p>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={2}
              className="w-full px-3 py-2 rounded-lg bg-[var(--surface-secondary)] border border-[var(--border)] text-sm text-[var(--text)] resize-none focus:outline-none focus:border-[var(--accent)]"
              placeholder="Dodaj notatkę do rozwiązania..."
            />
          </div>

          {/* Context (collapsible) */}
          {commitment.context && (
            <div className="border border-[var(--border)] rounded-lg overflow-hidden">
              <button
                onClick={() => setContextOpen(!contextOpen)}
                className="w-full flex items-center justify-between px-4 py-3 text-sm text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]"
              >
                <span>Kontekst źródłowy</span>
                <ChevronDown
                  size={14}
                  className={cn(
                    'transition-transform',
                    contextOpen && 'rotate-180',
                  )}
                />
              </button>
              {contextOpen && (
                <div className="px-4 pb-4 text-xs text-[var(--text-secondary)] leading-relaxed border-t border-[var(--border)] pt-3 whitespace-pre-wrap">
                  {commitment.context}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
