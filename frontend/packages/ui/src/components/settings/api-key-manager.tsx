'use client';

import { useState } from 'react';
import { ClipboardCopy, RefreshCw, Key, Check } from 'lucide-react';
import { cn } from '../../lib/utils';

interface ApiKeyInfo {
  id: number;
  name: string;
  role: string;
  user_email: string;
  is_active: boolean;
  created_at: string;
  last_used_at: string | null;
  key?: string;
}

interface ApiKeyManagerProps {
  keys: ApiKeyInfo[];
  isLoading: boolean;
  onRotate: () => void;
  isRotating: boolean;
}

function maskKey(key: string | undefined, name: string): string {
  if (!key) return `${name.slice(0, 10)}...`;
  if (key.length <= 14) return key;
  return `${key.slice(0, 10)}...${key.slice(-4)}`;
}

export function ApiKeyManager({
  keys,
  isLoading,
  onRotate,
  isRotating,
}: ApiKeyManagerProps) {
  const [confirmRotate, setConfirmRotate] = useState(false);
  const [copiedId, setCopiedId] = useState<number | null>(null);

  const handleCopy = async (key: ApiKeyInfo) => {
    const text = key.key ?? key.name;
    await navigator.clipboard.writeText(text);
    setCopiedId(key.id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleRotateClick = () => {
    if (!confirmRotate) {
      setConfirmRotate(true);
      return;
    }
    onRotate();
    setConfirmRotate(false);
  };

  return (
    <div className="rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Key className="h-4 w-4 text-[var(--text-secondary)]" />
          <h4 className="text-sm font-medium text-[var(--text)]">Klucze API</h4>
        </div>

        {keys.length > 0 && (
          <div className="flex items-center gap-2">
            {confirmRotate && (
              <span className="text-xs text-[var(--warning)]">
                Rotacja klucza unieważni stary. Kontynuować?
              </span>
            )}
            <button
              type="button"
              onClick={handleRotateClick}
              disabled={isRotating}
              className={cn(
                'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                confirmRotate
                  ? 'bg-[var(--warning)] text-white'
                  : 'bg-[var(--surface-hover)] text-[var(--text-secondary)] hover:text-[var(--text)]',
                isRotating && 'opacity-50 cursor-not-allowed',
              )}
            >
              <RefreshCw className={cn('h-3.5 w-3.5', isRotating && 'animate-spin')} />
              {confirmRotate ? 'Potwierdź' : 'Rotuj klucz'}
            </button>
            {confirmRotate && (
              <button
                type="button"
                onClick={() => setConfirmRotate(false)}
                className="rounded-md px-2 py-1.5 text-xs text-[var(--text-secondary)] hover:text-[var(--text)] transition-colors"
              >
                Anuluj
              </button>
            )}
          </div>
        )}
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[1, 2].map((i) => (
            <div
              key={i}
              className="h-14 rounded-md bg-[var(--surface-hover)] animate-pulse"
            />
          ))}
        </div>
      ) : keys.length === 0 ? (
        <p className="text-sm text-[var(--text-secondary)] py-4 text-center">
          Brak kluczy API
        </p>
      ) : (
        <div className="space-y-2">
          {keys.map((k) => (
            <div
              key={k.id}
              className="flex items-center justify-between rounded-md border border-[var(--border)] bg-[var(--bg)] px-4 py-3"
            >
              <div className="flex flex-col gap-0.5 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-[var(--text)] truncate">
                    {k.name}
                  </span>
                  <span className="rounded-full bg-[var(--accent)]/15 px-2 py-0.5 text-xs text-[var(--accent)]">
                    {k.role}
                  </span>
                </div>
                <div className="flex items-center gap-3 text-xs text-[var(--text-secondary)]">
                  <code className="font-mono">{maskKey(k.key, k.name)}</code>
                  <span>Utworzony: {new Date(k.created_at).toLocaleDateString('pl-PL')}</span>
                  {k.last_used_at && (
                    <span>
                      Ostatnio: {new Date(k.last_used_at).toLocaleDateString('pl-PL')}
                    </span>
                  )}
                </div>
              </div>
              <button
                type="button"
                onClick={() => handleCopy(k)}
                className="shrink-0 ml-3 rounded-md p-2 text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text)] transition-colors"
                title="Kopiuj klucz"
              >
                {copiedId === k.id ? (
                  <Check className="h-4 w-4 text-[var(--success)]" />
                ) : (
                  <ClipboardCopy className="h-4 w-4" />
                )}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
