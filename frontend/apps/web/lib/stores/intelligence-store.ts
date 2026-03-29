import { create } from 'zustand';
import { persist } from 'zustand/middleware';

type IntelTab = 'opportunities' | 'inefficiencies' | 'correlations' | 'scenarios' | 'predictions';
type CorrelationType = 'temporal' | 'person' | 'anomaly' | 'report';

interface IntelligenceStore {
  activeTab: IntelTab;
  opportunityStatus: string | null;
  correlationType: CorrelationType;
  correlationParams: Record<string, string>;
  scenarioStatus: string | null;

  setActiveTab: (tab: IntelTab) => void;
  setOpportunityStatus: (status: string | null) => void;
  setCorrelationType: (type: CorrelationType) => void;
  setCorrelationParam: (key: string, value: string) => void;
  resetCorrelationParams: () => void;
  setScenarioStatus: (status: string | null) => void;
}

export const useIntelligenceStore = create<IntelligenceStore>()(
  persist(
    (set) => ({
      activeTab: 'opportunities',
      opportunityStatus: null,
      correlationType: 'temporal',
      correlationParams: {},
      scenarioStatus: null,

      setActiveTab: (tab) => set({ activeTab: tab }),
      setOpportunityStatus: (status) => set({ opportunityStatus: status }),
      setCorrelationType: (type) => set({ correlationType: type, correlationParams: {} }),
      setCorrelationParam: (key, value) =>
        set((s) => ({ correlationParams: { ...s.correlationParams, [key]: value } })),
      resetCorrelationParams: () => set({ correlationParams: {} }),
      setScenarioStatus: (status) => set({ scenarioStatus: status }),
    }),
    { name: 'gilbertus-intelligence' },
  ),
);
