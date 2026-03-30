'use client';

import { useState, useCallback } from 'react';

interface AutoUpdateState {
  available: boolean;
  version: string | null;
  notes: string | null;
  checking: boolean;
  install: () => void;
  dismiss: () => void;
}

// Updater disabled for v0.1 — will be re-enabled when update server is live
export function useAutoUpdate(): AutoUpdateState {
  const [available] = useState(false);
  const [version] = useState<string | null>(null);
  const [notes] = useState<string | null>(null);
  const [checking] = useState(false);

  const install = useCallback(() => {}, []);
  const dismiss = useCallback(() => {}, []);

  return { available, version, notes, checking, install, dismiss };
}
