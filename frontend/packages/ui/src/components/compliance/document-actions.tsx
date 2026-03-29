'use client';

import { useState, useEffect, useCallback } from 'react';
import { CheckCircle, PenTool, Loader2, X } from 'lucide-react';
import type { DocStatus, SignatureStatus } from '@gilbertus/api-client';

export interface DocumentActionsProps {
  documentId: number;
  currentStatus: DocStatus;
  signatureStatus: SignatureStatus;
  onApprove: (id: number) => void;
  onSign: (id: number, signerName: string) => void;
  isApproving?: boolean;
  isSigning?: boolean;
}

function SignModal({
  isOpen,
  onClose,
  onSubmit,
  isSigning,
}: {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (name: string) => void;
  isSigning?: boolean;
}) {
  const [signerName, setSignerName] = useState('');

  useEffect(() => {
    if (isOpen) setSignerName('');
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

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      style={{ backgroundColor: 'rgba(0, 0, 0, 0.6)' }}
    >
      <div
        className="relative w-full max-w-sm rounded-lg p-6 shadow-xl"
        style={{ backgroundColor: 'var(--bg)', border: '1px solid var(--border)' }}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold" style={{ color: 'var(--text)' }}>
            Podpisz dokument
          </h2>
          <button
            onClick={onClose}
            className="rounded-md p-1 transition-colors"
            style={{ color: 'var(--text-secondary)' }}
          >
            <X size={18} />
          </button>
        </div>
        <label className="space-y-1">
          <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
            Imię i nazwisko podpisującego *
          </span>
          <input
            type="text"
            value={signerName}
            onChange={(e) => setSignerName(e.target.value)}
            className="block w-full rounded-md border px-3 py-1.5 text-sm"
            style={{
              backgroundColor: 'var(--surface)',
              borderColor: 'var(--border)',
              color: 'var(--text)',
            }}
          />
        </label>
        <div className="mt-6 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="rounded-md px-4 py-1.5 text-sm transition-colors"
            style={{ color: 'var(--text-secondary)' }}
          >
            Anuluj
          </button>
          <button
            onClick={() => {
              if (signerName.trim()) onSubmit(signerName.trim());
            }}
            disabled={!signerName.trim() || isSigning}
            className="flex items-center gap-2 rounded-md px-4 py-1.5 text-sm font-medium transition-colors disabled:opacity-50"
            style={{ backgroundColor: 'var(--accent)', color: '#fff' }}
          >
            {isSigning && <Loader2 size={14} className="animate-spin" />}
            Podpisz
          </button>
        </div>
      </div>
    </div>
  );
}

export function DocumentActions({
  documentId,
  currentStatus,
  signatureStatus,
  onApprove,
  onSign,
  isApproving = false,
  isSigning = false,
}: DocumentActionsProps) {
  const [showSignModal, setShowSignModal] = useState(false);

  const showApprove = currentStatus === 'draft' || currentStatus === 'review';
  const showSign = signatureStatus === 'pending' || signatureStatus === 'partially_signed';

  if (!showApprove && !showSign) return null;

  return (
    <div className="flex items-center gap-1.5">
      {showApprove && (
        <button
          onClick={() => onApprove(documentId)}
          disabled={isApproving}
          className="flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-colors hover:bg-[var(--surface-hover)] disabled:opacity-50"
          style={{ color: 'var(--accent)' }}
          title="Zatwierdź"
        >
          {isApproving ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <CheckCircle size={14} />
          )}
          Zatwierdź
        </button>
      )}
      {showSign && (
        <>
          <button
            onClick={() => setShowSignModal(true)}
            disabled={isSigning}
            className="flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-colors hover:bg-[var(--surface-hover)] disabled:opacity-50"
            style={{ color: 'var(--accent)' }}
            title="Podpisz"
          >
            {isSigning ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <PenTool size={14} />
            )}
            Podpisz
          </button>
          <SignModal
            isOpen={showSignModal}
            onClose={() => setShowSignModal(false)}
            onSubmit={(name) => {
              onSign(documentId, name);
              setShowSignModal(false);
            }}
            isSigning={isSigning}
          />
        </>
      )}
    </div>
  );
}
