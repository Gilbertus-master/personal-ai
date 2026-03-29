import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getPluginProposals,
  getPluginReview,
  approvePlugin,
  rejectPlugin,
} from '@gilbertus/api-client';
import type { PluginApproveRequest, PluginRejectRequest } from '@gilbertus/api-client';

// ── Plugin Proposals ──────────────────────────────────────────────────────

export function usePluginProposals(params?: { tenant?: string; status?: string }) {
  return useQuery({
    queryKey: ['plugin-proposals', params],
    queryFn: ({ signal }) => getPluginProposals(params, signal),
    staleTime: 30_000,
  });
}

export function usePluginReview(proposalId: number | null, tenant: string) {
  return useQuery({
    queryKey: ['plugin-review', proposalId, tenant],
    queryFn: ({ signal }) => getPluginReview(proposalId!, tenant, signal),
    enabled: proposalId != null && !!tenant,
    staleTime: 60_000,
  });
}

export function useApprovePlugin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: { proposalId: number; data: PluginApproveRequest }) =>
      approvePlugin(params.proposalId, params.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['plugin-proposals'] });
    },
  });
}

export function useRejectPlugin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: { proposalId: number; data: PluginRejectRequest }) =>
      rejectPlugin(params.proposalId, params.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['plugin-proposals'] });
    },
  });
}
