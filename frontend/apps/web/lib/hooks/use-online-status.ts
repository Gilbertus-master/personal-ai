'use client';

import { useEffect, useRef, useState } from 'react';
import { customFetch } from '@gilbertus/api-client';

interface OnlineStatus {
  isOnline: boolean;
  lastOnlineAt: string | null;
}

const HEALTH_POLL_INTERVAL = 30_000;

export function useOnlineStatus(): OnlineStatus {
  const [isOnline, setIsOnline] = useState<boolean>(
    typeof navigator !== 'undefined' ? navigator.onLine : true,
  );
  const [lastOnlineAt, setLastOnlineAt] = useState<string | null>(
    typeof navigator !== 'undefined' && navigator.onLine
      ? new Date().toISOString()
      : null,
  );
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const markOnline = () => {
      setIsOnline(true);
      setLastOnlineAt(new Date().toISOString());
    };

    const markOffline = () => {
      setIsOnline(false);
    };

    const checkHealth = async () => {
      if (!navigator.onLine) {
        markOffline();
        return;
      }

      try {
        await customFetch<unknown>({ url: '/health', method: 'GET' });
        markOnline();
      } catch {
        markOffline();
      }
    };

    const handleOnline = () => {
      // Browser says we're online — verify with health check
      void checkHealth();
    };

    const handleOffline = () => {
      markOffline();
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    // Initial health check
    void checkHealth();

    // Poll health endpoint
    intervalRef.current = setInterval(() => {
      void checkHealth();
    }, HEALTH_POLL_INTERVAL);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, []);

  return { isOnline, lastOnlineAt };
}
