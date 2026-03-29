import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface DashboardStore {
  // Preferences
  collapsedSections: string[];
  dismissedAlertIds: number[];
  autoRefresh: boolean;
  refreshInterval: number;
  timelineFilter: string | null;

  // Actions
  toggleSection: (section: string) => void;
  dismissAlert: (alertId: number) => void;
  undismissAlert: (alertId: number) => void;
  clearDismissedAlerts: () => void;
  setAutoRefresh: (enabled: boolean) => void;
  setRefreshInterval: (ms: number) => void;
  setTimelineFilter: (filter: string | null) => void;
}

export const useDashboardStore = create<DashboardStore>()(
  persist(
    (set) => ({
      collapsedSections: [],
      dismissedAlertIds: [],
      autoRefresh: true,
      refreshInterval: 300_000,
      timelineFilter: null,

      toggleSection: (section) =>
        set((s) => ({
          collapsedSections: s.collapsedSections.includes(section)
            ? s.collapsedSections.filter((id) => id !== section)
            : [...s.collapsedSections, section],
        })),

      dismissAlert: (alertId) =>
        set((s) => ({
          dismissedAlertIds: s.dismissedAlertIds.includes(alertId)
            ? s.dismissedAlertIds
            : [...s.dismissedAlertIds, alertId],
        })),

      undismissAlert: (alertId) =>
        set((s) => ({
          dismissedAlertIds: s.dismissedAlertIds.filter((id) => id !== alertId),
        })),

      clearDismissedAlerts: () => set({ dismissedAlertIds: [] }),

      setAutoRefresh: (enabled) => set({ autoRefresh: enabled }),
      setRefreshInterval: (ms) => set({ refreshInterval: ms }),
      setTimelineFilter: (filter) => set({ timelineFilter: filter }),
    }),
    { name: 'gilbertus-dashboard' },
  ),
);
