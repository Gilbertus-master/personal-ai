import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface PluginDevStore {
  selectedTenant: string | null;
  statusFilter: string | null;
  expandedProposalId: number | null;

  setTenant: (tenant: string | null) => void;
  setStatusFilter: (status: string | null) => void;
  toggleExpanded: (id: number) => void;
}

export const usePluginDevStore = create<PluginDevStore>()(
  persist(
    (set, get) => ({
      selectedTenant: null,
      statusFilter: null,
      expandedProposalId: null,

      setTenant: (tenant) => set({ selectedTenant: tenant }),
      setStatusFilter: (status) => set({ statusFilter: status }),
      toggleExpanded: (id) =>
        set({ expandedProposalId: get().expandedProposalId === id ? null : id }),
    }),
    { name: 'gilbertus-plugin-dev' },
  ),
);
