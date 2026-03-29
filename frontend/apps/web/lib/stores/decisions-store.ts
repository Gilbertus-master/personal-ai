import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface DecisionsStore {
  areaFilter: string | null;
  searchQuery: string;
  listLimit: number;
  activeTab: 'journal' | 'patterns' | 'intelligence';
  expandedDecisionId: number | null;
  intelligenceMonths: number;

  setAreaFilter: (area: string | null) => void;
  setSearchQuery: (query: string) => void;
  setListLimit: (limit: number) => void;
  setActiveTab: (tab: 'journal' | 'patterns' | 'intelligence') => void;
  setExpandedDecisionId: (id: number | null) => void;
  setIntelligenceMonths: (months: number) => void;
}

export const useDecisionsStore = create<DecisionsStore>()(
  persist(
    (set) => ({
      areaFilter: null,
      searchQuery: '',
      listLimit: 50,
      activeTab: 'journal',
      expandedDecisionId: null,
      intelligenceMonths: 6,

      setAreaFilter: (area) => set({ areaFilter: area }),
      setSearchQuery: (query) => set({ searchQuery: query }),
      setListLimit: (limit) => set({ listLimit: limit }),
      setActiveTab: (tab) => set({ activeTab: tab }),
      setExpandedDecisionId: (id) => set({ expandedDecisionId: id }),
      setIntelligenceMonths: (months) => set({ intelligenceMonths: months }),
    }),
    { name: 'gilbertus-decisions' },
  ),
);
