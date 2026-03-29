'use client';

import { useRouter } from 'next/navigation';
import {
  Shield,
  FolderOpen,
  Clock,
  AlertTriangle,
  Gavel,
  CheckSquare,
  Calendar,
  FileText,
  GraduationCap,
  ShieldAlert,
  Users,
  BarChart3,
} from 'lucide-react';
import { KpiCard } from '../dashboard/kpi-card';
import { AreaStatusCard } from './area-status-card';

import type { ComplianceDashboard as DashboardData, ComplianceArea } from '@gilbertus/api-client';

// ── Props ───────────────────────────────────────────────────────────────────

export interface ComplianceDashboardProps {
  dashboard?: DashboardData;
  areas?: ComplianceArea[];
  isLoading?: boolean;
}

// ── Risk score color ────────────────────────────────────────────────────────

function riskScoreColor(score: number): 'success' | 'warning' | 'danger' | 'default' {
  if (score < 30) return 'success';
  if (score < 60) return 'warning';
  if (score < 80) return 'warning'; // orange maps to warning in KpiCard
  return 'danger';
}

// ── Quick links ─────────────────────────────────────────────────────────────

const QUICK_LINKS = [
  { href: '/compliance/matters', label: 'Sprawy', icon: Gavel },
  { href: '/compliance/obligations', label: 'Obowiązki', icon: CheckSquare },
  { href: '/compliance/deadlines', label: 'Terminy', icon: Calendar },
  { href: '/compliance/documents', label: 'Dokumenty', icon: FileText },
  { href: '/compliance/trainings', label: 'Szkolenia', icon: GraduationCap },
  { href: '/compliance/risks', label: 'Ryzyka', icon: ShieldAlert },
  { href: '/compliance/raci', label: 'RACI', icon: Users },
  { href: '/compliance/reports', label: 'Raporty', icon: BarChart3 },
] as const;

// ── Component ───────────────────────────────────────────────────────────────

export function ComplianceDashboard({ dashboard, areas, isLoading = false }: ComplianceDashboardProps) {
  const router = useRouter();

  return (
    <div className="space-y-6">
      {/* KPI Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          label="Obowiązki"
          value={isLoading ? '' : `${dashboard?.compliant_count ?? 0}/${dashboard?.total_obligations ?? 0}`}
          icon={<Shield />}
          color="success"
          isLoading={isLoading}
        />
        <KpiCard
          label="Sprawy otwarte"
          value={dashboard?.open_matters ?? 0}
          icon={<FolderOpen />}
          color="default"
          isLoading={isLoading}
        />
        <KpiCard
          label="Zaległe terminy"
          value={dashboard?.overdue_deadlines ?? 0}
          icon={<Clock />}
          color={(dashboard?.overdue_deadlines ?? 0) > 0 ? 'danger' : 'success'}
          isLoading={isLoading}
        />
        <KpiCard
          label="Ryzyko ogólne"
          value={dashboard?.overall_risk_score ?? 0}
          icon={<AlertTriangle />}
          color={riskScoreColor(dashboard?.overall_risk_score ?? 0)}
          isLoading={isLoading}
        />
      </div>

      {/* Area Status Grid */}
      <div>
        <h2 className="text-lg font-semibold text-[var(--text)] mb-3">Obszary compliance</h2>
        {isLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 9 }).map((_, i) => (
              <div
                key={i}
                className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4"
              >
                <div className="h-5 w-24 animate-pulse rounded bg-[var(--bg-hover)] mb-2" />
                <div className="h-4 w-16 animate-pulse rounded bg-[var(--bg-hover)] mb-2" />
                <div className="h-3 w-32 animate-pulse rounded bg-[var(--bg-hover)]" />
              </div>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {areas?.map((area) => (
              <AreaStatusCard
                key={area.code}
                area={area}
                onClick={() => router.push(`/compliance/areas/${area.code}`)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Quick Links */}
      <div>
        <h2 className="text-lg font-semibold text-[var(--text)] mb-3">Szybkie linki</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {QUICK_LINKS.map(({ href, label, icon: Icon }) => (
            <button
              key={href}
              type="button"
              onClick={() => router.push(href)}
              className="flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3 text-sm text-[var(--text-secondary)] hover:text-[var(--text)] hover:border-[var(--accent)] transition-colors"
            >
              <Icon className="h-4 w-4" />
              {label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
