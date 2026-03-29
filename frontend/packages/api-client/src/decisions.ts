import { customFetch } from './base';
import type {
  DecisionCreate,
  DecisionIntelligenceResponse,
  DecisionResponse,
  DecisionsListResponse,
  OutcomeCreate,
  OutcomeResponse,
  PatternsResponse,
} from './decisions-types';

export async function fetchDecisions(params?: {
  area?: string;
  limit?: number;
}): Promise<DecisionsListResponse> {
  const queryParams: Record<string, string> = {};
  if (params?.area) queryParams.area = params.area;
  if (params?.limit !== undefined) queryParams.limit = String(params.limit);
  return customFetch<DecisionsListResponse>({
    url: '/decisions/decisions',
    method: 'GET',
    params: Object.keys(queryParams).length ? queryParams : undefined,
  });
}

export async function createDecision(data: DecisionCreate): Promise<DecisionResponse> {
  return customFetch<DecisionResponse>({
    url: '/decisions/decision',
    method: 'POST',
    data,
  });
}

export async function addOutcome(
  decisionId: number,
  data: OutcomeCreate,
): Promise<OutcomeResponse> {
  return customFetch<OutcomeResponse>({
    url: `/decisions/decision/${decisionId}/outcome`,
    method: 'POST',
    data,
  });
}

export async function fetchDecisionPatterns(): Promise<PatternsResponse> {
  return customFetch<PatternsResponse>({
    url: '/decisions/decisions/patterns',
    method: 'GET',
  });
}

export async function fetchDecisionIntelligence(params?: {
  months?: number;
}): Promise<DecisionIntelligenceResponse> {
  const queryParams: Record<string, string> = {};
  if (params?.months !== undefined) queryParams.months = String(params.months);
  return customFetch<DecisionIntelligenceResponse>({
    url: '/decision-intelligence',
    method: 'GET',
    params: Object.keys(queryParams).length ? queryParams : undefined,
  });
}

export async function runDecisionIntelligence(): Promise<DecisionIntelligenceResponse> {
  return customFetch<DecisionIntelligenceResponse>({
    url: '/decision-intelligence/run',
    method: 'POST',
  });
}
