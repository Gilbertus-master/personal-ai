'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import {
  MoreHorizontal,
  Search,
  MessageSquare,
  Star,
  ClipboardList,
  Ban,
  ArrowRight,
  Loader2,
  ChevronDown,
  ChevronUp,
  Send,
} from 'lucide-react';
import { cn } from '../../lib/utils';
import {
  logActivity,
  annotateItem,
  researchItem,
  getItemAnnotations,
} from '@gilbertus/api-client';
import type { Annotation } from '@gilbertus/api-client';
import { showToast } from './toast-notification';

interface ActionableItemProps {
  itemId: string;
  itemType: string;
  itemTitle: string;
  itemContent?: unknown;
  context?: string;
  children: React.ReactNode;
  className?: string;
}

export function ActionableItem({
  itemId,
  itemType,
  itemTitle,
  itemContent,
  context,
  children,
  className,
}: ActionableItemProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [activePanel, setActivePanel] = useState<string | null>(null);
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [annotationCount, setAnnotationCount] = useState(0);
  const [researchResult, setResearchResult] = useState<string | null>(null);
  const [researchLoading, setResearchLoading] = useState(false);
  const [researchExpanded, setResearchExpanded] = useState(true);
  const [comment, setComment] = useState('');
  const [rating, setRating] = useState(0);
  const [ratingReason, setRatingReason] = useState('');
  const [taskInstruction, setTaskInstruction] = useState('');
  const [flagReason, setFlagReason] = useState('');
  const [forwardTo, setForwardTo] = useState('');
  const [forwardNote, setForwardNote] = useState('');
  const [saving, setSaving] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  // Load annotation count on mount
  useEffect(() => {
    getItemAnnotations(itemType, itemId)
      .then((data) => setAnnotationCount(data.length))
      .catch(() => {});
  }, [itemType, itemId]);

  const closeMenu = useCallback(() => {
    setMenuOpen(false);
  }, []);

  // Close menu on click outside
  useEffect(() => {
    if (!menuOpen) return;
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        closeMenu();
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [menuOpen, closeMenu]);

  // Close on Escape
  useEffect(() => {
    if (!menuOpen && !activePanel) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        closeMenu();
        setActivePanel(null);
      }
    }
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [menuOpen, activePanel, closeMenu]);

  const handleResearch = async () => {
    setActivePanel('research');
    setMenuOpen(false);
    setResearchLoading(true);
    setResearchResult(null);
    try {
      const contentStr = itemContent ? JSON.stringify(itemContent).slice(0, 2000) : undefined;
      const res = await researchItem({
        item_id: itemId,
        item_type: itemType,
        item_title: itemTitle,
        item_content: contentStr,
        context,
      });
      setResearchResult(res.research_result);
      setAnnotationCount((c) => c + 1);
      showToast('Badanie zakończone');
    } catch {
      showToast('Błąd podczas badania', 'error');
    } finally {
      setResearchLoading(false);
    }
  };

  const handleComment = async () => {
    if (!comment.trim()) return;
    setSaving(true);
    try {
      await annotateItem({
        item_id: itemId,
        item_type: itemType,
        annotation_type: 'comment',
        content: comment,
      });
      await logActivity({
        action_type: 'comment',
        item_id: itemId,
        item_type: itemType,
        item_title: itemTitle,
        item_context: context,
        payload: { comment },
      });
      setComment('');
      setActivePanel(null);
      setAnnotationCount((c) => c + 1);
      showToast('Komentarz zapisany');
    } catch {
      showToast('Błąd zapisu', 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleRate = async () => {
    if (rating === 0) return;
    setSaving(true);
    try {
      await annotateItem({
        item_id: itemId,
        item_type: itemType,
        annotation_type: 'rating',
        rating,
        content: ratingReason || undefined,
      });
      await logActivity({
        action_type: 'rate',
        item_id: itemId,
        item_type: itemType,
        item_title: itemTitle,
        item_context: context,
        payload: { rating, reason: ratingReason },
      });
      setRating(0);
      setRatingReason('');
      setActivePanel(null);
      setAnnotationCount((c) => c + 1);
      showToast('Ocena zapisana');
    } catch {
      showToast('Błąd zapisu', 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleTask = async () => {
    if (!taskInstruction.trim()) return;
    setSaving(true);
    try {
      await logActivity({
        action_type: 'task',
        item_id: itemId,
        item_type: itemType,
        item_title: itemTitle,
        item_context: context,
        payload: { instruction: taskInstruction },
      });
      setTaskInstruction('');
      setActivePanel(null);
      showToast('Zadanie zlecone');
    } catch {
      showToast('Błąd zapisu', 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleFlag = async () => {
    setSaving(true);
    try {
      await annotateItem({
        item_id: itemId,
        item_type: itemType,
        annotation_type: 'flag',
        is_false_positive: true,
        content: flagReason || undefined,
      });
      await logActivity({
        action_type: 'flag',
        item_id: itemId,
        item_type: itemType,
        item_title: itemTitle,
        item_context: context,
        payload: { reason: flagReason, is_false_positive: true },
      });
      setFlagReason('');
      setActivePanel(null);
      setAnnotationCount((c) => c + 1);
      showToast('Oznaczono jako błędne');
    } catch {
      showToast('Błąd zapisu', 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleForward = async () => {
    if (!forwardTo.trim()) return;
    setSaving(true);
    try {
      await annotateItem({
        item_id: itemId,
        item_type: itemType,
        annotation_type: 'forward',
        forward_to: forwardTo,
        content: forwardNote || undefined,
      });
      await logActivity({
        action_type: 'forward',
        item_id: itemId,
        item_type: itemType,
        item_title: itemTitle,
        item_context: context,
        payload: { forward_to: forwardTo, note: forwardNote },
      });
      setForwardTo('');
      setForwardNote('');
      setActivePanel(null);
      setAnnotationCount((c) => c + 1);
      showToast('Przekazano');
    } catch {
      showToast('Błąd zapisu', 'error');
    } finally {
      setSaving(false);
    }
  };

  const menuItems = [
    { key: 'research', icon: Search, label: 'Zbadaj głębiej', action: handleResearch },
    { key: 'comment', icon: MessageSquare, label: 'Dodaj komentarz', action: () => { setActivePanel('comment'); setMenuOpen(false); } },
    { key: 'rate', icon: Star, label: 'Oceń', action: () => { setActivePanel('rate'); setMenuOpen(false); } },
    { key: 'task', icon: ClipboardList, label: 'Zlec zadanie', action: () => { setActivePanel('task'); setMenuOpen(false); } },
    { key: 'flag', icon: Ban, label: 'Błędne wskazanie', action: () => { setActivePanel('flag'); setMenuOpen(false); } },
    { key: 'forward', icon: ArrowRight, label: 'Przekaż dalej', action: () => { setActivePanel('forward'); setMenuOpen(false); } },
  ];

  return (
    <div ref={containerRef} className={cn('group/actionable relative', className)}>
      {/* Children content */}
      {children}

      {/* Annotation badge */}
      {annotationCount > 0 && (
        <span className="absolute top-1 right-10 flex items-center gap-0.5 rounded-full bg-[var(--accent)]/10 px-1.5 py-0.5 text-[10px] font-medium text-[var(--accent)]">
          <MessageSquare className="h-2.5 w-2.5" />
          {annotationCount}
        </span>
      )}

      {/* Menu trigger */}
      <div ref={menuRef} className="absolute top-1 right-1 z-40">
        <button
          type="button"
          onClick={() => setMenuOpen((p) => !p)}
          className={cn(
            'rounded-md p-1 text-[var(--text-secondary)] transition-all',
            'hover:bg-[var(--surface-hover)] hover:text-[var(--text)]',
            menuOpen ? 'opacity-100' : 'opacity-0 group-hover/actionable:opacity-100',
          )}
          aria-label="Akcje"
        >
          <MoreHorizontal className="h-4 w-4" />
        </button>

        {/* Dropdown menu */}
        {menuOpen && (
          <div className="absolute right-0 top-full mt-1 w-52 rounded-lg border border-[var(--border)] bg-[var(--surface)] shadow-xl z-50">
            {menuItems.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.key}
                  type="button"
                  onClick={item.action}
                  className="flex w-full items-center gap-2.5 px-3 py-2 text-sm text-[var(--text-secondary)] transition-colors hover:bg-[var(--surface-hover)] hover:text-[var(--text)] first:rounded-t-lg last:rounded-b-lg"
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  {item.label}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Inline panels */}
      {activePanel === 'research' && (
        <div className="mt-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3">
          <button
            type="button"
            onClick={() => setResearchExpanded((p) => !p)}
            className="flex w-full items-center justify-between text-sm font-medium text-[var(--text)]"
          >
            <span className="flex items-center gap-2">
              <Search className="h-4 w-4 text-[var(--accent)]" />
              Wyniki badania
            </span>
            {researchExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
          {researchExpanded && (
            <div className="mt-2">
              {researchLoading ? (
                <div className="flex items-center gap-2 py-4 text-sm text-[var(--text-secondary)]">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Analizuję...
                </div>
              ) : researchResult ? (
                <div className="prose prose-sm prose-invert max-w-none text-sm text-[var(--text-secondary)] whitespace-pre-wrap">
                  {researchResult}
                </div>
              ) : null}
            </div>
          )}
        </div>
      )}

      {activePanel === 'comment' && (
        <div className="mt-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3">
          <p className="mb-2 text-sm font-medium text-[var(--text)]">Dodaj komentarz</p>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Twój komentarz..."
            rows={3}
            className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-muted)] focus:border-[var(--accent)] focus:outline-none"
          />
          <div className="mt-2 flex justify-end gap-2">
            <button type="button" onClick={() => setActivePanel(null)} className="rounded-md px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]">
              Anuluj
            </button>
            <button type="button" onClick={handleComment} disabled={saving || !comment.trim()} className="flex items-center gap-1.5 rounded-md bg-[var(--accent)] px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50">
              {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Send className="h-3 w-3" />}
              Zapisz
            </button>
          </div>
        </div>
      )}

      {activePanel === 'rate' && (
        <div className="mt-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3">
          <p className="mb-2 text-sm font-medium text-[var(--text)]">Oceń</p>
          <div className="flex gap-1 mb-2">
            {[1, 2, 3, 4, 5].map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setRating(s)}
                className={cn(
                  'text-lg transition-colors',
                  s <= rating ? 'text-amber-400' : 'text-[var(--border)] hover:text-amber-400/50',
                )}
              >
                ★
              </button>
            ))}
          </div>
          <input
            value={ratingReason}
            onChange={(e) => setRatingReason(e.target.value)}
            placeholder="Powód (opcjonalnie)..."
            className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-muted)] focus:border-[var(--accent)] focus:outline-none"
          />
          <div className="mt-2 flex justify-end gap-2">
            <button type="button" onClick={() => setActivePanel(null)} className="rounded-md px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]">
              Anuluj
            </button>
            <button type="button" onClick={handleRate} disabled={saving || rating === 0} className="flex items-center gap-1.5 rounded-md bg-[var(--accent)] px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50">
              {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Send className="h-3 w-3" />}
              Zapisz
            </button>
          </div>
        </div>
      )}

      {activePanel === 'task' && (
        <div className="mt-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3">
          <p className="mb-2 text-sm font-medium text-[var(--text)]">Zlec zadanie</p>
          <textarea
            value={taskInstruction}
            onChange={(e) => setTaskInstruction(e.target.value)}
            placeholder="Instrukcja zadania..."
            rows={3}
            className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-muted)] focus:border-[var(--accent)] focus:outline-none"
          />
          <div className="mt-2 flex justify-end gap-2">
            <button type="button" onClick={() => setActivePanel(null)} className="rounded-md px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]">
              Anuluj
            </button>
            <button type="button" onClick={handleTask} disabled={saving || !taskInstruction.trim()} className="flex items-center gap-1.5 rounded-md bg-[var(--accent)] px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50">
              {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <ClipboardList className="h-3 w-3" />}
              Zlec
            </button>
          </div>
        </div>
      )}

      {activePanel === 'flag' && (
        <div className="mt-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3">
          <p className="mb-2 text-sm font-medium text-[var(--text)]">Oznacz jako błędne wskazanie</p>
          <textarea
            value={flagReason}
            onChange={(e) => setFlagReason(e.target.value)}
            placeholder="Powód (opcjonalnie)..."
            rows={2}
            className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-muted)] focus:border-[var(--accent)] focus:outline-none"
          />
          <div className="mt-2 flex justify-end gap-2">
            <button type="button" onClick={() => setActivePanel(null)} className="rounded-md px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]">
              Anuluj
            </button>
            <button type="button" onClick={handleFlag} disabled={saving} className="flex items-center gap-1.5 rounded-md bg-red-500 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50">
              {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Ban className="h-3 w-3" />}
              Oznacz
            </button>
          </div>
        </div>
      )}

      {activePanel === 'forward' && (
        <div className="mt-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3">
          <p className="mb-2 text-sm font-medium text-[var(--text)]">Przekaż dalej</p>
          <input
            value={forwardTo}
            onChange={(e) => setForwardTo(e.target.value)}
            placeholder="Imię i nazwisko osoby..."
            className="mb-2 w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-muted)] focus:border-[var(--accent)] focus:outline-none"
          />
          <textarea
            value={forwardNote}
            onChange={(e) => setForwardNote(e.target.value)}
            placeholder="Notatka (opcjonalnie)..."
            rows={2}
            className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-muted)] focus:border-[var(--accent)] focus:outline-none"
          />
          <div className="mt-2 flex justify-end gap-2">
            <button type="button" onClick={() => setActivePanel(null)} className="rounded-md px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]">
              Anuluj
            </button>
            <button type="button" onClick={handleForward} disabled={saving || !forwardTo.trim()} className="flex items-center gap-1.5 rounded-md bg-[var(--accent)] px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50">
              {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <ArrowRight className="h-3 w-3" />}
              Przekaż
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
