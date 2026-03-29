'use client';

import { useEffect, useState } from 'react';
import { WifiOff } from 'lucide-react';

export function OfflineBanner() {
  const [isOffline, setIsOffline] = useState(false);

  useEffect(() => {
    const goOffline = () => setIsOffline(true);
    const goOnline = () => setIsOffline(false);

    setIsOffline(!navigator.onLine);

    window.addEventListener('offline', goOffline);
    window.addEventListener('online', goOnline);
    return () => {
      window.removeEventListener('offline', goOffline);
      window.removeEventListener('online', goOnline);
    };
  }, []);

  if (!isOffline) return null;

  return (
    <div className="animate-slide-down flex items-center justify-center gap-2 bg-[var(--warning)] px-4 py-1.5 text-sm font-medium text-black">
      <WifiOff className="h-4 w-4" />
      <span>Jestes offline. Dane moga byc nieaktualne.</span>
    </div>
  );
}
