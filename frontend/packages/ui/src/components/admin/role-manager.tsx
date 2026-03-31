'use client';

import { useState } from 'react';
import { ChevronDown, ChevronRight, Shield, Users, Eye, Wrench } from 'lucide-react';
import type { RoleDefinition } from '@gilbertus/api-client';

interface RoleManagerProps {
  roles: RoleDefinition[];
  isLoading: boolean;
}

const levelColors: Record<number, string> = {
  100: 'bg-purple-600/20 text-purple-400 border-purple-500/30',
  99: 'bg-red-600/20 text-red-400 border-red-500/30',
  70: 'bg-orange-600/20 text-orange-400 border-orange-500/30',
  60: 'bg-blue-600/20 text-blue-400 border-blue-500/30',
  50: 'bg-cyan-600/20 text-cyan-400 border-cyan-500/30',
  40: 'bg-green-600/20 text-green-400 border-green-500/30',
  30: 'bg-yellow-600/20 text-yellow-400 border-yellow-500/30',
  20: 'bg-gray-600/20 text-gray-400 border-gray-500/30',
};

function PermissionBadge({ perm }: { perm: string }) {
  if (perm === '*') {
    return (
      <span className="rounded-full bg-purple-600/20 px-2 py-0.5 text-[10px] font-medium text-purple-400">
        Pełen dostęp
      </span>
    );
  }
  const [category] = perm.split(':');
  const catColors: Record<string, string> = {
    data: 'bg-blue-600/15 text-blue-400',
    config: 'bg-orange-600/15 text-orange-400',
    commands: 'bg-green-600/15 text-green-400',
    users: 'bg-red-600/15 text-red-400',
    sync: 'bg-cyan-600/15 text-cyan-400',
    infra: 'bg-yellow-600/15 text-yellow-400',
    dev: 'bg-purple-600/15 text-purple-400',
    financials: 'bg-emerald-600/15 text-emerald-400',
    evaluations: 'bg-pink-600/15 text-pink-400',
    communications: 'bg-indigo-600/15 text-indigo-400',
    queries: 'bg-teal-600/15 text-teal-400',
    prompts: 'bg-amber-600/15 text-amber-400',
    rbac: 'bg-rose-600/15 text-rose-400',
    views: 'bg-slate-600/15 text-slate-400',
  };
  return (
    <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${catColors[category] ?? 'bg-gray-600/15 text-gray-400'}`}>
      {perm}
    </span>
  );
}

function ClassificationBadge({ cls }: { cls: string }) {
  const clsColors: Record<string, string> = {
    public: 'bg-green-600/20 text-green-400',
    internal: 'bg-blue-600/20 text-blue-400',
    confidential: 'bg-orange-600/20 text-orange-400',
    ceo_only: 'bg-red-600/20 text-red-400',
    personal: 'bg-purple-600/20 text-purple-400',
  };
  const labels: Record<string, string> = {
    public: 'Publiczne',
    internal: 'Wewnętrzne',
    confidential: 'Poufne',
    ceo_only: 'Tylko CEO',
    personal: 'Osobiste',
  };
  return (
    <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${clsColors[cls] ?? 'bg-gray-600/20 text-gray-400'}`}>
      {labels[cls] ?? cls}
    </span>
  );
}

function ModuleBadge({ mod }: { mod: string }) {
  if (mod === 'all') {
    return (
      <span className="rounded-full bg-purple-600/20 px-2 py-0.5 text-[10px] font-medium text-purple-400">
        Wszystkie moduły
      </span>
    );
  }
  return (
    <span className="rounded-full bg-[var(--bg)] px-2 py-0.5 text-[10px] text-[var(--text-secondary)]">
      {mod}
    </span>
  );
}

