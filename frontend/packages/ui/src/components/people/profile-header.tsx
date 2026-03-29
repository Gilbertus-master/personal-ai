'use client';

import { ArrowLeft, Pencil, Star } from 'lucide-react';
import type { PersonFull } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';

interface ProfileHeaderProps {
  person: PersonFull;
  canEdit?: boolean;
  canEvaluate?: boolean;
  onEdit?: () => void;
  onEvaluate?: () => void;
}

const SENTIMENT_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  positive: { bg: 'bg-emerald-500/20', text: 'text-emerald-400', label: 'Pozytywny' },
  neutral: { bg: 'bg-zinc-500/20', text: 'text-zinc-400', label: 'Neutralny' },
  negative: { bg: 'bg-red-500/20', text: 'text-red-400', label: 'Negatywny' },
};

const STATUS_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  active: { bg: 'bg-emerald-500/20', text: 'text-emerald-400', label: 'Aktywny' },
  inactive: { bg: 'bg-zinc-500/20', text: 'text-zinc-400', label: 'Nieaktywny' },
};

function getInitials(firstName: string, lastName: string | null): string {
  const first = firstName.charAt(0).toUpperCase();
  const last = lastName ? lastName.charAt(0).toUpperCase() : '';
  return first + last;
}

function hashColor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  const hue = Math.abs(hash) % 360;
  return `hsl(${hue}, 60%, 45%)`;
}

export function ProfileHeader({
  person,
  canEdit = false,
  canEvaluate = false,
  onEdit,
  onEvaluate,
}: ProfileHeaderProps) {
  const rel = person.relationship;
  const fullName = [person.first_name, person.last_name].filter(Boolean).join(' ');
  const initials = getInitials(person.first_name, person.last_name);
  const avatarColor = hashColor(fullName);

  const status = rel?.status ?? 'active';
  const sentiment = rel?.sentiment ?? 'neutral';
  const statusStyle = STATUS_STYLES[status] ?? STATUS_STYLES.active;
  const sentimentStyle = SENTIMENT_STYLES[sentiment] ?? SENTIMENT_STYLES.neutral;

  return (
    <div className="space-y-4">
      <a
        href="/people"
        className="inline-flex items-center gap-1 text-sm text-[var(--text-secondary)] hover:text-[var(--text)] transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        Ludzie
      </a>

      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-4">
          <div
            className="flex h-[60px] w-[60px] shrink-0 items-center justify-center rounded-full text-xl font-bold text-white"
            style={{ backgroundColor: avatarColor }}
          >
            {initials}
          </div>

          <div className="space-y-2">
            <h1 className="text-2xl font-bold text-[var(--text)]">{fullName}</h1>

            {rel && (rel.current_role || rel.organization) && (
              <p className="text-sm text-[var(--text-secondary)]">
                {[rel.current_role, rel.organization].filter(Boolean).join(' @ ')}
              </p>
            )}

            <div className="flex flex-wrap items-center gap-2">
              <span className={cn('inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium', statusStyle.bg, statusStyle.text)}>
                {statusStyle.label}
              </span>
              <span className={cn('inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium', sentimentStyle.bg, sentimentStyle.text)}>
                {sentimentStyle.label}
              </span>
              {rel?.contact_channel && (
                <span className="inline-flex items-center rounded-full bg-blue-500/20 px-2.5 py-0.5 text-xs font-medium text-blue-400">
                  {rel.contact_channel}
                </span>
              )}
            </div>

            {person.aliases.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {person.aliases.map((alias) => (
                  <span
                    key={alias}
                    className="inline-flex rounded bg-[var(--bg-hover)] px-1.5 py-0.5 text-xs text-[var(--text-muted)]"
                  >
                    {alias}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {canEdit && onEdit && (
            <button
              onClick={onEdit}
              className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] transition-colors"
            >
              <Pencil className="h-4 w-4" />
              Edytuj
            </button>
          )}
          {canEvaluate && onEvaluate && (
            <button
              onClick={onEvaluate}
              className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] transition-colors"
            >
              <Star className="h-4 w-4" />
              Oce\u0144
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
