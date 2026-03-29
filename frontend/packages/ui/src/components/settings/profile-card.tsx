'use client';

import {
  User,
  Mail,
  Shield,
  Building2,
  Key,
} from 'lucide-react';
import { cn } from '../../lib/utils';

interface ProfileCardProps {
  name: string;
  email: string;
  role: string;
  roleLevel: number;
  department?: string;
  authType?: string;
  lastLogin?: string;
  permissions?: string[];
}

function getRoleBadgeColor(level: number): string {
  if (level >= 90) return 'bg-purple-500/15 text-purple-400';
  if (level >= 60) return 'bg-blue-500/15 text-blue-400';
  if (level >= 40) return 'bg-emerald-500/15 text-emerald-400';
  return 'bg-gray-500/15 text-gray-400';
}

function getInitials(name: string): string {
  return name
    .split(' ')
    .map((w) => w[0])
    .filter(Boolean)
    .slice(0, 2)
    .join('')
    .toUpperCase();
}

export function ProfileCard({
  name,
  email,
  role,
  roleLevel,
  department,
  authType,
  lastLogin,
  permissions = [],
}: ProfileCardProps) {
  const initials = getInitials(name);

  return (
    <div className="rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] p-6">
      {/* Avatar + Name */}
      <div className="flex items-center gap-4 mb-6">
        <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full bg-[var(--accent)] text-white text-xl font-bold">
          {initials}
        </div>
        <div>
          <h3 className="text-lg font-semibold text-[var(--text)]">{name}</h3>
          <span
            className={cn(
              'inline-block mt-1 rounded-full px-2.5 py-0.5 text-xs font-medium',
              getRoleBadgeColor(roleLevel),
            )}
          >
            {role}
          </span>
        </div>
      </div>

      {/* Info rows */}
      <div className="space-y-3">
        <InfoRow icon={<Mail className="h-4 w-4" />} label="Email" value={email} />
        <InfoRow icon={<Shield className="h-4 w-4" />} label="Rola" value={role} />
        <InfoRow icon={<User className="h-4 w-4" />} label="Poziom" value={String(roleLevel)} />
        {department && (
          <InfoRow icon={<Building2 className="h-4 w-4" />} label="Dział" value={department} />
        )}
      </div>

      {/* Session info */}
      {(authType || lastLogin || permissions.length > 0) && (
        <div className="mt-6 border-t border-[var(--border)] pt-4">
          <h4 className="text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)] mb-3">
            Sesja
          </h4>
          <div className="space-y-3">
            {authType && (
              <InfoRow icon={<Key className="h-4 w-4" />} label="Typ auth" value={authType} />
            )}
            {lastLogin && (
              <InfoRow icon={<Key className="h-4 w-4" />} label="Ostatnie logowanie" value={lastLogin} />
            )}
            {permissions.length > 0 && (
              <div className="flex items-start gap-3">
                <Shield className="h-4 w-4 mt-0.5 text-[var(--text-secondary)]" />
                <div>
                  <span className="text-xs text-[var(--text-secondary)]">Uprawnienia</span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {permissions.map((p) => (
                      <span
                        key={p}
                        className="rounded-full bg-[var(--surface-hover)] px-2 py-0.5 text-xs text-[var(--text-secondary)]"
                      >
                        {p}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function InfoRow({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-[var(--text-secondary)]">{icon}</span>
      <div className="flex flex-col">
        <span className="text-xs text-[var(--text-secondary)]">{label}</span>
        <span className="text-sm text-[var(--text)]">{value}</span>
      </div>
    </div>
  );
}
