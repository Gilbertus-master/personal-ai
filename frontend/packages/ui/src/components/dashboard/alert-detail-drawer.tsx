'use client';

import { useState, useEffect, useRef } from 'react';
import { X, Wrench, Ban, ChevronRight, AlertTriangle, Info, AlertCircle } from 'lucide-react';
import type { AlertItem } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';

interface AlertDetailDrawerProps {
  alert: AlertItem | null;
  onClose: () => void;
  onResolve: (
    alertId: number,
    action: 'fix' | 'suppress',
    comment: string,
    fixInstruction?: string,
  ) => void;
  isResolving: boolean;
}

const SEVERITY_CONFIG: Record<string, { label: string; color: string; bg: string; icon: typeof AlertTriangle }> = {
  high: { label: 'Wysoki', color: 'text-red-400', bg: 'bg-red-500/10', icon: AlertCircle },
  medium: { label: 'Sredni', color: 'text-amber-400', bg: 'bg-amber-500/10', icon: AlertTriangle },
  low: { label: 'Niski', color: 'text-blue-400', bg: 'bg-blue-500/10', icon: Info },
};

const ALERT_TYPE_LABEL: Record<string, string> = {
  decision_no_followup: 'Brak follow-up',
  conflict_spike: 'Konflikt',
  missing_communication: 'Brak komunikacji',
  health_clustering: 'Zdrowie',
  data_guardian: 'Data Guardian',
  ingestion_stale: 'Ingestion',
  compliance: 'Compliance',
  extraction_watchdog: 'Extraction',
};

function formatEvidence(evidence: string | null): string | null {
  if (!evidence) return null;
  try {
    const parsed = JSON.parse(evidence);
    return JSON.stringify(parsed, null, 2);
  } catch {
    return evidence;
  }
}

