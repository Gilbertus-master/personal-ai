import { useQuery } from '@tanstack/react-query';
import {
  fetchBrief,
  fetchAlerts,
  fetchStatus,
  fetchTimeline,
  fetchCommitments,
  fetchBudget,
} from '@gilbertus/api-client';
import type {
  MorningBriefResponse,
  AlertsResponse,
  StatusResponse,
  TimelineResponse,
  CommitmentsListResponse,
  BudgetResponse,
} from '@gilbertus/api-client';
import { useDashboardStore } from '../stores/dashboard-store';

export function useBrief(options?: { force?: boolean; date?: string }) {
  const { autoRefresh, refreshInterval } = useDashboardStore();
  return useQuery<MorningBriefResponse>({
    queryKey: ['brief', options?.date ?? 'today'],
    queryFn: () => fetchBrief({ force: options?.force, date: options?.date }),
    refetchInterval: autoRefresh ? refreshInterval : false,
  });
}

export function useAlerts(options?: { activeOnly?: boolean; severity?: string }) {
  const { autoRefresh } = useDashboardStore();
  return useQuery<AlertsResponse>({
    queryKey: ['alerts', options?.activeOnly, options?.severity],
    queryFn: () =>
      fetchAlerts({
        active_only: options?.activeOnly ?? true,
        severity: options?.severity,
      }),
    refetchInterval: autoRefresh ? 60_000 : false,
  });
}

export function useStatus() {
  const { autoRefresh } = useDashboardStore();
  return useQuery<StatusResponse>({
    queryKey: ['status'],
    queryFn: fetchStatus,
    refetchInterval: autoRefresh ? 60_000 : false,
  });
}

export function useTimeline(options?: { eventType?: string; limit?: number }) {
  const { autoRefresh, refreshInterval, timelineFilter } = useDashboardStore();
  const filter = options?.eventType ?? timelineFilter;
  return useQuery<TimelineResponse>({
    queryKey: ['timeline', filter, options?.limit],
    queryFn: () =>
      fetchTimeline({
        event_type: filter ?? undefined,
        limit: options?.limit ?? 20,
      }),
    refetchInterval: autoRefresh ? refreshInterval : false,
  });
}

export function useCommitmentsCount() {
  const { autoRefresh, refreshInterval } = useDashboardStore();
  return useQuery<CommitmentsListResponse>({
    queryKey: ['commitments', 'open'],
    queryFn: () => fetchCommitments({ status: 'open' }),
    refetchInterval: autoRefresh ? refreshInterval : false,
  });
}

export function useBudget() {
  const { autoRefresh, refreshInterval } = useDashboardStore();
  return useQuery<BudgetResponse>({
    queryKey: ['budget'],
    queryFn: fetchBudget,
    refetchInterval: autoRefresh ? refreshInterval : false,
  });
}

export function useAlertsBell() {
  return useQuery<AlertsResponse>({
    queryKey: ['alerts', 'bell'],
    queryFn: () => fetchAlerts({ active_only: true, limit: 5 }),
    refetchInterval: 60_000,
  });
}
