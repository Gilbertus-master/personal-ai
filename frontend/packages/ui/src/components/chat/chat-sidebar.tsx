'use client';

import { useState, useMemo } from 'react';
import { Plus, Search } from 'lucide-react';
import { ConversationItem } from './conversation-item';

interface ConversationMessage {
  content: string;
  role: string;
}

interface Conversation {
  id: string;
  title: string;
  lastActive: string;
  messages: ConversationMessage[];
}

export interface ChatSidebarProps {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onRename: (id: string, title: string) => void;
}

export function ChatSidebar({
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete,
  onRename,
}: ChatSidebarProps) {
  const [search, setSearch] = useState('');

  const filtered = useMemo(() => {
    const sorted = [...conversations].sort(
      (a, b) => b.lastActive.localeCompare(a.lastActive),
    );
    if (!search.trim()) return sorted;
    const q = search.trim().toLowerCase();
    return sorted.filter((c) => c.title.toLowerCase().includes(q));
  }, [conversations, search]);

  return (
    <div className="w-72 h-full flex flex-col bg-[var(--surface)] border-r border-[var(--border)]">
      {/* New conversation button */}
      <div className="p-3">
        <button
          onClick={onNew}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white text-sm font-medium transition-colors"
        >
          <Plus size={16} />
          Nowa rozmowa
        </button>
      </div>

      {/* Search */}
      <div className="px-3 pb-2">
        <div className="relative">
          <Search
            size={14}
            className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-secondary)]"
          />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Szukaj..."
            className="w-full pl-8 pr-3 py-1.5 text-sm rounded-lg bg-[var(--bg)] border border-[var(--border)] text-[var(--text)] placeholder:text-[var(--text-secondary)] outline-none focus:border-[var(--accent)] transition-colors"
          />
        </div>
      </div>

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto px-2 pb-2 space-y-0.5">
        {filtered.length === 0 ? (
          <p className="text-sm text-[var(--text-secondary)] text-center py-8">
            Brak rozmów
          </p>
        ) : (
          filtered.map((conv) => (
            <ConversationItem
              key={conv.id}
              conversation={conv}
              isActive={conv.id === activeId}
              onSelect={() => onSelect(conv.id)}
              onDelete={() => onDelete(conv.id)}
              onRename={(title) => onRename(conv.id, title)}
            />
          ))
        )}
      </div>
    </div>
  );
}
