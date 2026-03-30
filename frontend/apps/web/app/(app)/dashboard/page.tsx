'use client';

import { useState } from 'react';
import { useRole } from '@gilbertus/rbac';
import {
  KpiGrid,
  MorningBrief,
  AlertsFeed,
  ActivityTimeline,
  SystemStatus,
  DashboardQuickActions,
  DashboardDetailDrawer,
  AlertDetailDrawer,
} from '@gilbertus/ui';
import type { TileKey } from '@gilbertus/ui';
import type { AlertItem } from '@gilbertus/api-client';
import { resolveAlert } from '@gilbertus/api-client';
import {
  useBrief,
  useAlerts,
  useStatus,
  useTimeline,
  useCommitmentsCount,
  useBudget,
} from '@/lib/hooks/use-dashboard';
import { useDashboardStore } from '@/lib/stores/dashboard-store';
import { useQueryClient } from '@tanstack/react-query';

export default function DashboardPage() {
  const { role } = useRole();
  const queryClient = useQueryClient();
  const store = useDashboardStore();
  const [drawerTile, setDrawerTile] = useState<TileKey | null>(null);
  const [selectedAlert, setSelectedAlert] = useState<AlertItem | null>(null);
  const [isResolving, setIsResolving] = useState(false);

  const brief = useBrief();
  const alerts = useAlerts();
  const status = useStatus();
  const timeline = useTimeline();
  const commitments = useCommitmentsCount();
  const budget = useBudget();

  const handleBriefRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ['brief'] });
  };

  const handleResolveAlert = async (
    alertId: number,
    action: 'fix' | 'suppress',
    comment: string,
    fixInstruction?: string,
  ) => {
    setIsResolving(true);
    try {
      await resolveAlert(alertId, { action, comment, fix_instruction: fixInstruction });
      setSelectedAlert(null);
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
    } catch (err) {
      console.error('Failed to resolve alert', err);
    } finally {
      setIsResolving(false);
    }
  };

  const isFullAccess = role === 'gilbertus_admin' || role === 'ceo';
  const isBoardAccess = isFullAccess || role === 'board';
  const isOperator = role === 'operator';
  const isSpecialist = role === 'specialist';

  if (isOperator) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-[var(--text)]">Status systemu</h1>
        <SystemStatus status={status.data} isLoading={status.isLoading} error={status.error} />
      </div>
    );
  }

  if (isSpecialist) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-[var(--text)]">Panel główny</h1>
        <p className="text-sm text-[var(--text-secondary)]">
          Twoje zadania pojawią się tutaj wkrótce.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-[var(--text)]">Panel główny</h1>

      {isFullAccess && (
        <KpiGrid
          status={status.data}
          commitmentsCount={commitments.data?.commitments?.length}
          budget={budget.data}
          isLoading={status.isLoading || commitments.isLoading || budget.isLoading}
          onTileClick={setDrawerTile}
        />
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {isBoardAccess && (
            <MorningBrief
              data={brief.data}
              isLoading={brief.isLoading}
              error={brief.error}
              onRefresh={handleBriefRefresh}
              isCollapsed={store.collapsedSections.includes('brief')}
              onToggleCollapse={() => store.toggleSection('brief')}
            />
          )}

          {isBoardAccess && (
            <ActivityTimeline
              events={timeline.data?.events}
              isLoading={timeline.isLoading}
              error={timeline.error}
              filter={store.timelineFilter}
              onFilterChange={store.setTimelineFilter}
              isCollapsed={store.collapsedSections.includes('timeline')}
              onToggleCollapse={() => store.toggleSection('timeline')}
            />
          )}
        </div>

        <div className="space-y-6">
          {isBoardAccess && (
            <AlertsFeed
              alerts={alerts.data?.alerts}
              dismissedIds={store.dismissedAlertIds}
              isLoading={alerts.isLoading}
              error={alerts.error}
              onDismiss={store.dismissAlert}
              isCollapsed={store.collapsedSections.includes('alerts')}
              onToggleCollapse={() => store.toggleSection('alerts')}
            />
          )}

          {isFullAccess && (
            <SystemStatus
              status={status.data}
              isLoading={status.isLoading}
              error={status.error}
            />
          )}

          <DashboardQuickActions />
        </div>
      </div>

      <DashboardDetailDrawer
        tile={drawerTile}
        onClose={() => setDrawerTile(null)}
        onOpenAlert={(alert) => {
          setDrawerTile(null);
          setSelectedAlert(alert);
        }}
      />

      <AlertDetailDrawer
        alert={selectedAlert}
        onClose={() => setSelectedAlert(null)}
        onResolve={handleResolveAlert}
        isResolving={isResolving}
      />
    </div>
  );
}