export function RoleManager({ roles, isLoading }: RoleManagerProps) {
  const [expandedRole, setExpandedRole] = useState<string | null>(null);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-64 animate-pulse rounded bg-[var(--surface)]" />
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-20 animate-pulse rounded bg-[var(--surface)]" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-[var(--text)]">Role i uprawnienia</h2>
        <span className="text-sm text-[var(--text-secondary)]">{roles.length} ról</span>
      </div>

      {/* Role cards */}
      <div className="space-y-2">
        {roles.map((role) => {
          const expanded = expandedRole === role.name;
          const colorClass = levelColors[role.level] ?? 'bg-gray-600/20 text-gray-400 border-gray-500/30';

          return (
            <div
              key={role.name}
              className="rounded-lg border border-[var(--border)] bg-[var(--surface)] overflow-hidden"
            >
              {/* Header row */}
              <button
                onClick={() => setExpandedRole(expanded ? null : role.name)}
                className="flex w-full items-center gap-4 px-4 py-3 text-left hover:bg-[var(--surface-hover)] transition-colors"
              >
                <span className="text-[var(--text-secondary)]">
                  {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                </span>

                {/* Level badge */}
                <span className={`inline-flex min-w-[52px] items-center justify-center rounded-md border px-2 py-0.5 text-xs font-bold ${colorClass}`}>
                  L{role.level}
                </span>

                {/* Name + label */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-[var(--text)]">{role.label}</span>
                    <span className="font-mono text-xs text-[var(--text-secondary)]">{role.name}</span>
                  </div>
                  <p className="text-xs text-[var(--text-secondary)] truncate">{role.description}</p>
                </div>

                {/* Quick stats */}
                <div className="flex items-center gap-4 shrink-0">
                  <div className="flex items-center gap-1 text-xs text-[var(--text-secondary)]" title="Użytkownicy">
                    <Users className="h-3.5 w-3.5" />
                    <span>{role.user_count}</span>
                  </div>
                  <div className="flex items-center gap-1 text-xs text-[var(--text-secondary)]" title="Uprawnienia">
                    <Shield className="h-3.5 w-3.5" />
                    <span>{role.permissions[0] === '*' ? '∞' : role.permissions.length}</span>
                  </div>
                  <div className="flex items-center gap-1 text-xs text-[var(--text-secondary)]" title="Moduły">
                    <Wrench className="h-3.5 w-3.5" />
                    <span>{role.modules[0] === 'all' ? '∞' : role.modules.length}</span>
                  </div>
                  <div className="flex items-center gap-1 text-xs text-[var(--text-secondary)]" title="Klasyfikacje">
                    <Eye className="h-3.5 w-3.5" />
                    <span>{role.classifications.length}</span>
                  </div>
                </div>
              </button>

              {/* Expanded details */}
              {expanded && (
                <div className="border-t border-[var(--border)] bg-[var(--bg)] px-6 py-4 space-y-4">
                  {/* Permissions */}
                  <div>
                    <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                      Uprawnienia ({role.permissions[0] === '*' ? 'pełne' : role.permissions.length})
                    </h4>
                    <div className="flex flex-wrap gap-1.5">
                      {role.permissions.map((p) => (
                        <PermissionBadge key={p} perm={p} />
                      ))}
                    </div>
                  </div>

                  {/* Classifications */}
                  <div>
                    <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                      Dostęp do danych ({role.classifications.length} poziomów)
                    </h4>
                    {role.classifications.length > 0 ? (
                      <div className="flex flex-wrap gap-1.5">
                        {role.classifications.map((c) => (
                          <ClassificationBadge key={c} cls={c} />
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-[var(--text-secondary)]">Brak dostępu do danych biznesowych</p>
                    )}
                  </div>

                  {/* Modules */}
                  <div>
                    <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                      Moduły ({role.modules[0] === 'all' ? 'wszystkie' : role.modules.length})
                    </h4>
                    <div className="flex flex-wrap gap-1.5">
                      {role.modules.map((m) => (
                        <ModuleBadge key={m} mod={m} />
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
