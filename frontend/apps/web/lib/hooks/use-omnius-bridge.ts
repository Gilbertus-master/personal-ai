import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getTenantStatus,
  getOperatorTasks,
  createOperatorTask,
  updateOperatorTask,
  getTenantAuditLog,
  getTenantConfig,
  pushTenantConfig,
  triggerTenantSync,
} from '@gilbertus/api-client';
import type {
  OmniusTenant,
  CreateTaskRequest,
  UpdateTaskRequest,
} from '@gilbertus/api-client';

// ── Tenant Status ──────────────────────────────────────────────────────────

export function useTenantStatus(tenant: OmniusTenant) {
  return useQuery({
    queryKey: ['tenant-status', tenant],
    queryFn: ({ signal }) => getTenantStatus(tenant, signal),
    staleTime: 30_000,
  });
}

export function useBothTenantsStatus() {
  const reh = useTenantStatus('reh');
  const ref = useTenantStatus('ref');
  return { reh, ref, isLoading: reh.isLoading || ref.isLoading };
}

// ── Operator Tasks ─────────────────────────────────────────────────────────

export function useOperatorTasks(tenant: OmniusTenant) {
  return useQuery({
    queryKey: ['operator-tasks', tenant],
    queryFn: ({ signal }) => getOperatorTasks(tenant, signal),
    staleTime: 30_000,
  });
}

export function useCreateOperatorTask(tenant: OmniusTenant) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateTaskRequest) => createOperatorTask(tenant, data),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ['operator-tasks', tenant] }),
  });
}

export function useUpdateOperatorTask(tenant: OmniusTenant) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: { taskId: number; data: UpdateTaskRequest }) =>
      updateOperatorTask(tenant, params.taskId, params.data),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ['operator-tasks', tenant] }),
  });
}

// ── Tenant Audit Log ───────────────────────────────────────────────────────

export function useTenantAuditLog(tenant: OmniusTenant) {
  return useQuery({
    queryKey: ['tenant-audit', tenant],
    queryFn: ({ signal }) => getTenantAuditLog(tenant, signal),
    staleTime: 30_000,
  });
}

// ── Tenant Config ──────────────────────────────────────────────────────────

export function useTenantConfig(tenant: OmniusTenant) {
  return useQuery({
    queryKey: ['tenant-config', tenant],
    queryFn: ({ signal }) => getTenantConfig(tenant, signal),
    staleTime: 60_000,
  });
}

export function usePushTenantConfig(tenant: OmniusTenant) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { key: string; value: unknown }) =>
      pushTenantConfig(tenant, data.key, data.value),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ['tenant-config', tenant] }),
  });
}

// ── Tenant Sync ────────────────────────────────────────────────────────────

export function useTriggerSync(tenant: OmniusTenant) {
  return useMutation({
    mutationFn: (source: string) => triggerTenantSync(tenant, source),
  });
}
