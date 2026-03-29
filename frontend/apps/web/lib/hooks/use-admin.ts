import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getCrons,
  getCronSummary,
  enableCron,
  disableCron,
  getSystemStatus,
  getCodeFindings,
  getAdminUsers,
  createAdminUser,
  getAuditLog,
  getCostBudget,
} from '@gilbertus/api-client';
import type { CreateUserRequest } from '@gilbertus/api-client';

// ── Crons ──────────────────────────────────────────────────────────────────

export function useCrons(params?: { user?: string; category?: string }) {
  return useQuery({
    queryKey: ['crons', params],
    queryFn: ({ signal }) => getCrons(params, signal),
    staleTime: 30_000,
  });
}

export function useCronSummary() {
  return useQuery({
    queryKey: ['cron-summary'],
    queryFn: ({ signal }) => getCronSummary(signal),
    staleTime: 30_000,
  });
}

export function useToggleCron() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: { jobName: string; enable: boolean; user?: string }) =>
      params.enable
        ? enableCron(params.jobName, params.user)
        : disableCron(params.jobName, params.user),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['crons'] });
      qc.invalidateQueries({ queryKey: ['cron-summary'] });
    },
  });
}

// ── System Status ──────────────────────────────────────────────────────────

export function useSystemStatus() {
  return useQuery({
    queryKey: ['system-status'],
    queryFn: ({ signal }) => getSystemStatus(signal),
    refetchInterval: 30_000,
  });
}

// ── Costs ──────────────────────────────────────────────────────────────────

export function useAdminCostBudget() {
  return useQuery({
    queryKey: ['cost-budget'],
    queryFn: () => getCostBudget(),
    staleTime: 30_000,
  });
}

// ── Code Findings ──────────────────────────────────────────────────────────

export function useCodeFindings() {
  return useQuery({
    queryKey: ['code-findings'],
    queryFn: ({ signal }) => getCodeFindings(signal),
    staleTime: 60_000,
  });
}

// ── Users ──────────────────────────────────────────────────────────────────

export function useAdminUsers() {
  return useQuery({
    queryKey: ['admin-users'],
    queryFn: ({ signal }) => getAdminUsers(signal),
    staleTime: 60_000,
  });
}

export function useCreateAdminUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateUserRequest) => createAdminUser(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-users'] }),
  });
}

// ── Audit ──────────────────────────────────────────────────────────────────

export function useAuditLog() {
  return useQuery({
    queryKey: ['audit-log'],
    queryFn: ({ signal }) => getAuditLog(signal),
    staleTime: 30_000,
  });
}
