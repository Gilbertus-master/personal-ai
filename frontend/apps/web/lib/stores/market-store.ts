import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface MarketStore {
  // State
  insightTypeFilter: string | null;
  minRelevance: number;
  insightLimit: number;
  alertsShowAcknowledged: boolean;
  signalDays: number;
  signalTypeFilter: string | null;
  activeTab: 'dashboard' | 'alerts' | 'sources' | 'competitors';
  sourcesExpanded: boolean;
  refreshInterval: number;

  // Actions
  setInsightTypeFilter: (filter: string | null) => void;
  setMinRelevance: (value: number) => void;
  setInsightLimit: (value: number) => void;
  setAlertsShowAcknowledged: (value: boolean) => void;
  setSignalDays: (value: number) => void;
  setSignalTypeFilter: (filter: string | null) => void;
  setActiveTab: (tab: 'dashboard' | 'alerts' | 'sources' | 'competitors') => void;
  setSourcesExpanded: (value: boolean) => void;
  toggleSourcesExpanded: () => void;
  setRefreshInterval: (ms: number) => void;
}

export const useMarketStore = create<MarketStore>()(
  persist(
    (set) => ({
      insightTypeFilter: null,
      minRelevance: 0,
      insightLimit: 20,
      alertsShowAcknowledged: false,
      signalDays: 30,
      signalTypeFilter: null,
      activeTab: 'dashboard',
      sourcesExpanded: true,
      refreshInterval: 0,

      setInsightTypeFilter: (filter) => set({ insightTypeFilter: filter }),
      setMinRelevance: (value) => set({ minRelevance: value }),
      setInsightLimit: (value) => set({ insightLimit: value }),
      setAlertsShowAcknowledged: (value) => set({ alertsShowAcknowledged: value }),
      setSignalDays: (value) => set({ signalDays: value }),
      setSignalTypeFilter: (filter) => set({ signalTypeFilter: filter }),
      setActiveTab: (tab) => set({ activeTab: tab }),
      setSourcesExpanded: (value) => set({ sourcesExpanded: value }),
      toggleSourcesExpanded: () => set((s) => ({ sourcesExpanded: !s.sourcesExpanded })),
      setRefreshInterval: (ms) => set({ refreshInterval: ms }),
    }),
    { name: 'gilbertus-market' },
  ),
);
