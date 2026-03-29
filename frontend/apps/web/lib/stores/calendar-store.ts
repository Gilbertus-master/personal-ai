import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface CalendarStore {
  weekOffset: number;
  eventsDays: number;
  activeTab: 'week' | 'prep' | 'minutes' | 'analytics';
  selectedEventId: string | null;
  analyticsDays: number;
  autoRefresh: boolean;
  refreshInterval: number;

  setWeekOffset: (offset: number) => void;
  nextWeek: () => void;
  prevWeek: () => void;
  setActiveTab: (tab: CalendarStore['activeTab']) => void;
  setSelectedEventId: (id: string | null) => void;
  setAnalyticsDays: (days: number) => void;
  toggleAutoRefresh: () => void;
}

export const useCalendarStore = create<CalendarStore>()(
  persist(
    (set) => ({
      weekOffset: 0,
      eventsDays: 7,
      activeTab: 'week',
      selectedEventId: null,
      analyticsDays: 30,
      autoRefresh: true,
      refreshInterval: 300_000,

      setWeekOffset: (offset) => set({ weekOffset: offset }),
      nextWeek: () => set((s) => ({ weekOffset: s.weekOffset + 1 })),
      prevWeek: () => set((s) => ({ weekOffset: s.weekOffset - 1 })),
      setActiveTab: (tab) => set({ activeTab: tab }),
      setSelectedEventId: (id) => set({ selectedEventId: id }),
      setAnalyticsDays: (days) => set({ analyticsDays: days }),
      toggleAutoRefresh: () => set((s) => ({ autoRefresh: !s.autoRefresh })),
    }),
    { name: 'gilbertus-calendar' },
  ),
);
