import { customFetch } from './base';
import type {
  AdminUser,
  AuditLogEntry,
  AutofixerDashboard,
  CodeFinding,
  CronListResponse,
  CronSummary,
  CronToggleResponse,
  CreateUserRequest,
  CreateUserResponse,
  RoleDefinition,
  SystemStatus,
} from './admin-types';

// ── Crons (Gilbertus API) ──────────────────────────────────────────────────

export async function getCrons(
  params?: { user?: string; category?: string },
  signal?: AbortSignal,
): Promise<CronListResponse> {
  const queryParams: Record<string, string> = {};
  if (params?.user) queryParams.user = params.user;
  if (params?.category) queryParams.category = params.category;
  return customFetch<CronListResponse>({
    url: '/crons',
    method: 'GET',
    params: Object.keys(queryParams).length ? queryParams : undefined,
    signal,
  });
}

export async function getCronSummary(
  signal?: AbortSignal,
): Promise<CronSummary> {
  return customFetch<CronSummary>({
    url: '/crons/summary',
    method: 'GET',
    signal,
  });
}

export async function enableCron(
  jobName: string,
  user: string = 'sebastian',
): Promise<CronToggleResponse> {
  return customFetch<CronToggleResponse>({
    url: `/crons/${encodeURIComponent(jobName)}/enable`,
    method: 'POST',
    params: { user },
  });
}

export async function disableCron(
  jobName: string,
  user: string = 'sebastian',
): Promise<CronToggleResponse> {
  return customFetch<CronToggleResponse>({
    url: `/crons/${encodeURIComponent(jobName)}/disable`,
    method: 'POST',
    params: { user },
  });
}

// ── System Status (Gilbertus API) ──────────────────────────────────────────

export async function getSystemStatus(
  signal?: AbortSignal,
): Promise<SystemStatus> {
  return customFetch<SystemStatus>({
    url: '/status',
    method: 'GET',
    signal,
  });
}

// ── Code Findings (Gilbertus API) ──────────────────────────────────────────

export async function getCodeFindings(
  signal?: AbortSignal,
): Promise<CodeFinding[]> {
  return customFetch<CodeFinding[]>({
    url: '/code-fixes/manual-queue',
    method: 'GET',
    signal,
  });
}

// ── Users (Omnius API) ─────────────────────────────────────────────────────

export async function getAdminUsers(
  signal?: AbortSignal,
): Promise<AdminUser[]> {
  return customFetch<AdminUser[]>({
    url: '/api/v1/admin/users',
    method: 'GET',
    signal,
  });
}

export async function createAdminUser(
  data: CreateUserRequest,
): Promise<CreateUserResponse> {
  return customFetch<CreateUserResponse>({
    url: '/api/v1/admin/users',
    method: 'POST',
    data,
  });
}

// ── Audit Log (Omnius API) ─────────────────────────────────────────────────

export async function getAuditLog(
  signal?: AbortSignal,
): Promise<AuditLogEntry[]> {
  return customFetch<AuditLogEntry[]>({
    url: '/api/v1/admin/audit',
    method: 'GET',
    signal,
  });
}

// ── Roles (Gilbertus API) ─────────────────────────────────────────────────

export async function getAdminRoles(
  signal?: AbortSignal,
): Promise<RoleDefinition[]> {
  return customFetch<RoleDefinition[]>({
    url: '/admin/roles',
    method: 'GET',
    signal,
  });
}

// ── Autofixer Dashboard (Gilbertus API) ───────────────────────────────────

export async function getAutofixerDashboard(
  signal?: AbortSignal,
): Promise<AutofixerDashboard> {
  return customFetch<AutofixerDashboard>({
    url: '/autofixers/dashboard',
    method: 'GET',
    signal,
  });
}