export function AlertDetailDrawer({
  alert,
  onClose,
  onResolve,
  isResolving,
}: AlertDetailDrawerProps) {
  const [mode, setMode] = useState<'view' | 'fix' | 'suppress'>('view');
  const [comment, setComment] = useState('');
  const [fixInstruction, setFixInstruction] = useState('');
  const drawerRef = useRef<HTMLDivElement>(null);

  // Reset state when alert changes
  useEffect(() => {
    if (alert) {
      setMode('view');
      setComment('');
      setFixInstruction(alert.description || '');
    }
  }, [alert]);

  // Close on Escape
  useEffect(() => {
    if (!alert) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [alert, onClose]);

  if (!alert) return null;

  const severity = SEVERITY_CONFIG[alert.severity] ?? SEVERITY_CONFIG.low;
  const SeverityIcon = severity.icon;
  const typeLabel = ALERT_TYPE_LABEL[alert.alert_type] ?? alert.alert_type;
  const evidence = formatEvidence(alert.evidence);

  function handleSubmitFix() {
    onResolve(alert!.alert_id, 'fix', comment, fixInstruction || undefined);
  }

  function handleSubmitSuppress() {
    onResolve(alert!.alert_id, 'suppress', comment);
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/50 transition-opacity"
        onClick={onClose}
      />

      {/* Drawer */}
      <div
        ref={drawerRef}
        className="fixed right-0 top-0 z-50 flex h-full w-full max-w-lg flex-col border-l border-[var(--border)] bg-[var(--bg)] shadow-2xl animate-in slide-in-from-right duration-200"
      >
        {/* Header */}
        <div className="flex items-start justify-between border-b border-[var(--border)] px-6 py-4">
          <div className="min-w-0 flex-1 pr-4">
            <div className="mb-2 flex items-center gap-2">
              <span className={cn('inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium', severity.bg, severity.color)}>
                <SeverityIcon className="h-3 w-3" />
                {severity.label}
              </span>
              <span className="rounded-full bg-[var(--surface-hover)] px-2 py-0.5 text-[10px] text-[var(--text-secondary)]">
                {typeLabel}
              </span>
            </div>
            <h2 className="text-base font-semibold text-[var(--text)]">
              {alert.title}
            </h2>
            {alert.created_at && (
              <p className="mt-1 text-xs text-[var(--text-secondary)]">
                {new Date(alert.created_at).toLocaleString('pl-PL')}
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            className="rounded-md p-1.5 text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text)]"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Body — scrollable */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {/* Description */}
          <div>
            <h3 className="mb-1 text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">
              Opis
            </h3>
            <p className="text-sm text-[var(--text)] whitespace-pre-wrap">
              {alert.description}
            </p>
          </div>

          {/* Evidence */}
          {evidence && (
            <div>
              <h3 className="mb-1 text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">
                Dowody
              </h3>
              <pre className="max-h-48 overflow-auto rounded-md bg-[var(--surface)] p-3 text-xs text-[var(--text-secondary)] border border-[var(--border)]">
                {evidence}
              </pre>
            </div>
          )}

          {/* Action mode: Fix */}
          {mode === 'fix' && (
            <div className="space-y-3 rounded-lg border border-blue-500/20 bg-blue-500/5 p-4">
              <h3 className="text-sm font-medium text-blue-400">
                Instrukcja naprawy
              </h3>
              <textarea
                value={fixInstruction}
                onChange={(e) => setFixInstruction(e.target.value)}
                rows={4}
                className="w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-secondary)] focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder="Co trzeba zrobić..."
              />
              <textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                rows={2}
                className="w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-secondary)] focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder="Komentarz (opcjonalny)..."
              />
              <div className="flex gap-2">
                <button
                  onClick={handleSubmitFix}
                  disabled={isResolving || !fixInstruction.trim()}
                  className="flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Wrench className="h-4 w-4" />
                  {isResolving ? 'Wysylanie...' : 'Zatwierdz naprawe'}
                </button>
                <button
                  onClick={() => setMode('view')}
                  className="rounded-md px-3 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]"
                >
                  Anuluj
                </button>
              </div>
            </div>
          )}

          {/* Action mode: Suppress */}
          {mode === 'suppress' && (
            <div className="space-y-3 rounded-lg border border-red-500/20 bg-red-500/5 p-4">
              <h3 className="text-sm font-medium text-red-400">
                Suppresja alertu
              </h3>
              <p className="text-xs text-[var(--text-secondary)]">
                Wszystkie przyszle alerty typu <strong>{typeLabel}</strong> zostana zignorowane.
              </p>
              <textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                rows={2}
                className="w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-secondary)] focus:outline-none focus:ring-1 focus:ring-red-500"
                placeholder="Powod suppresji..."
              />
              <div className="flex gap-2">
                <button
                  onClick={handleSubmitSuppress}
                  disabled={isResolving || !comment.trim()}
                  className="flex items-center gap-2 rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Ban className="h-4 w-4" />
                  {isResolving ? 'Wysylanie...' : 'Potwierdz suppresje'}
                </button>
                <button
                  onClick={() => setMode('view')}
                  className="rounded-md px-3 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]"
                >
                  Anuluj
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Footer actions — visible in view mode */}
        {mode === 'view' && (
          <div className="border-t border-[var(--border)] px-6 py-4 flex gap-3">
            <button
              onClick={() => setMode('fix')}
              className="flex flex-1 items-center justify-center gap-2 rounded-md bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
            >
              <Wrench className="h-4 w-4" />
              Napraw
              <ChevronRight className="h-4 w-4 ml-auto" />
            </button>
            <button
              onClick={() => setMode('suppress')}
              className="flex flex-1 items-center justify-center gap-2 rounded-md border border-red-500/30 px-4 py-2.5 text-sm font-medium text-red-400 hover:bg-red-500/10 transition-colors"
            >
              <Ban className="h-4 w-4" />
              Nie valid
              <ChevronRight className="h-4 w-4 ml-auto" />
            </button>
          </div>
        )}
      </div>
    </>
  );
}
