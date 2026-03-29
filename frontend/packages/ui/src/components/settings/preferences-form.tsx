'use client';

import { Globe, Sun, Moon, Bell } from 'lucide-react';
import { cn } from '../../lib/utils';

interface PreferencesFormProps {
  language: 'pl' | 'en';
  theme: 'dark' | 'light';
  notifications: {
    email_alerts: boolean;
    whatsapp_alerts: boolean;
    daily_brief: boolean;
  };
  onLanguageChange: (lang: 'pl' | 'en') => void;
  onThemeChange: (theme: 'dark' | 'light') => void;
  onNotificationsChange: (
    prefs: Partial<{
      email_alerts: boolean;
      whatsapp_alerts: boolean;
      daily_brief: boolean;
    }>,
  ) => void;
}

export function PreferencesForm({
  language,
  theme,
  notifications,
  onLanguageChange,
  onThemeChange,
  onNotificationsChange,
}: PreferencesFormProps) {
  return (
    <div className="rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] p-6 space-y-6">
      {/* Language */}
      <Section icon={<Globe className="h-4 w-4" />} label="Język">
        <ToggleGroup
          options={[
            { value: 'pl', label: 'PL' },
            { value: 'en', label: 'EN' },
          ]}
          active={language}
          onChange={(v) => onLanguageChange(v as 'pl' | 'en')}
        />
      </Section>

      {/* Theme */}
      <Section icon={<Sun className="h-4 w-4" />} label="Motyw">
        <ToggleGroup
          options={[
            { value: 'dark', label: 'Ciemny', icon: <Moon className="h-3.5 w-3.5" /> },
            { value: 'light', label: 'Jasny', icon: <Sun className="h-3.5 w-3.5" /> },
          ]}
          active={theme}
          onChange={(v) => onThemeChange(v as 'dark' | 'light')}
        />
      </Section>

      {/* Notifications */}
      <Section
        icon={<Bell className="h-4 w-4" />}
        label="Powiadomienia"
        note="(wkrótce)"
      >
        <div className="space-y-3">
          <SwitchRow
            label="Alerty email"
            checked={notifications.email_alerts}
            onChange={(v) => onNotificationsChange({ email_alerts: v })}
          />
          <SwitchRow
            label="Alerty WhatsApp"
            checked={notifications.whatsapp_alerts}
            onChange={(v) => onNotificationsChange({ whatsapp_alerts: v })}
          />
          <SwitchRow
            label="Poranny brief"
            checked={notifications.daily_brief}
            onChange={(v) => onNotificationsChange({ daily_brief: v })}
          />
        </div>
      </Section>
    </div>
  );
}

function Section({
  icon,
  label,
  note,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  note?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <span className="text-[var(--text-secondary)]">{icon}</span>
        <h4 className="text-sm font-medium text-[var(--text)]">{label}</h4>
        {note && (
          <span className="text-xs text-[var(--text-secondary)] italic">{note}</span>
        )}
      </div>
      {children}
    </div>
  );
}

function ToggleGroup({
  options,
  active,
  onChange,
}: {
  options: { value: string; label: string; icon?: React.ReactNode }[];
  active: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="inline-flex rounded-md border border-[var(--border)] overflow-hidden">
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(opt.value)}
          className={cn(
            'flex items-center gap-1.5 px-4 py-1.5 text-sm font-medium transition-colors',
            active === opt.value
              ? 'bg-[var(--accent)] text-white'
              : 'bg-[var(--surface)] text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]',
          )}
        >
          {opt.icon}
          {opt.label}
        </button>
      ))}
    </div>
  );
}

function SwitchRow({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="flex items-center justify-between cursor-pointer">
      <span className="text-sm text-[var(--text)]">{label}</span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={cn(
          'relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors',
          checked ? 'bg-[var(--accent)]' : 'bg-[var(--border)]',
        )}
      >
        <span
          className={cn(
            'inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform',
            checked ? 'translate-x-[18px]' : 'translate-x-[3px]',
          )}
        />
      </button>
    </label>
  );
}
