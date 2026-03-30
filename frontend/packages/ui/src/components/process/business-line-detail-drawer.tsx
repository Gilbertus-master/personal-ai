'use client';

import { useState, useEffect, useCallback } from 'react';
import { X, ClipboardList, Search, ArrowRight, Settings, Wrench, MessageSquare, Loader2, Radio, Clock } from 'lucide-react';
import type { BusinessLine } from '@gilbertus/api-client';
import { logActivity, annotateItem, researchItem } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';

export interface BusinessLineDetailDrawerProps {
  line: BusinessLine;
  onClose: () => void;
}

const IMPORTANCE_CONFIG: Record<BusinessLine['importance'], { label: string; color: string }> = {
  critical: { label: 'Krytyczny', color: 'bg-red-500/20 text-red-400' },
  high: { label: 'Wysoki', color: 'bg-orange-500/20 text-orange-400' },
  medium: { label: 'Średni', color: 'bg-amber-500/20 text-amber-400' },
  low: { label: 'Niski', color: 'bg-gray-500/20 text-gray-400' },
};

const STATUS_CONFIG: Record<BusinessLine['status'], { label: string; color: string }> = {
  active: { label: 'Aktywny', color: 'bg-green-500/20 text-green-400' },
  archived: { label: 'Archiwalny', color: 'bg-gray-500/20 text-gray-400' },
  merged: { label: 'Scalony', color: 'bg-blue-500/20 text-blue-400' },
};

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('pl-PL', { day: 'numeric', month: 'long', year: 'numeric' });
}

type ActionKey = 'task' | 'research' | 'forward' | 'new_process' | 'new_tool' | 'comment';

