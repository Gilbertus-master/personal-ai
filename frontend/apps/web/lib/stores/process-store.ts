import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface ProcessStore {
  processTypeFilter: string | null;
  appStatusFilter: string | null;
  techStatusFilter: string | null;
  techTypeFilter: string | null;
  activeSection: 'overview' | 'apps' | 'flows' | 'tech' | 'workforce';
  appViewMode: 'inventory' | 'ranking' | 'costs';
  selectedEmployee: string | null;
  refreshInterval: number;

  setProcessTypeFilter: (filter: string | null) => void;
  setAppStatusFilter: (filter: string | null) => void;
  setTechStatusFilter: (filter: string | null) => void;
  setTechTypeFilter: (filter: string | null) => void;
  setActiveSection: (section: ProcessStore['activeSection']) => void;
  setAppViewMode: (mode: ProcessStore['appViewMode']) => void;
  setSelectedEmployee: (slug: string | null) => void;
  setRefreshInterval: (ms: number) => void;
}

export const useProcessStore = create<ProcessStore>()(
  persist(
    (set) => ({
      processTypeFilter: null,
      appStatusFilter: null,
      techStatusFilter: null,
      techTypeFilter: null,
      activeSection: 'overview',
      appViewMode: 'inventory',
      selectedEmployee: null,
      refreshInterval: 0,

      setProcessTypeFilter: (filter) => set({ processTypeFilter: filter }),
      setAppStatusFilter: (filter) => set({ appStatusFilter: filter }),
      setTechStatusFilter: (filter) => set({ techStatusFilter: filter }),
      setTechTypeFilter: (filter) => set({ techTypeFilter: filter }),
      setActiveSection: (section) => set({ activeSection: section }),
      setAppViewMode: (mode) => set({ appViewMode: mode }),
      setSelectedEmployee: (slug) => set({ selectedEmployee: slug }),
      setRefreshInterval: (ms) => set({ refreshInterval: ms }),
    }),
    { name: 'gilbertus-process' },
  ),
);
