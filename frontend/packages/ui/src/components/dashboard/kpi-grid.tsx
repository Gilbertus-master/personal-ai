'use client';

import {
  FileText,
  Calendar,
  Users,
  Target,
  DollarSign,
  AlertTriangle,
} from 'lucide-react';
import { KpiCard } from './kpi-card';

/** Minimal shape matching StatusResponse from @gilbertus/api-client */
interface StatusData {
  db: {
    documents: number;
    entities: number;
    events: number;
    alerts: number | null;
  };
}

/** Minimal shape matching BudgetResponse from @gilbertus/api-client */
interface BudgetData {
  daily_total_usd: number;
  budgets: Array<{ status: string }>;
}

interface KpiGridProps {
  status?: StatusData;
  commitmentsCount?: number;
  budget?: BudgetData;
  isLoading?: boolean;
}

function getBudgetColor(budget?: BudgetData): 'success' | 'warning' | 'danger' {
  if (!budget) return 'success';
  for (const b of budget.budgets) {
    if (b.status === 'exceeded') return 'danger';
  }
  for (const b of budget.budgets) {
    if (b.status === 'warning') return 'warning';
  }
  return 'success';
}

export function KpiGrid({ status, commitmentsCount, budget, isLoading = false }: KpiGridProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <KpiCard key={i} label="" value="" isLoading />
        ))}
      </div>
    );
  }

  const alertCount = status?.db.alerts ?? 0;

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
      <KpiCard
        label="Dokumenty"
        value={status?.db.documents ?? 0}
        icon={<FileText />}
        color="default"
      />
      <KpiCard
        label="Eventy"
        value={status?.db.events ?? 0}
        icon={<Calendar />}
        color="default"
      />
      <KpiCard
        label="Encje"
        value={status?.db.entities ?? 0}
        icon={<Users />}
        color="default"
      />
      <KpiCard
        label="Otwarte zobowiązania"
        value={commitmentsCount ?? 0}
        icon={<Target />}
        color={(commitmentsCount ?? 0) > 10 ? 'warning' : 'default'}
      />
      <KpiCard
        label="Koszty dziś"
        value={budget ? `$${budget.daily_total_usd.toFixed(2)}` : '$0.00'}
        icon={<DollarSign />}
        color={getBudgetColor(budget)}
      />
      <KpiCard
        label="Aktywne alerty"
        value={alertCount}
        icon={<AlertTriangle />}
        color={alertCount > 0 ? 'danger' : 'success'}
      />
    </div>
  );
}
