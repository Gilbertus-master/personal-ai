'use client';

import type { ComplianceArea } from '@gilbertus/api-client';
import { ComplianceBadge } from './compliance-badge';

export interface AreaStatusCardProps {
  area: ComplianceArea;
  onClick?: () => void;
}

export function AreaStatusCard({ area, onClick }: AreaStatusCardProps) {
  const regs = area.key_regulations ?? [];
  const shown = regs.slice(0, 2);
  const remaining = regs.length - shown.length;

  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 cursor-pointer hover:border-[var(--accent)] transition-colors text-left w-full"
    >
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-semibold text-[var(--text)]">{area.name_pl}</h3>
        <ComplianceBadge type="risk" value={area.risk_level} size="sm" />
      </div>

      <p className="text-xs text-[var(--text-secondary)] mb-2">{area.governing_body}</p>

      {shown.length > 0 && (
        <p className="text-xs text-[var(--text-muted)] line-clamp-2">
          {shown.join(', ')}
          {remaining > 0 && ` +${remaining} więcej`}
        </p>
      )}
    </button>
  );
}
