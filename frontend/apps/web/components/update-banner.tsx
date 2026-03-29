'use client';

import { useState } from 'react';
import { useAutoUpdate } from '@/lib/hooks/use-auto-update';

export default function UpdateBanner() {
  const { available, version, notes, install, dismiss } = useAutoUpdate();
  const [hidden, setHidden] = useState(false);

  if (!available || hidden) return null;

  const truncatedNotes = notes && notes.length > 100 ? notes.slice(0, 100) + '...' : notes;

  return (
    <div
      className="sticky top-0 z-50 flex items-center justify-between bg-blue-600 px-4 py-2 text-white"
    >
      <div className="flex items-center gap-3">
        <span className="font-medium">Dostępna aktualizacja v{version}</span>
        {truncatedNotes && (
          <span className="hidden text-sm text-blue-100 sm:inline">{truncatedNotes}</span>
        )}
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={() => void install()}
          className="rounded bg-white px-3 py-1 text-sm font-medium text-blue-600 hover:bg-blue-50"
        >
          Zainstaluj teraz
        </button>
        <button
          onClick={dismiss}
          className="rounded px-2 py-1 text-sm text-blue-100 hover:text-white"
        >
          Później
        </button>
        <button
          onClick={() => setHidden(true)}
          className="ml-1 text-blue-200 hover:text-white"
          aria-label="Zamknij"
        >
          ×
        </button>
      </div>
    </div>
  );
}
