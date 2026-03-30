'use client';

import { useState } from 'react';
import { SessionProvider } from 'next-auth/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { DesktopProvider } from '@/lib/providers/desktop-provider';
import { SetupWizard } from '@/components/setup-wizard';

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60_000,
          },
        },
      }),
  );

  return (
    <SessionProvider>
      <QueryClientProvider client={queryClient}>
        <DesktopProvider>
          <SetupWizard />
          {children}
        </DesktopProvider>
      </QueryClientProvider>
    </SessionProvider>
  );
}
