'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { Trash2, Check, X } from 'lucide-react';

interface ConversationMessage {
  content: string;
  role: string;
}

export interface ConversationItemProps {
  conversation: {
    id: string;
    title: string;
    lastActive: string;
    messages: ConversationMessage[];
  };
  isActive: boolean;
  onSelect: () => void;
  onDelete: () => void;
  onRename: (title: string) => void;
}

function relativeTime(iso: string): string {
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60_000);
    if (mins < 1) return 'teraz';
    if (mins < 60) return `${mins} min`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours} godz.`;
    const days = Math.floor(hours / 24);
    if (days < 7) return `${days} dn.`;
    return new Date(iso).toLocaleDateString('pl-PL', { day: '2-digit', month: '2-digit' });
  } catch {
    return '';
  }
}

export function ConversationItem({
  conversation,
  isActive,
  onSelect,
  onDelete,
  onRename,
}: ConversationItemProps) {
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(conversation.title);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editing]);

  const lastMessage = conversation.messages.length > 0
    ? conversation.messages[conversation.messages.length - 1]
    : null;

  const preview = lastMessage
    ? lastMessage.content.slice(0, 80).replace(/\n/g, ' ')
    : '';

  const handleDoubleClick = useCallback(() => {
    setEditValue(conversation.title);
    setEditing(true);
  }, [conversation.title]);

  const commitRename = useCallback(() => {
    const trimmed = editValue.trim();
    if (trimmed && trimmed !== conversation.title) {
      onRename(trimmed);
    }
    setEditing(false);
  }, [editValue, conversation.title, onRename]);

  const cancelEdit = useCallback(() => {
    setEditValue(conversation.title);
    setEditing(false);
  }, [conversation.title]);

  if (confirmDelete) {
    return (
      <div
        className={`flex items-center justify-between px-3 py-2.5 rounded-lg ${
          isActive ? 'bg-[var(--surface-hover)] border-l-2 border-[var(--accent)]' : 'bg-[var(--surface)]'
        }`}
      >
        <span className="text-sm text-[var(--text)]">Usunąć?</span>
        <div className="flex items-center gap-1">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete();
              setConfirmDelete(false);
            }}
            className="p-1 rounded hover:bg-[var(--surface-hover)] text-[var(--danger)] transition-colors"
          >
            <Check size={14} />
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              setConfirmDelete(false);
            }}
            className="p-1 rounded hover:bg-[var(--surface-hover)] text-[var(--text-secondary)] transition-colors"
          >
            <X size={14} />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onDoubleClick={handleDoubleClick}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onSelect(); }}
      className={`group w-full text-left px-3 py-2.5 rounded-lg transition-colors relative cursor-pointer ${
        isActive
          ? 'bg-[var(--surface-hover)] border-l-2 border-[var(--accent)]'
          : 'hover:bg-[var(--surface-hover)] border-l-2 border-transparent'
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          {editing ? (
            <input
              ref={inputRef}
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') commitRename();
                if (e.key === 'Escape') cancelEdit();
              }}
              onBlur={commitRename}
              onClick={(e) => e.stopPropagation()}
              className="w-full text-sm font-medium text-[var(--text)] bg-transparent border-b border-[var(--accent)] outline-none"
            />
          ) : (
            <p className="text-sm font-medium text-[var(--text)] truncate">
              {conversation.title}
            </p>
          )}
          {preview && !editing && (
            <p className="text-xs text-[var(--text-secondary)] truncate mt-0.5">
              {preview}
            </p>
          )}
        </div>

        <div className="flex items-center gap-1 shrink-0">
          <span className="text-[10px] text-[var(--text-secondary)] group-hover:hidden">
            {relativeTime(conversation.lastActive)}
          </span>
          <button
            onClick={(e) => {
              e.stopPropagation();
              setConfirmDelete(true);
            }}
            className="hidden group-hover:block p-1 rounded hover:bg-[var(--surface)] text-[var(--text-secondary)] hover:text-[var(--danger)] transition-colors"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}
