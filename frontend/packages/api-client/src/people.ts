import { customFetch } from './base';
import type {
  PeopleListResponse,
  Person,
  PersonFull,
  PersonCreate,
  PersonUpdate,
  Scorecard,
  SentimentTrend,
  SentimentAlertsResponse,
  DelegationScore,
  DelegationStatsResponse,
  NetworkGraph,
  EvaluateRequest,
  EvaluationResult,
  WellbeingResponse,
  ResponseTrackingResponse,
  BlindSpotsResponse,
  PersonTimelineEvent,
  TimelineEventCreate,
  RoleHistory,
  RoleHistoryCreate,
  OpenLoop,
  OpenLoopCreate,
} from './people-types';

export async function fetchPeople(params?: {
  type?: string;
  status?: string;
  limit?: number;
}): Promise<PeopleListResponse> {
  const queryParams: Record<string, string> = {};
  if (params?.type) queryParams.type = params.type;
  if (params?.status) queryParams.status = params.status;
  if (params?.limit) queryParams.limit = String(params.limit);
  return customFetch<PeopleListResponse>({
    url: '/people',
    method: 'GET',
    params: Object.keys(queryParams).length ? queryParams : undefined,
  });
}

export async function fetchPerson(slug: string): Promise<PersonFull> {
  return customFetch<PersonFull>({ url: `/people/${slug}`, method: 'GET' });
}

export async function createPerson(data: PersonCreate): Promise<Person> {
  return customFetch<Person>({ url: '/people', method: 'POST', data });
}

export async function updatePerson(slug: string, data: PersonUpdate): Promise<Person> {
  return customFetch<Person>({ url: `/people/${slug}`, method: 'PUT', data });
}

export async function deletePerson(slug: string): Promise<{ deleted: boolean }> {
  return customFetch<{ deleted: boolean }>({ url: `/people/${slug}`, method: 'DELETE' });
}

export async function fetchScorecard(slug: string): Promise<Scorecard> {
  return customFetch<Scorecard>({ url: `/scorecard/${slug}`, method: 'GET' });
}

export async function fetchSentiment(slug: string, weeks?: number): Promise<SentimentTrend> {
  const queryParams: Record<string, string> = {};
  if (weeks) queryParams.weeks = String(weeks);
  return customFetch<SentimentTrend>({
    url: `/sentiment/${slug}`,
    method: 'GET',
    params: Object.keys(queryParams).length ? queryParams : undefined,
  });
}

export async function fetchDelegation(slug: string, months?: number): Promise<DelegationScore> {
  const queryParams: Record<string, string> = {};
  if (months) queryParams.months = String(months);
  return customFetch<DelegationScore>({
    url: `/delegation/${slug}`,
    method: 'GET',
    params: Object.keys(queryParams).length ? queryParams : undefined,
  });
}

export async function fetchNetwork(): Promise<NetworkGraph> {
  return customFetch<NetworkGraph>({ url: '/network', method: 'GET' });
}

export async function triggerEvaluation(data: EvaluateRequest): Promise<EvaluationResult> {
  return customFetch<EvaluationResult>({ url: '/evaluate', method: 'POST', data });
}

export async function addTimelineEvent(
  slug: string,
  data: TimelineEventCreate,
): Promise<PersonTimelineEvent> {
  return customFetch<PersonTimelineEvent>({
    url: `/people/${slug}/timeline`,
    method: 'POST',
    data,
  });
}

export async function addRoleHistory(
  slug: string,
  data: RoleHistoryCreate,
): Promise<RoleHistory> {
  return customFetch<RoleHistory>({
    url: `/people/${slug}/roles`,
    method: 'POST',
    data,
  });
}

export async function addOpenLoop(slug: string, data: OpenLoopCreate): Promise<OpenLoop> {
  return customFetch<OpenLoop>({
    url: `/people/${slug}/loops`,
    method: 'POST',
    data,
  });
}

export async function closeOpenLoop(slug: string, loopId: number): Promise<OpenLoop> {
  return customFetch<OpenLoop>({
    url: `/people/${slug}/loops/${loopId}`,
    method: 'PUT',
  });
}

export async function fetchWellbeing(weeks?: number): Promise<WellbeingResponse> {
  const queryParams: Record<string, string> = {};
  if (weeks) queryParams.weeks = String(weeks);
  return customFetch<WellbeingResponse>({
    url: '/wellbeing',
    method: 'GET',
    params: Object.keys(queryParams).length ? queryParams : undefined,
  });
}

export async function fetchSentimentAlerts(): Promise<SentimentAlertsResponse> {
  return customFetch<SentimentAlertsResponse>({ url: '/sentiment-alerts', method: 'GET' });
}

export async function fetchResponseTracking(days?: number): Promise<ResponseTrackingResponse> {
  const queryParams: Record<string, string> = {};
  if (days) queryParams.days = String(days);
  return customFetch<ResponseTrackingResponse>({
    url: '/response-tracking',
    method: 'GET',
    params: Object.keys(queryParams).length ? queryParams : undefined,
  });
}

export async function fetchBlindSpots(): Promise<BlindSpotsResponse> {
  return customFetch<BlindSpotsResponse>({ url: '/blind-spots', method: 'GET' });
}

export async function fetchDelegationStats(): Promise<DelegationStatsResponse> {
  return customFetch<DelegationStatsResponse>({ url: '/delegation', method: 'GET' });
}
