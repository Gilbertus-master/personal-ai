'use client';

import { useState } from 'react';
import { signIn } from 'next-auth/react';
import { useRouter } from 'next/navigation';

// i18n strings — will be replaced with useTranslations('auth') once next-intl provider is wired
const t = {
  loginTitle: 'Gilbertus Albans',
  loginSubtitle: 'Zaloguj się do systemu',
  apiKeyLabel: 'Klucz API',
  apiKeyPlaceholder: 'Wpisz klucz API...',
  login: 'Zaloguj się',
  invalidKey: 'Nieprawidłowy klucz API',
  azureAdButton: 'Zaloguj przez Microsoft',
} as const;

export default function LoginPage() {
  const router = useRouter();
  const [apiKey, setApiKey] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleApiKeySubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const result = await signIn('api-key', {
        apiKey,
        redirect: false,
      });

      if (result?.error) {
        setError(t.invalidKey);
      } else {
        router.push('/dashboard');
      }
    } catch {
      setError(t.invalidKey);
    } finally {
      setLoading(false);
    }
  }

  function handleAzureAdLogin() {
    signIn('microsoft-entra-id');
  }

  return (
    <div className="w-full max-w-md rounded-xl border border-[var(--border)] bg-[var(--surface)] p-8 shadow-2xl">
      <div className="mb-8 text-center">
        <h1 className="text-2xl font-bold text-[var(--text)]">
          {t.loginTitle}
        </h1>
        <p className="mt-2 text-sm text-[var(--text-secondary)]">
          {t.loginSubtitle}
        </p>
      </div>

      <form onSubmit={handleApiKeySubmit} className="space-y-4">
        <div>
          <label
            htmlFor="apiKey"
            className="mb-1.5 block text-sm font-medium text-[var(--text-secondary)]"
          >
            {t.apiKeyLabel}
          </label>
          <input
            id="apiKey"
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={t.apiKeyPlaceholder}
            className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-4 py-2.5 text-sm text-[var(--text)] placeholder-[var(--text-muted)] outline-none transition-colors focus:border-[var(--accent)] focus:ring-1 focus:ring-[var(--accent)]"
            required
          />
        </div>

        {error && (
          <p className="text-sm text-red-400">{error}</p>
        )}

        <button
          type="submit"
          disabled={loading || !apiKey}
          className="w-full rounded-lg bg-[var(--accent)] px-4 py-2.5 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {loading ? '...' : t.login}
        </button>
      </form>

      <div className="my-6 flex items-center gap-3">
        <div className="h-px flex-1 bg-[var(--border)]" />
        <span className="text-xs text-[var(--text-muted)]">lub</span>
        <div className="h-px flex-1 bg-[var(--border)]" />
      </div>

      <button
        type="button"
        onClick={handleAzureAdLogin}
        className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-4 py-2.5 text-sm font-medium text-[var(--text)] transition-colors hover:bg-[var(--surface-hover)]"
      >
        {t.azureAdButton}
      </button>
    </div>
  );
}
