import { create } from 'zustand';
import { persist } from 'zustand/middleware';

type SettingsTab = 'profile' | 'preferences' | 'api-keys';

interface SettingsStore {
  activeTab: SettingsTab;
  language: 'pl' | 'en';
  notifications: {
    email_alerts: boolean;
    whatsapp_alerts: boolean;
    daily_brief: boolean;
  };

  setActiveTab: (tab: SettingsTab) => void;
  setLanguage: (lang: 'pl' | 'en') => void;
  setNotifications: (prefs: Partial<SettingsStore['notifications']>) => void;
}

export const useSettingsStore = create<SettingsStore>()(
  persist(
    (set) => ({
      activeTab: 'profile',
      language: 'pl',
      notifications: { email_alerts: true, whatsapp_alerts: true, daily_brief: true },

      setActiveTab: (tab) => set({ activeTab: tab }),
      setLanguage: (lang) => set({ language: lang }),
      setNotifications: (prefs) =>
        set((s) => ({ notifications: { ...s.notifications, ...prefs } })),
    }),
    { name: 'gilbertus-settings' },
  ),
);
