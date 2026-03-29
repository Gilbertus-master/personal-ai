import { customFetch } from './base';
import type {
  Opportunity,
  OpportunityScanResult,
  InefficiencyReport,
  CorrelationRequest,
  CorrelationResult,
  Scenario,
  ScenarioAnalysis,
  ScenarioCreateParams,
  PredictiveAlerts,
  OrgHealth,
  OrgHealthAssessment,
} from './intelligence-types';

export async function fetchOpportunities(params?: {
  status?: string;
  limit?: number;
}): Promise<Opportunity[]> {
  const queryParams: Record<string, string> = {};
  if (params?.status) queryParams.status = params.status;
  if (params?.limit) queryParams.limit = String(params.limit);
  return customFetch<Opportunity[]>({
    url: '/opportunities',
    method: 'GET',
    params: Object.keys(queryParams).length ? queryParams : undefined,
  });
}

export async function scanOpportunities(hours?: number): Promise<OpportunityScanResult> {
  const queryParams: Record<string, string> = {};
  if (hours !== undefined) queryParams.hours = String(hours);
  return customFetch<OpportunityScanResult>({
    url: '/opportunities/scan',
    method: 'POST',
    params: Object.keys(queryParams).length ? queryParams : undefined,
  });
}

export async function fetchInefficiency(): Promise<InefficiencyReport> {
  return customFetch<InefficiencyReport>({ url: '/inefficiency', method: 'GET' });
}

export async function postCorrelation(data: CorrelationRequest): Promise<CorrelationResult> {
  return customFetch<CorrelationResult>({
    url: '/correlate',
    method: 'POST',
    data,
  });
}

export async function fetchScenarios(params?: {
  status?: string;
  limit?: number;
}): Promise<Scenario[]> {
  const queryParams: Record<string, string> = {};
  if (params?.status) queryParams.status = params.status;
  if (params?.limit) queryParams.limit = String(params.limit);
  return customFetch<Scenario[]>({
    url: '/scenarios',
    method: 'GET',
    params: Object.keys(queryParams).length ? queryParams : undefined,
  });
}

export async function createScenario(
  params: ScenarioCreateParams,
): Promise<{ id: number; title: string; status: string }> {
  const queryParams: Record<string, string> = {
    title: params.title,
    description: params.description,
  };
  if (params.scenario_type) queryParams.scenario_type = params.scenario_type;
  return customFetch<{ id: number; title: string; status: string }>({
    url: '/scenarios',
    method: 'POST',
    params: queryParams,
  });
}

export async function analyzeScenario(scenarioId: number): Promise<ScenarioAnalysis> {
  return customFetch<ScenarioAnalysis>({
    url: `/scenarios/${scenarioId}/analyze`,
    method: 'POST',
  });
}

export async function compareScenarios(ids: number[]): Promise<unknown> {
  return customFetch<unknown>({
    url: '/scenarios/compare',
    method: 'GET',
    params: { ids: ids.join(',') },
  });
}

export async function autoScanScenarios(): Promise<unknown> {
  return customFetch<unknown>({ url: '/scenarios/auto-scan', method: 'POST' });
}

export async function fetchPredictions(): Promise<PredictiveAlerts> {
  return customFetch<PredictiveAlerts>({ url: '/predictions', method: 'GET' });
}

export async function fetchOrgHealth(weeks?: number): Promise<OrgHealth> {
  const queryParams: Record<string, string> = {};
  if (weeks !== undefined) queryParams.weeks = String(weeks);
  return customFetch<OrgHealth>({
    url: '/org-health',
    method: 'GET',
    params: Object.keys(queryParams).length ? queryParams : undefined,
  });
}

export async function assessOrgHealth(): Promise<OrgHealthAssessment> {
  return customFetch<OrgHealthAssessment>({ url: '/org-health/assess', method: 'POST' });
}
