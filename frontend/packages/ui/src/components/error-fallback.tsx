'use client';

import { AlertTriangle } from 'lucide-react';
import { cn } from '../lib/utils';

interface ErrorFallbackProps {
  error: Error;
  resetErrorBoundary: () => void;
  moduleName?: string;
}

export function ErrorFallback({
  error,
  resetErrorBoundary,
  moduleName,
}: ErrorFallbackProps) {
  return (
    <div className="flex min-h-[300px] items-center justify-center p-6">
      <div
        className={cn(
          'w-full max-w-md rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6',
          'border-l-4 border-l-[var(--danger)]',
        )}
      >
        <div className="mb-4 flex items-center gap-3">
          <AlertTriangle className="h-6 w-6 shrink-0 text-[var(--danger)]" />
          <h3 className="text-lg font-medium text-[var(--text)]">
            {moduleName
              ? `Blad w module: ${moduleName}`
              : 'Cos poszlo nie tak'}
          </h3>
        </div>

        <p className="mb-6 text-sm text-[var(--text-secondary)]">
          {error.message}
        </p>

        <div className="flex items-center gap-3">
          <button
            onClick={resetErrorBoundary}
            className="rounded-md bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:bg-[var(--accent-hover)] transition-colors"
          >
            Sprobuj ponownie
          </button>
          <a
            href="/"
            className="rounded-md px-4 py-2 text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] transition-colors"
          >
            Przejdz do dashboardu
          </a>
        </div>
      </div>
    </div>
  );
}
