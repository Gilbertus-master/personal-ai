import { create } from 'zustand';
import { persist } from 'zustand/middleware';

type SortField = 'name' | 'last_contact' | 'status';
type ProfileTab = 'timeline' | 'loops' | 'sentiment' | 'delegation' | 'roles';

interface PeopleStore {
  searchQuery: string;
  filterType: string | null;
  filterStatus: string | null;
  sortBy: SortField;
  sortOrder: 'asc' | 'desc';
  activeTab: ProfileTab;

  setSearchQuery: (q: string) => void;
  setFilterType: (type: string | null) => void;
  setFilterStatus: (status: string | null) => void;
  setSortBy: (sort: SortField) => void;
  toggleSortOrder: () => void;
  setActiveTab: (tab: ProfileTab) => void;
  resetFilters: () => void;
}

export const usePeopleStore = create<PeopleStore>()(
  persist(
    (set) => ({
      searchQuery: '',
      filterType: null,
      filterStatus: null,
      sortBy: 'name',
      sortOrder: 'asc',
      activeTab: 'timeline',

      setSearchQuery: (q) => set({ searchQuery: q }),
      setFilterType: (type) => set({ filterType: type }),
      setFilterStatus: (status) => set({ filterStatus: status }),
      setSortBy: (sort) => set({ sortBy: sort }),
      toggleSortOrder: () => set((s) => ({ sortOrder: s.sortOrder === 'asc' ? 'desc' : 'asc' })),
      setActiveTab: (tab) => set({ activeTab: tab }),
      resetFilters: () => set({ searchQuery: '', filterType: null, filterStatus: null }),
    }),
    { name: 'gilbertus-people' },
  ),
);
