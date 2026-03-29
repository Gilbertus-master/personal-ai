'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react';
import { useRouter } from 'next/navigation';
import { useTauri } from '@/lib/hooks/use-tauri';

interface DeepLink {
  action: string;
  params: Record<string, string>;
}

interface DesktopContextValue {
  isTauri: boolean;
  platform: string | null;
  trayAlertCount: number;
  deepLinkPending: DeepLink | null;
  clearDeepLink: () => void;
}

const DesktopContext = createContext<DesktopContextValue>({
  isTauri: false,
  platform: null,
  trayAlertCount: 0,
  deepLinkPending: null,
  clearDeepLink: () => {},
});

function parseDeepLink(url: string): DeepLink | null {
  try {
    // gilbertus://action/param?query=value
    const parsed = new URL(url);
    if (parsed.protocol !== 'gilbertus:') return null;

    // hostname is the action, pathname has additional segments
    const action = parsed.hostname;
    const pathSegments = parsed.pathname.replace(/^\//, '').split('/').filter(Boolean);
    const params: Record<string, string> = {};

    // Copy search params
    parsed.searchParams.forEach((value, key) => {
      params[key] = value;
    });

    // Add path segments as positional params
    if (pathSegments.length > 0) {
      params.slug = pathSegments.join('/');
    }

    return { action, params };
  } catch {
    return null;
  }
}

function deepLinkToRoute(link: DeepLink): string | null {
  switch (link.action) {
    case 'ask':
      return link.params.q ? `/chat?q=${encodeURIComponent(link.params.q)}` : '/chat';
    case 'brief':
      return '/dashboard';
    case 'person':
      return link.params.slug ? `/people/${link.params.slug}` : '/people';
    case 'chat':
      return link.params.slug ? `/chat/${link.params.slug}` : '/chat';
    default:
      return null;
  }
}

export function DesktopProvider({ children }: { children: ReactNode }) {
  const { isTauri, invoke, listen } = useTauri();
  const router = useRouter();
  const [platform, setPlatform] = useState<string | null>(null);
  const [trayAlertCount, setTrayAlertCount] = useState(0);
  const [deepLinkPending, setDeepLinkPending] = useState<DeepLink | null>(null);

  const clearDeepLink = useCallback(() => {
    setDeepLinkPending(null);
  }, []);

  // Get platform info
  useEffect(() => {
    if (!isTauri || !invoke) return;

    invoke('get_platform')
      .then((p) => setPlatform(p as string))
      .catch(() => {
        // Command may not be registered yet
      });
  }, [isTauri, invoke]);

  // Listen for tray actions
  useEffect(() => {
    if (!isTauri || !listen) return;

    let unlisten: (() => void) | null = null;

    listen('tray-action', (event) => {
      const payload = event.payload as { action?: string; route?: string };
      if (payload.route) {
        router.push(payload.route);
      }
    }).then((fn) => {
      unlisten = fn;
    });

    return () => {
      unlisten?.();
    };
  }, [isTauri, listen, router]);

  // Listen for deep links
  useEffect(() => {
    if (!isTauri || !listen) return;

    let unlisten: (() => void) | null = null;

    listen('deep-link', (event) => {
      const url = event.payload as string;
      const parsed = parseDeepLink(url);
      if (!parsed) return;

      setDeepLinkPending(parsed);

      const route = deepLinkToRoute(parsed);
      if (route) {
        router.push(route);
      }
    }).then((fn) => {
      unlisten = fn;
    });

    return () => {
      unlisten?.();
    };
  }, [isTauri, listen, router]);

  // Listen for tray alert count updates
  useEffect(() => {
    if (!isTauri || !listen) return;

    let unlisten: (() => void) | null = null;

    listen('tray-alert-count', (event) => {
      setTrayAlertCount(event.payload as number);
    }).then((fn) => {
      unlisten = fn;
    });

    return () => {
      unlisten?.();
    };
  }, [isTauri, listen]);

  return (
    <DesktopContext.Provider
      value={{ isTauri, platform, trayAlertCount, deepLinkPending, clearDeepLink }}
    >
      {children}
    </DesktopContext.Provider>
  );
}

export function useDesktop(): DesktopContextValue {
  return useContext(DesktopContext);
}
