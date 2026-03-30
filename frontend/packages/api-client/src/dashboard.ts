import { customFetch } from './base';
import type {
  MorningBriefResponse,
  AlertsResponse,
  StatusResponse,
  TimelineRequest,
  TimelineResponse,
  CommitmentsListResponse,
  BudgetResponse,
  ResolveAlertRequest,
  ResolveAlertResponse,
  AlertSuppressionsResponse,
  AlertFixTasksResponse,
} from './dashboard-types';

export async function fetchBrief(params?: {
  force?: boolean;
  days?: number;
  date?: string;
}): Promise<MorningBriefResponse> {
  const queryParams: Record<string, string> = {};
  if (params?.force) queryParams.force = 'true';
  if (params?.days) queryParams.days = String(params.days);
  if (params?.date) queryParams.date = params.date;
  return customFetch<MorningBriefResponse>({
    url: '/brief/today',
    method: 'GET',
    params: Object.keys(queryParams).length ? queryParams : undefined,
  });
}

export async function fetchAlerts(params?: {
  active_only?: boolean;
  alert_type?: string;
  severity?: string;
  limit?: number;
  refresh?: boolean;
  date?: string;
}): Promise<AlertsResponse> {
  const queryParams: Record<string, string> = {};
  if (params?.active_only !== undefined) queryParams.active_only = String(params.active_only);
  if (params?.alert_type) queryParams.alert_type = params.alert_type;
  if (params?.severity) queryParams.severity = params.severity;
  if (params?.limit) queryParams.limit = String(params.limit);
  if (params?.refresh) queryParams.refresh = 'true';
  if (params?.date) queryParams.date = params.date;
  return customFetch<AlertsResponse>({
    url: '/alerts',
    method: 'GET',
    params: Object.keys(queryParams).length ? queryParams : undefined,
  });
}

export async function fetchStatus(): Promise<StatusResponse> {
  return customFetch<StatusResponse>({ url: '/status', method: 'GET' });
}

export async function fetchTimeline(body?: TimelineRequest): Promise<TimelineResponse> {
  return customFetch<TimelineResponse>({
    url: '/timeline',
    method: 'POST',
    data: body ?? {},
  });
}

export async function fetchCommitments(params?: {
  status?: string;
  limit?: number;
}): Promise<CommitmentsListResponse> {
  const queryParams: Record<string, string> = {};
  if (params?.status) queryParams.status = params.status;
  if (params?.limit) queryParams.limit = String(params.limit);
  return customFetch<CommitmentsListResponse>({
    url: '/commitments',
    method: 'GET',
    params: Object.keys(queryParams).length ? queryParams : undefined,
  });
}

export async function fetchBudget(): Promise<BudgetResponse> {
  return customFetch<BudgetResponse>({ url: '/costs/budget', method: 'GET' });
}

export async function resolveAlert(
  alertId: number,
  data: ResolveAlertRequest,
): Promise<ResolveAlertResponse> {
  return customFetch<ResolveAlertResponse>({
    url: `/alerts/${alertId}/resolve`,
    method: 'POST',
    data,
  });
}

export async function fetchAlertSuppressions(): Promise<AlertSuppressionsResponse> {
  return customFetch<AlertSuppressionsResponse>({
    url: '/alerts/suppressions',
    method: 'GET',
  });
}

export async function deleteAlertSuppression(id: number): Promise<{ status: string }> {
  return customFetch<{ status: string }>({
    url: `/alerts/suppressions/${id}`,
    method: 'DELETE',
  });
}

export async function fetchAlertFixTasks(status?: string): Promise<AlertFixTasksResponse> {
  const params: Record<string, string> = {};
  if (status) params.status = status;
  return customFetch<AlertFixTasksResponse>({
    url: '/alerts/fix-tasks',
    method: 'GET',
    params: Object.keys(params).length ? params : undefined,
  });
}

export async function completeAlertFixTask(
  taskId: number,
  result: string,
): Promise<{ status: string }> {
  return customFetch<{ status: string }>({
    url: `/alerts/fix-tasks/${taskId}/complete`,
    method: 'POST',
    data: { result },
  });
}
