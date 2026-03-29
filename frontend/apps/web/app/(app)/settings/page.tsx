'use client';

import { useRole } from '@gilbertus/rbac';
import { useSettingsStore } from '@/lib/stores/settings-store';

const TABS = [
  { id: 'profile' as const, label: 'Profil' },
  { id: 'preferences' as const, label: 'Preferencje' },
  { id: 'api-keys' as const, label: 'Klucze API' },
];

/* ProfileCard, PreferencesForm, ApiKeyManager will be built in P8T5.
   Inline placeholders for now so the page renders. */

function ProfileCard({ role, roleLevel }: { role: string; roleLevel: number }) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 space-y-3">
      <h2 className="text-lg font-semibold text-[var(--text)]">Profil</h2>
      <p className="text-sm text-[var(--text-secondary)]">
        Rola: <span className="font-medium text-[var(--text)]">{role}</span> (poziom {roleLevel})
      </p>
    </div>
  );
}

function PreferencesForm() {
  const { language, setLanguage, notifications, setNotifications } = useSettingsStore();

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 space-y-4">
      <h2 className="text-lg font-semibold text-[var(--text)]">Preferencje</h2>

      <div className="space-y-3">
        <label className="flex items-center justify-between">
          <span className="text-sm text-[var(--text)]">Język</span>
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value as 'pl' | 'en')}
            className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-1.5 text-sm text-[var(--text)]"
          >
            <option value="pl">Polski</option>
            <option value="en">English</option>
          </select>
        </label>

        {([
          { key: 'email_alerts' as const, label: 'E-mail alerts' },
          { key: 'whatsapp_alerts' as const, label: 'WhatsApp alerts' },
          { key: 'daily_brief' as const, label: 'Daily brief' },
        ]).map(({ key, label }) => (
          <label key={key} className="flex items-center justify-between">
            <span className="text-sm text-[var(--text)]">{label}</span>
            <input
              type="checkbox"
              checked={notifications[key]}
              onChange={(e) => setNotifications({ [key]: e.target.checked })}
              className="h-4 w-4 accent-[var(--accent)]"
            />
          </label>
        ))}
      </div>
    </div>
  );
}

function ApiKeyManager() {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 space-y-3">
      <h2 className="text-lg font-semibold text-[var(--text)]">Klucze API</h2>
      <p className="text-sm text-[var(--text-secondary)]">Zarządzanie kluczami API zostanie dodane w kolejnym etapie.</p>
    </div>
  );
}

export default function SettingsPage() {
  const { role, roleLevel } = useRole();
  const { activeTab, setActiveTab } = useSettingsStore();

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-[var(--text)]">Ustawienia</h1>

      {/* Tab bar */}
      <div className="flex gap-1 bg-[var(--surface)] rounded-lg p-1">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === t.id
                ? 'bg-[var(--accent)] text-white'
                : 'text-[var(--text-secondary)] hover:text-[var(--text)]'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'profile' && <ProfileCard role={role} roleLevel={roleLevel} />}
      {activeTab === 'preferences' && <PreferencesForm />}
      {activeTab === 'api-keys' && <ApiKeyManager />}
    </div>
  );
}
