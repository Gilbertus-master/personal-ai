import { create } from 'zustand';
import { persist } from 'zustand/middleware';

type OmniusTab = 'overview' | 'tasks' | 'audit' | 'config' | 'sync';
type OmniusTenant = 'reh' | 'ref';

interface AdminStore {
  // Cron filters
  cronCategoryFilter: string | null;
  cronUserFilter: string | null;
  cronEnabledFilter: boolean | null;

  // Code review filters
  codeReviewSeverityFilter: string | null;
  codeReviewCategoryFilter: string | null;

  // Audit filters
  auditUserFilter: string | null;
  auditActionFilter: string | null;
  auditResultFilter: string | null;

  // Omnius Bridge
  omniusActiveTab: OmniusTab;
  omniusActiveTenant: OmniusTenant;

  // Setters
  setCronCategoryFilter: (v: string | null) => void;
  setCronUserFilter: (v: string | null) => void;
  setCronEnabledFilter: (v: boolean | null) => void;
  setCodeReviewSeverityFilter: (v: string | null) => void;
  setCodeReviewCategoryFilter: (v: string | null) => void;
  setAuditUserFilter: (v: string | null) => void;
  setAuditActionFilter: (v: string | null) => void;
  setAuditResultFilter: (v: string | null) => void;
  setOmniusActiveTab: (tab: OmniusTab) => void;
  setOmniusActiveTenant: (tenant: OmniusTenant) => void;
  resetCronFilters: () => void;
  resetAuditFilters: () => void;
}

export const useAdminStore = create<AdminStore>()(
  persist(
    (set) => ({
      cronCategoryFilter: null,
      cronUserFilter: null,
      cronEnabledFilter: null,
      codeReviewSeverityFilter: null,
      codeReviewCategoryFilter: null,
      auditUserFilter: null,
      auditActionFilter: null,
      auditResultFilter: null,
      omniusActiveTab: 'overview',
      omniusActiveTenant: 'reh',

      setCronCategoryFilter: (v) => set({ cronCategoryFilter: v }),
      setCronUserFilter: (v) => set({ cronUserFilter: v }),
      setCronEnabledFilter: (v) => set({ cronEnabledFilter: v }),
      setCodeReviewSeverityFilter: (v) => set({ codeReviewSeverityFilter: v }),
      setCodeReviewCategoryFilter: (v) => set({ codeReviewCategoryFilter: v }),
      setAuditUserFilter: (v) => set({ auditUserFilter: v }),
      setAuditActionFilter: (v) => set({ auditActionFilter: v }),
      setAuditResultFilter: (v) => set({ auditResultFilter: v }),
      setOmniusActiveTab: (tab) => set({ omniusActiveTab: tab }),
      setOmniusActiveTenant: (tenant) => set({ omniusActiveTenant: tenant }),
      resetCronFilters: () =>
        set({ cronCategoryFilter: null, cronUserFilter: null, cronEnabledFilter: null }),
      resetAuditFilters: () =>
        set({ auditUserFilter: null, auditActionFilter: null, auditResultFilter: null }),
    }),
    { name: 'gilbertus-admin' },
  ),
);
