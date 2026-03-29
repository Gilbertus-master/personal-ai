'use client';

import { Brain } from 'lucide-react';
import { QuickActions } from './quick-actions';

interface EmptyStateProps {
  onQuickAction: (action: string) => void;
}

export function EmptyState({ onQuickAction }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center h-full px-4">
      <div className="max-w-2xl w-full flex flex-col items-center text-center gap-6">
        <div className="w-16 h-16 rounded-2xl bg-[var(--accent)]/10 flex items-center justify-center">
          <Brain size={32} className="text-[var(--accent)]" />
        </div>

        <div>
          <h2 className="text-2xl font-semibold text-[var(--text)]">
            Cześć! Jestem Gilbertus.
          </h2>
          <p className="mt-1 text-[var(--text-secondary)]">
            Jak mogę Ci dzisiaj pomóc?
          </p>
        </div>

        <QuickActions variant="grid" onAction={onQuickAction} />
      </div>
    </div>
  );
}
