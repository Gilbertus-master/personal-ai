'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { PanelLeft } from 'lucide-react';

export interface ChatHeaderProps {
  title: string;
  onRename: (title: string) => void;
  onToggleSidebar?: () => void;
}

export function ChatHeader({ title, onRename, onToggleSidebar }: ChatHeaderProps) {
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(title);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editing]);

  // Sync editValue when title changes externally
  useEffect(() => {
    if (!editing) setEditValue(title);
  }, [title, editing]);

  const commitRename = useCallback(() => {
    const trimmed = editValue.trim();
    if (trimmed && trimmed !== title) {
      onRename(trimmed);
    }
    setEditing(false);
  }, [editValue, title, onRename]);

  return (
    <div className="h-14 flex items-center gap-3 px-4 border-b border-[var(--border)] bg-[var(--surface)]">
      {/* Mobile sidebar toggle */}
      {onToggleSidebar && (
        <button
          onClick={onToggleSidebar}
          className="md:hidden p-1.5 rounded-lg hover:bg-[var(--surface-hover)] text-[var(--text-secondary)] transition-colors"
        >
          <PanelLeft size={18} />
        </button>
      )}

      {/* Title — click to edit */}
      <div className="flex-1 min-w-0">
        {editing ? (
          <input
            ref={inputRef}
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') commitRename();
              if (e.key === 'Escape') {
                setEditValue(title);
                setEditing(false);
              }
            }}
            onBlur={commitRename}
            className="w-full text-sm font-semibold text-[var(--text)] bg-transparent border-b border-[var(--accent)] outline-none"
          />
        ) : (
          <button
            onClick={() => {
              setEditValue(title);
              setEditing(true);
            }}
            className="text-sm font-semibold text-[var(--text)] truncate block max-w-full hover:text-[var(--accent)] transition-colors"
            title="Kliknij aby zmienić nazwę"
          >
            {title}
          </button>
        )}
      </div>
    </div>
  );
}
