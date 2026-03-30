'use client';

import { useState, useEffect, useRef } from 'react';
import {
  X,
  Wrench,
  Ban,
  AlertTriangle,
  Info,
  AlertCircle,
  Search,
  Forward,
  ClipboardList,
  MessageSquare,
  Send,
  ChevronDown,
  ChevronUp,
  Loader2,
} from 'lucide-react';
import type { AlertItem } from '@gilbertus/api-client';
import { logActivity, researchItem, annotateItem, askGilbertus } from '@gilbertus/api-client';
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

type ActionMode = 'view' | 'fix' | 'suppress' | 'forward' | 'task' | 'comment';

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
  const [mode, setMode] = useState<ActionMode>('view');
  const [comment, setComment] = useState('');
  const [fixInstruction, setFixInstruction] = useState('');
  const [freePrompt, setFreePrompt] = useState('');
  const [forwardTo, setForwardTo] = useState('');
  const [taskText, setTaskText] = useState('');
  const [commentText, setCommentText] = useState('');
  const [researchResult, setResearchResult] = useState<string | null>(null);
  const [researchExpanded, setResearchExpanded] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [isResearching, setIsResearching] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const drawerRef = useRef<HTMLDivElement>(null);

  // Reset state when alert changes
  useEffect(() => {
    if (alert) {
      setMode('view');
      setComment('');
      setFixInstruction(alert.description || '');
      setFreePrompt('');
      setForwardTo('');
      setTaskText('');
      setCommentText('');
      setResearchResult(null);
      setIsSending(false);
      setIsResearching(false);
      setToast(null);
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

  // Auto-hide toast
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3000);
    return () => clearTimeout(t);
  }, [toast]);

  if (!alert) return null;

  const severity = SEVERITY_CONFIG[alert.severity] ?? SEVERITY_CONFIG.low;
  const SeverityIcon = severity.icon;
  const typeLabel = ALERT_TYPE_LABEL[alert.alert_type] ?? alert.alert_type;
  const evidence = formatEvidence(alert.evidence);
  const alertIdStr = String(alert.alert_id);

  function handleSubmitFix() {
    onResolve(alert!.alert_id, 'fix', comment, fixInstruction || undefined);
  }

  function handleSubmitSuppress() {
    onResolve(alert!.alert_id, 'suppress', comment);
  }

  async function handleFreePrompt() {
    if (!freePrompt.trim()) return;
    setIsSending(true);
    try {
      await logActivity({
        action_type: 'prompt',
        item_id: alertIdStr,
        item_type: 'alert',
        item_title: alert!.title,
        payload: { instruction: freePrompt },
      });
      const resp = await askGilbertus({
        query: `Alert: ${alert!.title}. ${alert!.description || ''}. Instrukcja: ${freePrompt}`,
        answer_length: 'medium',
      });
      setResearchResult(resp.answer);
      setResearchExpanded(true);
      setFreePrompt('');
      setToast('Zlecono ✓');
    } catch {
      setToast('Błąd wysyłania');
    } finally {
      setIsSending(false);
    }
  }

  async function handleResearch() {
    setIsResearching(true);
    try {
      const resp = await researchItem({
        item_id: alertIdStr,
        item_type: 'alert',
        item_title: alert!.title,
        item_content: alert!.description || undefined,
        context: evidence || undefined,
      });
      setResearchResult(resp.research_result);
      setResearchExpanded(true);
      setToast('Zbadano ✓');
    } catch {
      setToast('Błąd badania');
    } finally {
      setIsResearching(false);
    }
  }

  async function handleForward() {
    if (!forwardTo.trim()) return;
    setIsSending(true);
    try {
      await logActivity({
        action_type: 'forward',
        item_id: alertIdStr,
        item_type: 'alert',
        item_title: alert!.title,
        payload: { forward_to: forwardTo },
      });
      setToast('Przekazano ✓');
      setMode('view');
      setForwardTo('');
    } catch {
      setToast('Błąd przekazania');
    } finally {
      setIsSending(false);
    }
  }

  async function handleTask() {
    if (!taskText.trim()) return;
    setIsSending(true);
    try {
      await logActivity({
        action_type: 'task',
        item_id: alertIdStr,
        item_type: 'alert',
        item_title: alert!.title,
        payload: { task_description: taskText },
      });
      setToast('Zadanie utworzone ✓');
      setMode('view');
      setTaskText('');
    } catch {
      setToast('Błąd tworzenia zadania');
    } finally {
      setIsSending(false);
    }
  }

  async function handleComment() {
    if (!commentText.trim()) return;
    setIsSending(true);
    try {
      await annotateItem({
        item_id: alertIdStr,
        item_type: 'alert',
        annotation_type: 'comment',
        content: commentText,
      });
      setToast('Komentarz dodany ✓');
      setMode('view');
      setCommentText('');
    } catch {
      setToast('Błąd komentarza');
    } finally {
      setIsSending(false);
    }
  }

  const quickActions = [
    { icon: Search, label: 'Zbadaj głębiej', onClick: handleResearch, loading: isResearching },
    { icon: Ban, label: 'False positive', onClick: () => setMode('suppress') },
    { icon: Wrench, label: 'Napraw', onClick: () => setMode('fix') },
    { icon: Forward, label: 'Przekaż dalej', onClick: () => setMode('forward') },
    { icon: ClipboardList, label: 'Nowe zadanie', onClick: () => setMode('task') },
    { icon: MessageSquare, label: 'Komentarz', onClick: () => setMode('comment') },
  ];

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
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-5">
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

          {/* FREE-FORM PROMPT */}
          <div className="space-y-2">
            <h3 className="text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">
              Co chcesz zrobić?
            </h3>
            <textarea
              value={freePrompt}
              onChange={(e) => setFreePrompt(e.target.value)}
              rows={3}
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2.5 text-sm text-[var(--text)] placeholder:text-[var(--text-secondary)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50 focus:border-[var(--accent)] resize-none"
              placeholder='Napisz co Gilbertus ma zrobić z tym alertem... (np. "Zbadaj dlaczego calendar jest DEAD", "Przekaż Rochowi że to nie jest problem", "Stwórz zadanie auto-naprawy")'
            />
            <button
              onClick={handleFreePrompt}
              disabled={isSending || !freePrompt.trim()}
              className="flex items-center gap-2 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed transition-opacity"
            >
              {isSending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              Wyślij do Gilbertusa
            </button>
          </div>

          {/* Quick actions grid */}
          <div>
            <h3 className="mb-2 text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">
              Szybkie akcje
            </h3>
            <div className="grid grid-cols-3 gap-2">
              {quickActions.map((action) => {
                const Icon = action.icon;
                return (
                  <button
                    key={action.label}
                    onClick={action.onClick}
                    disabled={action.loading}
                    className="flex flex-col items-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-3 text-xs text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text)] hover:border-[var(--accent)]/40 transition-all disabled:opacity-50"
                  >
                    {action.loading ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Icon className="h-4 w-4" />
                    )}
                    <span className="font-medium">{action.label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Expandable action panels */}
          {mode === 'fix' && (
            <div className="space-y-3 rounded-lg border border-blue-500/20 bg-blue-500/5 p-4">
              <h3 className="text-sm font-medium text-blue-400">Instrukcja naprawy</h3>
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
                  {isResolving ? 'Wysyłanie...' : 'Zatwierdź naprawę'}
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

          {mode === 'suppress' && (
            <div className="space-y-3 rounded-lg border border-red-500/20 bg-red-500/5 p-4">
              <h3 className="text-sm font-medium text-red-400">False positive / Suppresja</h3>
              <p className="text-xs text-[var(--text-secondary)]">
                Wszystkie przyszłe alerty typu <strong>{typeLabel}</strong> zostaną zignorowane.
              </p>
              <textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                rows={2}
                className="w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-secondary)] focus:outline-none focus:ring-1 focus:ring-red-500"
                placeholder="Powód suppresji..."
              />
              <div className="flex gap-2">
                <button
                  onClick={handleSubmitSuppress}
                  disabled={isResolving || !comment.trim()}
                  className="flex items-center gap-2 rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Ban className="h-4 w-4" />
                  {isResolving ? 'Wysyłanie...' : 'Potwierdź suppresję'}
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

          {mode === 'forward' && (
            <div className="space-y-3 rounded-lg border border-[var(--accent)]/20 bg-[var(--accent)]/5 p-4">
              <h3 className="text-sm font-medium text-[var(--accent)]">Przekaż dalej</h3>
              <input
                value={forwardTo}
                onChange={(e) => setForwardTo(e.target.value)}
                className="w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-secondary)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
                placeholder="Komu przekazać? (np. Roch, Krystian...)"
              />
              <div className="flex gap-2">
                <button
                  onClick={handleForward}
                  disabled={isSending || !forwardTo.trim()}
                  className="flex items-center gap-2 rounded-md bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Forward className="h-4 w-4" />
                  {isSending ? 'Wysyłanie...' : 'Przekaż'}
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

          {mode === 'task' && (
            <div className="space-y-3 rounded-lg border border-green-500/20 bg-green-500/5 p-4">
              <h3 className="text-sm font-medium text-green-400">Nowe zadanie</h3>
              <textarea
                value={taskText}
                onChange={(e) => setTaskText(e.target.value)}
                rows={3}
                className="w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-secondary)] focus:outline-none focus:ring-1 focus:ring-green-500"
                placeholder="Opis zadania..."
              />
              <div className="flex gap-2">
                <button
                  onClick={handleTask}
                  disabled={isSending || !taskText.trim()}
                  className="flex items-center gap-2 rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <ClipboardList className="h-4 w-4" />
                  {isSending ? 'Tworzenie...' : 'Utwórz zadanie'}
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

          {mode === 'comment' && (
            <div className="space-y-3 rounded-lg border border-purple-500/20 bg-purple-500/5 p-4">
              <h3 className="text-sm font-medium text-purple-400">Komentarz</h3>
              <textarea
                value={commentText}
                onChange={(e) => setCommentText(e.target.value)}
                rows={3}
                className="w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-secondary)] focus:outline-none focus:ring-1 focus:ring-purple-500"
                placeholder="Twój komentarz..."
              />
              <div className="flex gap-2">
                <button
                  onClick={handleComment}
                  disabled={isSending || !commentText.trim()}
                  className="flex items-center gap-2 rounded-md bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <MessageSquare className="h-4 w-4" />
                  {isSending ? 'Wysyłanie...' : 'Dodaj komentarz'}
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

          {/* Research result */}
          {researchResult && (
            <div className="rounded-lg border border-[var(--accent)]/30 bg-[var(--accent)]/5 p-4">
              <button
                onClick={() => setResearchExpanded((p) => !p)}
                className="flex w-full items-center justify-between"
              >
                <p className="text-xs font-medium text-[var(--accent)]">Odpowiedź Gilbertusa</p>
                {researchExpanded ? (
                  <ChevronUp className="h-4 w-4 text-[var(--accent)]" />
                ) : (
                  <ChevronDown className="h-4 w-4 text-[var(--accent)]" />
                )}
              </button>
              {researchExpanded && (
                <p className="mt-2 text-sm text-[var(--text)] whitespace-pre-wrap">{researchResult}</p>
              )}
            </div>
          )}
        </div>

        {/* Toast */}
        {toast && (
          <div className="absolute bottom-20 left-1/2 -translate-x-1/2 rounded-lg bg-[var(--surface)] border border-[var(--border)] px-4 py-2 text-sm text-[var(--text)] shadow-lg">
            {toast}
          </div>
        )}
      </div>
    </>
  );
}
