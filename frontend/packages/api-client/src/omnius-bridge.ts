import { getApiKey } from './base';
import type {
  CreateTaskRequest,
  OmniusConfigEntry,
  OmniusTenant,
  OmniusTenantStatus,
  OperatorTask,
  SyncTriggerResponse,
  UpdateTaskRequest,
} from './omnius-bridge-types';
import type { AuditLogEntry } from './admin-types';

declare const process: { env: Record<string, string | undefined> } | undefined;

const TENANT_URLS: Record<OmniusTenant, string> = {
  reh:
    typeof process !== 'undefined'
      ? (process.env.NEXT_PUBLIC_OMNIUS_REH_URL ?? 'http://127.0.0.1:8100')
      : 'http://127.0.0.1:8100',
  ref:
    typeof process !== 'undefined'
      ? (process.env.NEXT_PUBLIC_OMNIUS_REF_URL ?? 'http://127.0.0.1:8200')
      : 'http://127.0.0.1:8200',
};

async function tenantFetch<T>(
  tenant: OmniusTenant,
  config: {
    url: string;
    method: string;
    params?: Record<string, string>;
    data?: unknown;
    signal?: AbortSignal;
  },
): Promise<T> {
  const baseUrl = TENANT_URLS[tenant];
  const url = new URL(`${baseUrl}${config.url}`);

  if (config.params) {
    for (const [key, value] of Object.entries(config.params)) {
      if (value !== undefined && value !== null) {
        url.searchParams.set(key, String(value));
      }
    }
  }

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  const key = getApiKey();
  if (key) {
    headers['X-API-Key'] = key;
  }

  const response = await fetch(url.toString(), {
    method: config.method,
    headers,
    body: config.data ? JSON.stringify(config.data) : undefined,
    signal: config.signal,
  });

  if (!response.ok) {
    throw new Error(`Omnius API error: ${response.status} ${response.statusText}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

// ── Tenant Status ──────────────────────────────────────────────────────────

export async function getTenantStatus(
  tenant: OmniusTenant,
  signal?: AbortSignal,
): Promise<OmniusTenantStatus> {
  return tenantFetch<OmniusTenantStatus>(tenant, {
    url: '/api/v1/status',
    method: 'GET',
    signal,
  });
}

// ── Operator Tasks ─────────────────────────────────────────────────────────

export async function getOperatorTasks(
  tenant: OmniusTenant,
  signal?: AbortSignal,
): Promise<OperatorTask[]> {
  return tenantFetch<OperatorTask[]>(tenant, {
    url: '/api/v1/tasks',
    method: 'GET',
    signal,
  });
}

export async function createOperatorTask(
  tenant: OmniusTenant,
  data: CreateTaskRequest,
): Promise<OperatorTask> {
  return tenantFetch<OperatorTask>(tenant, {
    url: '/api/v1/tasks',
    method: 'POST',
    data,
  });
}

export async function updateOperatorTask(
  tenant: OmniusTenant,
  taskId: number,
  data: UpdateTaskRequest,
): Promise<OperatorTask> {
  return tenantFetch<OperatorTask>(tenant, {
    url: `/api/v1/tasks/${taskId}`,
    method: 'PATCH',
    data,
  });
}

// ── Tenant Audit Log ───────────────────────────────────────────────────────

export async function getTenantAuditLog(
  tenant: OmniusTenant,
  signal?: AbortSignal,
): Promise<AuditLogEntry[]> {
  return tenantFetch<AuditLogEntry[]>(tenant, {
    url: '/api/v1/admin/audit',
    method: 'GET',
    signal,
  });
}

// ── Tenant Config ──────────────────────────────────────────────────────────

export async function getTenantConfig(
  tenant: OmniusTenant,
  signal?: AbortSignal,
): Promise<OmniusConfigEntry[]> {
  return tenantFetch<OmniusConfigEntry[]>(tenant, {
    url: '/api/v1/admin/config',
    method: 'GET',
    signal,
  });
}

export async function pushTenantConfig(
  tenant: OmniusTenant,
  key: string,
  value: unknown,
): Promise<OmniusConfigEntry> {
  return tenantFetch<OmniusConfigEntry>(tenant, {
    url: '/api/v1/admin/config',
    method: 'POST',
    data: { key, value },
  });
}

// ── Tenant Sync ────────────────────────────────────────────────────────────

export async function triggerTenantSync(
  tenant: OmniusTenant,
  source: string,
): Promise<SyncTriggerResponse> {
  return tenantFetch<SyncTriggerResponse>(tenant, {
    url: '/api/v1/sync/trigger',
    method: 'POST',
    data: { source },
  });
}
