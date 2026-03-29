import { create } from 'zustand';
import { persist } from 'zustand/middleware';

type MatterDetailTab = 'overview' | 'analysis' | 'action_plan' | 'communication' | 'report';
type RiskActiveTab = 'register' | 'heatmap';
type ReportActiveTab = 'daily' | 'weekly' | 'area';
type AreaDetailTab =
  | 'overview'
  | 'obligations'
  | 'matters'
  | 'documents'
  | 'deadlines'
  | 'trainings'
  | 'risks'
  | 'raci';

interface ComplianceStore {
  // Matters filters
  matterStatus: string | null;
  matterArea: string | null;
  matterPriority: string | null;
  matterDetailTab: MatterDetailTab;

  // Obligations filters
  obligationArea: string | null;
  obligationStatus: string | null;
  showOverdueOnly: boolean;

  // Deadlines
  daysAhead: number;
  deadlineArea: string | null;

  // Documents filters
  docArea: string | null;
  docType: string | null;
  docStatus: string | null;
  showStaleOnly: boolean;

  // Trainings filters
  trainingArea: string | null;
  trainingStatus: string | null;

  // Risks
  riskArea: string | null;
  riskStatus: string | null;
  riskActiveTab: RiskActiveTab;

  // RACI
  raciArea: string | null;

  // Reports
  reportActiveTab: ReportActiveTab;
  reportAreaCode: string | null;

  // Area detail
  areaDetailTab: AreaDetailTab;

  // Setters
  setMatterStatus: (v: string | null) => void;
  setMatterArea: (v: string | null) => void;
  setMatterPriority: (v: string | null) => void;
  setMatterDetailTab: (v: MatterDetailTab) => void;

  setObligationArea: (v: string | null) => void;
  setObligationStatus: (v: string | null) => void;
  setShowOverdueOnly: (v: boolean) => void;

  setDaysAhead: (v: number) => void;
  setDeadlineArea: (v: string | null) => void;

  setDocArea: (v: string | null) => void;
  setDocType: (v: string | null) => void;
  setDocStatus: (v: string | null) => void;
  setShowStaleOnly: (v: boolean) => void;

  setTrainingArea: (v: string | null) => void;
  setTrainingStatus: (v: string | null) => void;

  setRiskArea: (v: string | null) => void;
  setRiskStatus: (v: string | null) => void;
  setRiskActiveTab: (v: RiskActiveTab) => void;

  setRaciArea: (v: string | null) => void;

  setReportActiveTab: (v: ReportActiveTab) => void;
  setReportAreaCode: (v: string | null) => void;

  setAreaDetailTab: (v: AreaDetailTab) => void;

  resetAllFilters: () => void;
}

const initialState = {
  matterStatus: null,
  matterArea: null,
  matterPriority: null,
  matterDetailTab: 'overview' as MatterDetailTab,

  obligationArea: null,
  obligationStatus: null,
  showOverdueOnly: false,

  daysAhead: 30,
  deadlineArea: null,

  docArea: null,
  docType: null,
  docStatus: null,
  showStaleOnly: false,

  trainingArea: null,
  trainingStatus: null,

  riskArea: null,
  riskStatus: null,
  riskActiveTab: 'register' as RiskActiveTab,

  raciArea: null,

  reportActiveTab: 'daily' as ReportActiveTab,
  reportAreaCode: null,

  areaDetailTab: 'overview' as AreaDetailTab,
};

export const useComplianceStore = create<ComplianceStore>()(
  persist(
    (set) => ({
      ...initialState,

      setMatterStatus: (v) => set({ matterStatus: v }),
      setMatterArea: (v) => set({ matterArea: v }),
      setMatterPriority: (v) => set({ matterPriority: v }),
      setMatterDetailTab: (v) => set({ matterDetailTab: v }),

      setObligationArea: (v) => set({ obligationArea: v }),
      setObligationStatus: (v) => set({ obligationStatus: v }),
      setShowOverdueOnly: (v) => set({ showOverdueOnly: v }),

      setDaysAhead: (v) => set({ daysAhead: v }),
      setDeadlineArea: (v) => set({ deadlineArea: v }),

      setDocArea: (v) => set({ docArea: v }),
      setDocType: (v) => set({ docType: v }),
      setDocStatus: (v) => set({ docStatus: v }),
      setShowStaleOnly: (v) => set({ showStaleOnly: v }),

      setTrainingArea: (v) => set({ trainingArea: v }),
      setTrainingStatus: (v) => set({ trainingStatus: v }),

      setRiskArea: (v) => set({ riskArea: v }),
      setRiskStatus: (v) => set({ riskStatus: v }),
      setRiskActiveTab: (v) => set({ riskActiveTab: v }),

      setRaciArea: (v) => set({ raciArea: v }),

      setReportActiveTab: (v) => set({ reportActiveTab: v }),
      setReportAreaCode: (v) => set({ reportAreaCode: v }),

      setAreaDetailTab: (v) => set({ areaDetailTab: v }),

      resetAllFilters: () => set(initialState),
    }),
    { name: 'gilbertus-compliance' },
  ),
);
