import { customFetch } from './base';
import type {
  CalendarEventsResponse,
  CalendarConflictsResponse,
  CalendarAnalytics,
  MeetingSuggestionsResponse,
  DeepWorkRequest,
  DeepWorkResponse,
  MeetingPrep,
  MeetingMinutes,
  MeetingROI,
} from './calendar-types';

export async function fetchCalendarEvents(params?: {
  days?: number;
}): Promise<CalendarEventsResponse> {
  const queryParams: Record<string, string> = {};
  if (params?.days !== undefined) queryParams.days = String(params.days);
  return customFetch<CalendarEventsResponse>({
    url: '/calendar/events',
    method: 'GET',
    params: Object.keys(queryParams).length ? queryParams : undefined,
  });
}

export async function fetchCalendarConflicts(params?: {
  days?: number;
}): Promise<CalendarConflictsResponse> {
  const queryParams: Record<string, string> = {};
  if (params?.days !== undefined) queryParams.days = String(params.days);
  return customFetch<CalendarConflictsResponse>({
    url: '/calendar/conflicts',
    method: 'GET',
    params: Object.keys(queryParams).length ? queryParams : undefined,
  });
}

export async function fetchCalendarAnalytics(params?: {
  days?: number;
}): Promise<CalendarAnalytics> {
  const queryParams: Record<string, string> = {};
  if (params?.days !== undefined) queryParams.days = String(params.days);
  return customFetch<CalendarAnalytics>({
    url: '/calendar/analytics',
    method: 'GET',
    params: Object.keys(queryParams).length ? queryParams : undefined,
  });
}

export async function fetchMeetingSuggestions(): Promise<MeetingSuggestionsResponse> {
  return customFetch<MeetingSuggestionsResponse>({
    url: '/calendar/suggestions',
    method: 'GET',
  });
}

export async function blockDeepWork(data: DeepWorkRequest): Promise<DeepWorkResponse> {
  return customFetch<DeepWorkResponse>({
    url: '/calendar/block-deep-work',
    method: 'POST',
    data,
  });
}

export async function fetchMeetingPrep(): Promise<MeetingPrep[]> {
  return customFetch<MeetingPrep[]>({
    url: '/meeting-prep',
    method: 'GET',
  });
}

export async function fetchMeetingMinutes(params?: {
  limit?: number;
}): Promise<MeetingMinutes[]> {
  const queryParams: Record<string, string> = {};
  if (params?.limit !== undefined) queryParams.limit = String(params.limit);
  return customFetch<MeetingMinutes[]>({
    url: '/meeting-minutes',
    method: 'GET',
    params: Object.keys(queryParams).length ? queryParams : undefined,
  });
}

export async function generateMeetingMinutes(): Promise<unknown> {
  return customFetch<unknown>({
    url: '/meeting-minutes/generate',
    method: 'POST',
  });
}

export async function fetchMeetingROI(): Promise<MeetingROI> {
  return customFetch<MeetingROI>({
    url: '/meeting-roi',
    method: 'GET',
  });
}
