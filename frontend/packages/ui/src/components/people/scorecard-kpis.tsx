'use client';

import type { Scorecard } from '@gilbertus/api-client';
import { KpiCard } from '../dashboard/kpi-card';
import { Database, Calendar, CircleDot, Activity } from 'lucide-react';

interface ScorecardKpisProps {
  scorecard?: Scorecard;
  isLoading?: boolean;
}

export function ScorecardKpis({ scorecard, isLoading = false }: ScorecardKpisProps) {
  const dataVolume = scorecard
    ? scorecard.data_volume.chunks + scorecard.data_volume.events
    : 0;

  const eventsCount = scorecard?.recent_events_30d.length ?? 0;
  const openLoopsCount = scorecard?.open_loops.length ?? 0;

  const lastActivity = scorecard?.weekly_activity?.length
    ? scorecard.weekly_activity[scorecard.weekly_activity.length - 1]
    : null;
  const activityLabel = lastActivity
    ? `${lastActivity.count} (${lastActivity.week})`
    : '-';

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <KpiCard
        label="Dane"
        value={dataVolume}
        icon={<Database />}
        isLoading={isLoading}
      />
      <KpiCard
        label="Eventy (30d)"
        value={eventsCount}
        icon={<Calendar />}
        isLoading={isLoading}
      />
      <KpiCard
        label="Otwarte w\u0105tki"
        value={openLoopsCount}
        icon={<CircleDot />}
        color={openLoopsCount > 3 ? 'warning' : 'default'}
        isLoading={isLoading}
      />
      <KpiCard
        label="Aktywno\u015b\u0107"
        value={activityLabel}
        icon={<Activity />}
        isLoading={isLoading}
      />
    </div>
  );
}
