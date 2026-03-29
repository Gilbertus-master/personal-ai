import { create } from 'zustand';
import { persist } from 'zustand/middleware';

type SyncStatus = 'idle' | 'syncing' | 'error';

interface OfflineStore {
  isOnline: boolean;
  lastOnlineAt: string | null;
  queuedMessageCount: number;
  syncStatus: SyncStatus;
  setOnline: (v: boolean) => void;
  incrementQueue: () => void;
  decrementQueue: () => void;
  setSyncStatus: (s: SyncStatus) => void;
}

export const useOfflineStore = create<OfflineStore>()(
  persist(
    (set) => ({
      isOnline: true,
      lastOnlineAt: null,
      queuedMessageCount: 0,
      syncStatus: 'idle' as SyncStatus,
      setOnline: (v) =>
        set({
          isOnline: v,
          ...(v ? { lastOnlineAt: new Date().toISOString() } : {}),
        }),
      incrementQueue: () =>
        set((s) => ({ queuedMessageCount: s.queuedMessageCount + 1 })),
      decrementQueue: () =>
        set((s) => ({
          queuedMessageCount: Math.max(0, s.queuedMessageCount - 1),
        })),
      setSyncStatus: (s) => set({ syncStatus: s }),
    }),
    { name: 'gilbertus-offline' },
  ),
);
