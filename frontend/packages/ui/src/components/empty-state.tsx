'use client';

import type { ReactNode } from 'react';

interface EmptyStateProps {
  icon: ReactNode;
  title: string;
  description: string;
  action?: { label: string; onClick: () => void };
}

export function GenericEmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex min-h-[200px] flex-col items-center justify-center gap-3 p-8 text-center">
      <div className="text-[var(--text-secondary)]" style={{ fontSize: 48, lineHeight: 1 }}>
        {icon}
      </div>
      <h3 className="text-lg font-medium text-[var(--text)]">{title}</h3>
      <p className="max-w-sm text-sm text-[var(--text-secondary)]">{description}</p>
      {action && (
        <button
          onClick={action.onClick}
          className="mt-2 rounded-md bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:bg-[var(--accent-hover)] transition-colors"
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