export function BusinessLineDetailDrawer({ line, onClose }: BusinessLineDetailDrawerProps) {
  const [activeAction, setActiveAction] = useState<ActionKey | null>(null);
  const [text, setText] = useState('');
  const [forwardTo, setForwardTo] = useState('');
  const [toast, setToast] = useState<string | null>(null);
  const [researchResult, setResearchResult] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const importance = IMPORTANCE_CONFIG[line.importance];
  const status = STATUS_CONFIG[line.status];

  // Close on Escape
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [onClose]);

  // Auto-hide toast
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3000);
    return () => clearTimeout(t);
  }, [toast]);

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    setText('');
    setForwardTo('');
  }, []);

  async function handleTask() {
    if (!text.trim()) return;
    setLoading(true);
    try {
      await logActivity({
        action_type: 'task',
        item_id: String(line.id),
        item_type: 'business_line',
        item_title: line.name,
        payload: { instruction: text.trim() },
      });
      showToast('Zlecono ✓');
    } finally {
      setLoading(false);
    }
  }

  async function handleResearch() {
    setLoading(true);
    setResearchResult(null);
    try {
      const result = await researchItem({
        item_id: String(line.id),
        item_type: 'business_line',
        item_title: line.name,
        item_content: JSON.stringify(line),
        context: 'process',
      });
      setResearchResult(result.summary ?? result.result ?? JSON.stringify(result));
    } finally {
      setLoading(false);
    }
  }

  async function handleForward() {
    if (!forwardTo.trim()) return;
    setLoading(true);
    try {
      await logActivity({
        action_type: 'forward',
        item_id: String(line.id),
        item_type: 'business_line',
        item_title: line.name,
        payload: { forward_to: forwardTo.trim(), note: text.trim() },
      });
      showToast('Zlecono ✓');
    } finally {
      setLoading(false);
    }
  }

  async function handleNewProcess() {
    if (!text.trim()) return;
    setLoading(true);
    try {
      await logActivity({
        action_type: 'new_process',
        item_id: String(line.id),
        item_type: 'business_line',
        item_title: line.name,
        payload: { description: text.trim() },
      });
      showToast('Zlecono ✓');
    } finally {
      setLoading(false);
    }
  }

  async function handleNewTool() {
    if (!text.trim()) return;
    setLoading(true);
    try {
      await logActivity({
        action_type: 'new_tool',
        item_id: String(line.id),
        item_type: 'business_line',
        item_title: line.name,
        payload: { description: text.trim() },
      });
      showToast('Zlecono ✓');
    } finally {
      setLoading(false);
    }
  }

  async function handleComment() {
    if (!text.trim()) return;
    setLoading(true);
    try {
      await annotateItem({
        item_id: String(line.id),
        item_type: 'business_line',
        annotation_type: 'comment',
        content: text.trim(),
      });
      showToast('Zlecono ✓');
    } finally {
      setLoading(false);
    }
  }

  const actions: { key: ActionKey; icon: typeof ClipboardList; label: string }[] = [
    { key: 'task', icon: ClipboardList, label: 'Zlec zadanie' },
    { key: 'research', icon: Search, label: 'Głębszy research' },
    { key: 'forward', icon: ArrowRight, label: 'Przekaż osobie' },
    { key: 'new_process', icon: Settings, label: 'Nowy proces' },
    { key: 'new_tool', icon: Wrench, label: 'Nowe narzędzie' },
    { key: 'comment', icon: MessageSquare, label: 'Komentarz' },
  ];

  function renderActionForm() {
    if (!activeAction) return null;

    if (activeAction === 'research') {
      return (
        <div className="space-y-3 rounded-lg border border-[var(--accent)]/20 bg-[var(--accent)]/5 p-4">
          <h4 className="text-sm font-medium text-[var(--text)]">Głębszy research</h4>
          {loading && (
            <div className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
              <Loader2 size={14} className="animate-spin" />
              Analizuję...
            </div>
          )}
          {researchResult && (
            <div className="max-h-64 overflow-y-auto rounded-md bg-[var(--surface)] border border-[var(--border)] p-3 text-sm text-[var(--text)] whitespace-pre-wrap">
              {researchResult}
            </div>
          )}
          {!loading && !researchResult && (
            <button
              onClick={handleResearch}
              className="rounded-md bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:opacity-90"
            >
              Rozpocznij analizę
            </button>
          )}
        </div>
      );
    }

    if (activeAction === 'forward') {
      return (
        <div className="space-y-3 rounded-lg border border-[var(--accent)]/20 bg-[var(--accent)]/5 p-4">
          <h4 className="text-sm font-medium text-[var(--text)]">Przekaż osobie</h4>
          <input
            type="text"
            value={forwardTo}
            onChange={(e) => setForwardTo(e.target.value)}
            placeholder="Imię lub rola..."
            className="w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-secondary)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
          />
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={2}
            placeholder="Notatka (opcjonalnie)..."
            className="w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-secondary)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
          />
          <button
            onClick={handleForward}
            disabled={loading || !forwardTo.trim()}
            className="rounded-md bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            {loading ? 'Wysyłanie...' : 'Wyślij'}
          </button>
        </div>
      );
    }

    const placeholders: Record<string, string> = {
      task: 'Opisz zadanie dla Gilbertusa...',
      new_process: 'Opisz proces do stworzenia...',
      new_tool: 'Opisz narzędzie/integrację...',
      comment: 'Twój komentarz...',
    };

    const handlers: Record<string, () => Promise<void>> = {
      task: handleTask,
      new_process: handleNewProcess,
      new_tool: handleNewTool,
      comment: handleComment,
    };

    return (
      <div className="space-y-3 rounded-lg border border-[var(--accent)]/20 bg-[var(--accent)]/5 p-4">
        <h4 className="text-sm font-medium text-[var(--text)]">
          {actions.find((a) => a.key === activeAction)?.label}
        </h4>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={3}
          placeholder={placeholders[activeAction]}
          className="w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-secondary)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
        />
        <button
          onClick={handlers[activeAction]}
          disabled={loading || !text.trim()}
          className="rounded-md bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
        >
          {loading ? 'Wysyłanie...' : 'Wyślij'}
        </button>
      </div>
    );
  }

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 z-40 bg-black/40" onClick={onClose} />

      {/* Drawer */}
      <div className="fixed right-0 top-0 z-50 flex h-full w-[480px] max-w-full flex-col border-l border-[var(--border)] bg-[var(--surface)] shadow-2xl animate-in slide-in-from-right duration-300">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-[var(--border)] px-6 py-4">
          <div className="min-w-0 flex-1 pr-4">
            <h2 className="text-lg font-bold text-[var(--text)]">{line.name}</h2>
            <div className="mt-2 flex items-center gap-2">
              <span className={cn('rounded-full px-2.5 py-0.5 text-xs font-semibold', importance.color)}>
                {importance.label}
              </span>
              <span className={cn('rounded-full px-2.5 py-0.5 text-xs font-semibold', status.color)}>
                {status.label}
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-md p-1.5 text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text)]"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Body — scrollable */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-5">
          {/* Stats */}
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-lg border border-[var(--border)] bg-[var(--bg)] p-3 text-center">
              <div className="flex items-center justify-center gap-1 text-[var(--text-secondary)]">
                <Radio size={12} />
                <span className="text-[10px] uppercase">Sygnałów</span>
              </div>
              <p className="mt-1 text-lg font-bold text-[var(--text)]">{line.signals}</p>
            </div>
            <div className="rounded-lg border border-[var(--border)] bg-[var(--bg)] p-3 text-center">
              <div className="flex items-center justify-center gap-1 text-[var(--text-secondary)]">
                <Settings size={12} />
                <span className="text-[10px] uppercase">Procesy</span>
              </div>
              <p className="mt-1 text-lg font-bold text-[var(--text)]">—</p>
            </div>
            <div className="rounded-lg border border-[var(--border)] bg-[var(--bg)] p-3 text-center">
              <div className="flex items-center justify-center gap-1 text-[var(--text-secondary)]">
                <Clock size={12} />
                <span className="text-[10px] uppercase">Odkryto</span>
              </div>
              <p className="mt-1 text-xs font-medium text-[var(--text)]">{formatDate(line.discovered_at)}</p>
            </div>
          </div>

          {/* Description */}
          <div>
            <h3 className="mb-1 text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">Opis</h3>
            <p className="text-sm text-[var(--text)] whitespace-pre-wrap">{line.description}</p>
          </div>

          {/* Actions */}
          <div>
            <h3 className="mb-3 text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">
              Co chcesz zrobić?
            </h3>
            <div className="grid grid-cols-2 gap-2">
              {actions.map(({ key, icon: Icon, label }) => (
                <button
                  key={key}
                  onClick={() => {
                    setActiveAction(activeAction === key ? null : key);
                    setText('');
                    setForwardTo('');
                    setResearchResult(null);
                  }}
                  className={cn(
                    'flex items-center gap-2 rounded-lg border px-3 py-2.5 text-sm font-medium transition-colors text-left',
                    activeAction === key
                      ? 'border-[var(--accent)] bg-[var(--accent)]/10 text-[var(--accent)]'
                      : 'border-[var(--border)] bg-[var(--bg)] text-[var(--text)] hover:border-[var(--accent)] hover:text-[var(--accent)]',
                  )}
                >
                  <Icon size={16} />
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Active action form */}
          {renderActionForm()}
        </div>

        {/* Toast */}
        {toast && (
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white shadow-lg">
            {toast}
          </div>
        )}
      </div>
    </>
  );
}
