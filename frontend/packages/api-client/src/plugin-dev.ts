import { customFetch } from './base';
import type {
  PluginProposal,
  PluginApproveRequest,
  PluginRejectRequest,
  PluginApproveResponse,
} from './plugin-dev-types';

// ── Plugin Proposals (Gilbertus API) ──────────────────────────────────────

export async function getPluginProposals(
  params?: { status?: string; tenant?: string },
  signal?: AbortSignal,
): Promise<PluginProposal[]> {
  const queryParams: Record<string, string> = {};
  if (params?.status) queryParams.status = params.status;
  if (params?.tenant) queryParams.tenant = params.tenant;
  return customFetch<PluginProposal[]>({
    url: '/plugins/proposals',
    method: 'GET',
    params: Object.keys(queryParams).length ? queryParams : undefined,
    signal,
  });
}

export async function getPluginReview(
  proposalId: number,
  tenant: string,
  signal?: AbortSignal,
): Promise<PluginProposal> {
  return customFetch<PluginProposal>({
    url: `/plugins/proposals/${proposalId}/review`,
    method: 'GET',
    params: { tenant },
    signal,
  });
}

export async function approvePlugin(
  proposalId: number,
  data: PluginApproveRequest,
): Promise<PluginApproveResponse> {
  return customFetch<PluginApproveResponse>({
    url: `/plugins/proposals/${proposalId}/approve`,
    method: 'POST',
    data,
  });
}

export async function rejectPlugin(
  proposalId: number,
  data: PluginRejectRequest,
): Promise<PluginApproveResponse> {
  return customFetch<PluginApproveResponse>({
    url: `/plugins/proposals/${proposalId}/reject`,
    method: 'POST',
    data,
  });
}
