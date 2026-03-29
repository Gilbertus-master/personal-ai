'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useTauri } from '@/lib/hooks/use-tauri';

interface AutoUpdateState {
  available: boolean;
  version: string | null;
  notes: string | null;
  checking: boolean;
  install: () => void;
  dismiss: () => void;
}

const DISMISS_KEY = 'update-dismissed-until';
const CHECK_INTERVAL_MS = 60 * 60 * 1000; // 1 hour

function isDismissed(): boolean {
  if (typeof window === 'undefined') return false;
  const until = localStorage.getItem(DISMISS_KEY);
  if (!until) return false;
  return Date.now() < Number(until);
}

export function useAutoUpdate(): AutoUpdateState {
  const { isTauri } = useTauri();
  const [available, setAvailable] = useState(false);
  const [version, setVersion] = useState<string | null>(null);
  const [notes, setNotes] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  const updateRef = useRef<any>(null);

  const checkForUpdate = useCallback(async () => {
    if (!isTauri) return;
    if (isDismissed()) return;

    setChecking(true);
    try {
      const { check } = await import('@tauri-apps/plugin-updater');
      const update = await check();
      if (update?.available) {
        updateRef.current = update;
        setAvailable(true);
        setVersion(update.version);
        setNotes(update.body ?? null);
      } else {
        setAvailable(false);
        setVersion(null);
        setNotes(null);
      }
    } catch {
      // Update check failed silently
    } finally {
      setChecking(false);
    }
  }, [isTauri]);

  useEffect(() => {
    if (!isTauri) return;

    void checkForUpdate();

    const interval = setInterval(() => {
      void checkForUpdate();
    }, CHECK_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [isTauri, checkForUpdate]);

  const install = useCallback(async () => {
    const update = updateRef.current;
    if (!update) return;

    try {
      await update.downloadAndInstall();
      const { relaunch } = await import('@tauri-apps/plugin-process');
      await relaunch();
    } catch {
      // Install failed — user can retry
    }
  }, []);

  const dismiss = useCallback(() => {
    const until = Date.now() + 24 * 60 * 60 * 1000; // 24 hours
    localStorage.setItem(DISMISS_KEY, String(until));
    setAvailable(false);
  }, []);

  return { available, version, notes, checking, install, dismiss };
}
