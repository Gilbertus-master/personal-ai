'use client';

import { useEffect } from 'react';
import { ErrorFallback } from '@gilbertus/ui';

export default function ModuleError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    const API = process.env.NEXT_PUBLIC_GILBERTUS_API_URL || 'http://127.0.0.1:8000';
    fetch(`${API}/errors/report`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: 'sebastian',
        error_type: 'render',
        error_message: error.message?.slice(0, 500),
        error_stack: error.stack?.slice(0, 500),
        route: typeof window !== 'undefined' ? window.location.pathname : undefined,
        browser: typeof navigator !== 'undefined' ? navigator.userAgent.slice(0, 100) : undefined,
      }),
    }).catch(() => {});
  }, [error]);

  return <ErrorFallback error={error} resetErrorBoundary={reset} moduleName="Aplikacja" />;
}
