import { create } from 'zustand';
import { persist } from 'zustand/middleware';

type FinanceTab = 'overview' | 'costs' | 'goals';

interface FinanceStore {
  selectedCompany: string | null;
  goalsAreaFilter: string | null;
  goalsStatusFilter: string | null;
  activeTab: FinanceTab;
  expandedCompanies: string[];
  refreshInterval: number;

  setSelectedCompany: (company: string | null) => void;
  setGoalsAreaFilter: (area: string | null) => void;
  setGoalsStatusFilter: (status: string | null) => void;
  setActiveTab: (tab: FinanceTab) => void;
  toggleCompanyExpanded: (company: string) => void;
  setRefreshInterval: (interval: number) => void;
}

export const useFinanceStore = create<FinanceStore>()(
  persist(
    (set) => ({
      selectedCompany: null,
      goalsAreaFilter: null,
      goalsStatusFilter: null,
      activeTab: 'overview',
      expandedCompanies: [],
      refreshInterval: 0,

      setSelectedCompany: (company) => set({ selectedCompany: company }),
      setGoalsAreaFilter: (area) => set({ goalsAreaFilter: area }),
      setGoalsStatusFilter: (status) => set({ goalsStatusFilter: status }),
      setActiveTab: (tab) => set({ activeTab: tab }),
      toggleCompanyExpanded: (company) =>
        set((s) => ({
          expandedCompanies: s.expandedCompanies.includes(company)
            ? s.expandedCompanies.filter((c) => c !== company)
            : [...s.expandedCompanies, company],
        })),
      setRefreshInterval: (interval) => set({ refreshInterval: interval }),
    }),
    { name: 'gilbertus-finance' },
  ),
);
