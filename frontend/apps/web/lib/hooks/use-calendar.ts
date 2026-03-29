import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchCalendarEvents,
  fetchCalendarConflicts,
  fetchCalendarAnalytics,
  fetchMeetingPrep,
  fetchMeetingMinutes,
  fetchMeetingSuggestions,
  fetchMeetingROI,
  blockDeepWork,
  generateMeetingMinutes,
} from '@gilbertus/api-client';
import { useCalendarStore } from '@/lib/stores/calendar-store';

export function useCalendarEvents(days?: number) {
  const { eventsDays, autoRefresh, refreshInterval } = useCalendarStore();
  const d = days ?? eventsDays;
  return useQuery({
    queryKey: ['calendar-events', d],
    queryFn: () => fetchCalendarEvents({ days: d }),
    staleTime: 60_000,
    refetchInterval: autoRefresh ? refreshInterval : false,
  });
}

export function useCalendarConflicts(days?: number) {
  const { eventsDays } = useCalendarStore();
  const d = days ?? eventsDays;
  return useQuery({
    queryKey: ['calendar-conflicts', d],
    queryFn: () => fetchCalendarConflicts({ days: d }),
    staleTime: 60_000,
  });
}

export function useCalendarAnalytics(days?: number) {
  const { analyticsDays } = useCalendarStore();
  const d = days ?? analyticsDays;
  return useQuery({
    queryKey: ['calendar-analytics', d],
    queryFn: () => fetchCalendarAnalytics({ days: d }),
    staleTime: 120_000,
  });
}

export function useMeetingPrep() {
  return useQuery({
    queryKey: ['meeting-prep'],
    queryFn: () => fetchMeetingPrep(),
    staleTime: 300_000,
  });
}

export function useMeetingMinutes(limit?: number) {
  return useQuery({
    queryKey: ['meeting-minutes', limit],
    queryFn: () => fetchMeetingMinutes({ limit }),
    staleTime: 60_000,
  });
}

export function useMeetingSuggestions() {
  return useQuery({
    queryKey: ['meeting-suggestions'],
    queryFn: () => fetchMeetingSuggestions(),
    staleTime: 300_000,
  });
}

export function useMeetingROI() {
  return useQuery({
    queryKey: ['meeting-roi'],
    queryFn: () => fetchMeetingROI(),
    staleTime: 120_000,
  });
}

export function useBlockDeepWork() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: blockDeepWork,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['calendar-events'] }),
  });
}

export function useGenerateMinutes() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: generateMeetingMinutes,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['meeting-minutes'] }),
  });
}
