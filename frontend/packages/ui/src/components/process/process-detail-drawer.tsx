'use client';

import { useState, useEffect, useCallback } from 'react';
import { X, ClipboardList, Search, ArrowRight, Settings, Wrench, MessageSquare, Loader2 } from 'lucide-react';
import type { DiscoveredProcess } from '@gilbertus/api-client';
import { logActivity, annotateItem, researchItem } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';

export interface ProcessDetailDrawerProps {
  process: DiscoveredProcess;
  onClose: () => void;
}

const TYPE_CONFIG: Record<DiscoveredProcess['process_type'], { label: string; color: string }> = {
  decision: { label: 'Decyzja', color: 'bg-blue-500/20 text-blue-400' },
  approval: { label: 'Zatwierdzenie', color: 'bg-purple-500/20 text-purple-400' },
  reporting: { label: 'Raportowanie', color: 'bg-cyan-500/20 text-cyan-400' },
  trading: { label: 'Trading', color: 'bg-green-500/20 text-green-400' },
  compliance: { label: 'Compliance', color: 'bg-orange-500/20 text-orange-400' },
  communication: { label: 'Komunikacja', color: 'bg-teal-500/20 text-teal-400' },
  operational: { label: 'Operacyjny', color: 'bg-amber-500/20 text-amber-400' },
};

const FREQUENCY_CONFIG: Record<DiscoveredProcess['frequency'], string> = {
  daily: 'Codziennie',
  weekly: 'Co tydzień',
  monthly: 'Co miesiąc',
  quarterly: 'Kwartalnie',
  ad_hoc: 'Ad hoc',
};

const STATUS_CONFIG: Record<DiscoveredProcess['status'], { label: string; color: string }> = {
  discovered: { label: 'Odkryty', color: 'bg-blue-500/20 text-blue-400' },
  confirmed: { label: 'Potwierdzony', color: 'bg-green-500/20 text-green-400' },
  automated: { label: 'Zautomatyzowany', color: 'bg-emerald-500/20 text-emerald-400' },
  archived: { label: 'Archiwalny', color: 'bg-gray-500/20 text-gray-400' },
};

function automationColor(pct: number): string {
  if (pct >= 70) return 'bg-green-500';
  if (pct >= 40) return 'bg-amber-500';
  return 'bg-red-500';
}

type ActionKey = 'task' | 'research' | 'forward' | 'new_process' | 'new_tool' | 'comment';

export function ProcessDetailDrawer({ process, onClose }: ProcessDetailDrawerProps) {
  const [activeAction, setActiveAction] = useState<ActionKey | null>(null);
  const [text, setText] = useState('');
  const [forwardTo, setForwardTo] = useState('');
  const [toast, setToast] = useState<string | null>(null);
  const [researchResult, setResearchResult] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const typeConfig = TYPE_CONFIG[process.process_type];
  const status = STATUS_CONFIG[process.status];
  const pct = Math.round(process.automation_potential);

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [onClose]);

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

  const itemBase = {
    item_id: String(process.id),
    item_type: 'process' as const,
    item_title: process.name,
  };

  async function handleTask() {
    if (!text.trim()) return;
    setLoading(true);
    try {
      await logActivity({ ...itemBase, action_type: 'task', payload: { instruction: text.trim() } });
      showToast('Zlecono ✓');
    } finally { setLoading(false); }
  }

  async function handleResearch() {
    setLoading(true);
    setResearchResult(null);
    try {
      const result = await researchItem({
        ...itemBase,
        item_content: JSON.stringify(process),
        context: 'process',
      });
      setResearchResult(result.research_result ?? JSON.stringify(result));
    } finally { setLoading(false); }
  }

  async function handleForward() {
    if (!forwardTo.trim()) return;
    setLoading(true);
    try {
      await logActivity({ ...itemBase, action_type: 'forward', payload: { forward_to: forwardTo.trim(), note: text.trim() } });
      showToast('Zlecono ✓');
    } finally { setLoading(false); }
  }

  async function handleNewProcess() {
    if (!text.trim()) return;
    setLoading(true);
    try {
      await logActivity({ ...itemBase, action_type: 'new_process', payload: { description: text.trim() } });
      showToast('Zlecono ✓');
    } finally { setLoading(false); }
  }

  async function handleNewTool() {
    if (!text.trim()) return;
    setLoading(true);
    try {
      await logActivity({ ...itemBase, action_type: 'new_tool', payload: { description: text.trim() } });
      showToast('Zlecono ✓');
    } finally { setLoading(false); }
  }

  async function handleComment() {
    if (!text.trim()) return;
    setLoading(true);
    try {
      await annotateItem({ item_id: String(process.id), item_type: 'process', annotation_type: 'comment', content: text.trim() });
      showToast('Zlecono ✓');
    } finally { setLoading(false); }
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
            <button onClick={handleResearch} className="rounded-md bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:opacity-90">
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
      <div className="fixed inset-0 z-40 bg-black/40" onClick={onClose} />

      <div className="fixed right-0 top-0 z-50 flex h-full w-[480px] max-w-full flex-col border-l border-[var(--border)] bg-[var(--surface)] shadow-2xl animate-in slide-in-from-right duration-300">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-[var(--border)] px-6 py-4">
          <div className="min-w-0 flex-1 pr-4">
            <h2 className="text-lg font-bold text-[var(--text)]">{process.name}</h2>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <span className={cn('rounded-full px-2.5 py-0.5 text-xs font-semibold', typeConfig.color)}>
                {typeConfig.label}
              </span>
              <span className="rounded-full bg-[var(--bg-hover)] px-2.5 py-0.5 text-xs text-[var(--text-secondary)]">
                {FREQUENCY_CONFIG[process.frequency]}
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

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-5">
          {/* Automation potential */}
          <div className="rounded-lg border border-[var(--border)] bg-[var(--bg)] p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">
                Potencjał automatyzacji
              </span>
              <span className="text-lg font-bold text-[var(--text)]">{pct}%</span>
            </div>
            <div className="h-2 rounded-full bg-[var(--border)]">
              <div
                className={cn('h-full rounded-full transition-all', automationColor(pct))}
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>

          {/* Description */}
          <div>
            <h3 className="mb-1 text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">Opis</h3>
            <p className="text-sm text-[var(--text)] whitespace-pre-wrap">{process.description}</p>
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

          {renderActionForm()}
        </div>

        {toast && (
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white shadow-lg">
            {toast}
          </div>
        )}
      </div>
    </>
  );
}
