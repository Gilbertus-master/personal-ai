'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { SendHorizontal, Paperclip } from 'lucide-react';
import { QuickActions } from './quick-actions';

export interface ChatInputProps {
  onSend: (message: string) => void;
  onQuickAction: (action: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export function ChatInput({
  onSend,
  onQuickAction,
  disabled = false,
  placeholder = 'Napisz wiadomość...',
}: ChatInputProps) {
  const [value, setValue] = useState('');
  const [showQuickActions, setShowQuickActions] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const resize = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    const lineHeight = 24; // ~text-sm line height
    const maxHeight = lineHeight * 6;
    el.style.height = `${Math.min(el.scrollHeight, maxHeight)}px`;
  }, []);

  useEffect(() => {
    resize();
  }, [value, resize]);

  const handleSend = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue('');
    // Reset height after clearing
    requestAnimationFrame(() => {
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    });
  }, [value, disabled, onSend]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  const handleChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const v = e.target.value;
    setValue(v);

    // Show quick actions when "/" is typed at start
    if (v === '/') {
      setShowQuickActions(true);
    } else if (!v.startsWith('/') || v.includes(' ')) {
      setShowQuickActions(false);
    }
  }, []);

  const handleQuickAction = useCallback(
    (action: string) => {
      setShowQuickActions(false);
      setValue('');
      onQuickAction(action);
    },
    [onQuickAction],
  );

  const canSend = value.trim().length > 0 && !disabled;

  return (
    <div className="relative border-t border-[var(--border)] bg-[var(--surface)]">
      {/* Quick actions menu */}
      {showQuickActions && (
        <div className="absolute bottom-full left-0 right-0 mx-3 mb-1 rounded-lg border border-[var(--border)] bg-[var(--surface)] shadow-lg z-10">
          <QuickActions variant="menu" onAction={handleQuickAction} />
        </div>
      )}

      <div className="flex items-end gap-2 p-3">
        {/* Attachment placeholder */}
        <button
          disabled
          className="p-2 rounded-lg text-[var(--text-secondary)] opacity-40 cursor-not-allowed shrink-0"
          title="Wkrótce"
        >
          <Paperclip size={18} />
        </button>

        {/* Textarea */}
        <textarea
          ref={textareaRef}
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder={placeholder}
          rows={1}
          className="flex-1 resize-none text-sm text-[var(--text)] placeholder:text-[var(--text-secondary)] bg-transparent outline-none py-2 leading-6"
        />

        {/* Send button */}
        <button
          onClick={handleSend}
          disabled={!canSend}
          className={`p-2 rounded-lg shrink-0 transition-colors ${
            canSend
              ? 'bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white'
              : 'text-[var(--text-secondary)] opacity-40 cursor-not-allowed'
          }`}
        >
          <SendHorizontal size={18} />
        </button>
      </div>

      {/* Safe area padding */}
      <div className="pb-[env(safe-area-inset-bottom)]" />
    </div>
  );
}
