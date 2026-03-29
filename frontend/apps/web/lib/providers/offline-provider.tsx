'use client';

import { createContext, useContext, useEffect, type ReactNode } from 'react';
import { useOnlineStatus } from '@/lib/hooks/use-online-status';
import { useOfflineStore } from '@/lib/stores/offline-store';

interface OfflineContextValue {
  isOnline: boolean;
  lastOnlineAt: string | null;
}

const OfflineContext = createContext<OfflineContextValue>({
  isOnline: true,
  lastOnlineAt: null,
});

export function OfflineProvider({ children }: { children: ReactNode }) {
  const status = useOnlineStatus();
  const setOnline = useOfflineStore((s) => s.setOnline);

  // Sync hook state to Zustand store so non-React consumers can read it
  useEffect(() => {
    setOnline(status.isOnline);
  }, [status.isOnline, setOnline]);

  return (
    <OfflineContext.Provider value={status}>{children}</OfflineContext.Provider>
  );
}

export function useOffline(): OfflineContextValue {
  return useContext(OfflineContext);
}
