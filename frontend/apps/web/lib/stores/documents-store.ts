import { create } from 'zustand';
import { persist } from 'zustand/middleware';

type DocumentTab = 'search' | 'browse' | 'ingestion';

interface DocumentsStore {
  searchQuery: string;
  sourceTypeFilter: string[];
  dateFrom: string | null;
  dateTo: string | null;
  classificationFilter: string | null;
  browseSourceType: string | null;
  activeTab: DocumentTab;
  selectedDocumentId: number | null;

  setSearchQuery: (q: string) => void;
  setSourceTypeFilter: (types: string[]) => void;
  setDateRange: (from: string | null, to: string | null) => void;
  setActiveTab: (tab: DocumentTab) => void;
  setSelectedDocumentId: (id: number | null) => void;
  setBrowseSourceType: (type: string | null) => void;
  setClassificationFilter: (classification: string | null) => void;
  clearFilters: () => void;
}

export const useDocumentsStore = create<DocumentsStore>()(
  persist(
    (set) => ({
      searchQuery: '',
      sourceTypeFilter: [],
      dateFrom: null,
      dateTo: null,
      classificationFilter: null,
      browseSourceType: null,
      activeTab: 'search',
      selectedDocumentId: null,

      setSearchQuery: (q) => set({ searchQuery: q }),
      setSourceTypeFilter: (types) => set({ sourceTypeFilter: types }),
      setDateRange: (from, to) => set({ dateFrom: from, dateTo: to }),
      setActiveTab: (tab) => set({ activeTab: tab }),
      setSelectedDocumentId: (id) => set({ selectedDocumentId: id }),
      setBrowseSourceType: (type) => set({ browseSourceType: type }),
      setClassificationFilter: (classification) => set({ classificationFilter: classification }),
      clearFilters: () =>
        set({
          searchQuery: '',
          sourceTypeFilter: [],
          dateFrom: null,
          dateTo: null,
          classificationFilter: null,
          browseSourceType: null,
          selectedDocumentId: null,
        }),
    }),
    { name: 'gilbertus-documents' },
  ),
);
