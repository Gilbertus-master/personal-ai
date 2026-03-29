'use client';

import { useEffect, useState } from 'react';

interface TauriAPI {
  isTauri: boolean;
  platform: string | null;
  invoke: ((cmd: string, args?: Record<string, unknown>) => Promise<unknown>) | null;
  listen: ((event: string, handler: (event: { payload: unknown }) => void) => Promise<() => void>) | null;
}

const DEFAULT_STATE: TauriAPI = {
  isTauri: false,
  platform: null,
  invoke: null,
  listen: null,
};

function isTauriEnv(): boolean {
  return typeof window !== 'undefined' && '__TAURI__' in window;
}

export function useTauri(): TauriAPI {
  const [state, setState] = useState<TauriAPI>(DEFAULT_STATE);

  useEffect(() => {
    if (!isTauriEnv()) return;

    let cancelled = false;

    async function loadTauriAPIs() {
      try {
        const [{ invoke }, { listen }] = await Promise.all([
          import('@tauri-apps/api/core'),
          import('@tauri-apps/api/event'),
        ]);

        if (cancelled) return;

        setState({
          isTauri: true,
          platform: null,
          invoke,
          listen,
        });
      } catch {
        // Tauri APIs not available — stay in web fallback mode
      }
    }

    void loadTauriAPIs();

    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}
