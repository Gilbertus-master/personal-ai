'use client';

import { ErrorFallback } from '@gilbertus/ui';

export default function ModuleError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return <ErrorFallback error={error} resetErrorBoundary={reset} moduleName="Rynek" />;
}
