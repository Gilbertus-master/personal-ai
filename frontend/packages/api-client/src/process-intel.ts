import { customFetch } from './base';
import type {
  ProcessIntelDashboard,
  BusinessLine,
  DiscoveredProcess,
  AppInventoryItem,
  AppDeepAnalysis,
  AppCostSummary,
  AppRankingItem,
  DataFlow,
  OptimizationsSummary,
  EmployeeWorkProfile,
  AutomationOverview,
  AutomationRoadmap,
  TechRadarResponse,
  TechSolution,
  TechRoadmap,
  TechAlignment,
  DiscoveryResult,
} from './process-intel-types';

export async function getProcessDashboard(): Promise<ProcessIntelDashboard> {
  return customFetch<ProcessIntelDashboard>({
    url: '/process-intel/dashboard',
    method: 'GET',
  });
}

export async function getBusinessLines(): Promise<{ business_lines: BusinessLine[] }> {
  return customFetch<{ business_lines: BusinessLine[] }>({
    url: '/process-intel/business-lines',
    method: 'GET',
  });
}

export async function discoverBusinessLines(): Promise<DiscoveryResult> {
  return customFetch<DiscoveryResult>({
    url: '/process-intel/discover',
    method: 'POST',
  });
}

export async function getProcesses(params?: {
  process_type?: string;
}): Promise<DiscoveredProcess[]> {
  const queryParams: Record<string, string> = {};
  if (params?.process_type) queryParams.process_type = params.process_type;
  return customFetch<DiscoveredProcess[]>({
    url: '/process-intel/processes',
    method: 'GET',
    params: Object.keys(queryParams).length ? queryParams : undefined,
  });
}

export async function mineProcesses(): Promise<DiscoveryResult> {
  return customFetch<DiscoveryResult>({
    url: '/process-intel/mine',
    method: 'POST',
  });
}

export async function getApps(): Promise<AppInventoryItem[]> {
  return customFetch<AppInventoryItem[]>({
    url: '/process-intel/apps',
    method: 'GET',
  });
}

export async function scanApps(): Promise<DiscoveryResult> {
  return customFetch<DiscoveryResult>({
    url: '/process-intel/scan-apps',
    method: 'POST',
  });
}

export async function scanAppsDeep(): Promise<DiscoveryResult> {
  return customFetch<DiscoveryResult>({
    url: '/process-intel/scan-apps-deep',
    method: 'POST',
  });
}

export async function getAppAnalysis(): Promise<AppDeepAnalysis[]> {
  return customFetch<AppDeepAnalysis[]>({
    url: '/process-intel/app-analysis',
    method: 'GET',
  });
}

export async function getAppDetail(appId: number): Promise<AppDeepAnalysis> {
  return customFetch<AppDeepAnalysis>({
    url: `/process-intel/app-analysis/${appId}`,
    method: 'GET',
  });
}

export async function getAppCosts(): Promise<AppCostSummary> {
  return customFetch<AppCostSummary>({
    url: '/process-intel/app-costs',
    method: 'POST',
  });
}

export async function getAppRanking(): Promise<AppRankingItem[]> {
  return customFetch<AppRankingItem[]>({
    url: '/process-intel/app-replacement-ranking',
    method: 'GET',
  });
}

export async function getFlows(): Promise<DataFlow[]> {
  return customFetch<DataFlow[]>({
    url: '/process-intel/flows',
    method: 'GET',
  });
}

export async function mapFlows(): Promise<DiscoveryResult> {
  return customFetch<DiscoveryResult>({
    url: '/process-intel/map-flows',
    method: 'POST',
  });
}

export async function getOptimizations(): Promise<OptimizationsSummary> {
  return customFetch<OptimizationsSummary>({
    url: '/process-intel/optimizations',
    method: 'GET',
  });
}

export async function generateOptimizations(): Promise<DiscoveryResult> {
  return customFetch<DiscoveryResult>({
    url: '/process-intel/plan',
    method: 'POST',
  });
}

export async function analyzeEmployee(personSlug: string): Promise<EmployeeWorkProfile> {
  return customFetch<EmployeeWorkProfile>({
    url: `/process-intel/analyze-employee/${personSlug}`,
    method: 'POST',
  });
}

export async function analyzeAllEmployees(params?: {
  organization?: string;
}): Promise<DiscoveryResult> {
  const queryParams: Record<string, string> = {};
  if (params?.organization) queryParams.organization = params.organization;
  return customFetch<DiscoveryResult>({
    url: '/process-intel/analyze-all-employees',
    method: 'POST',
    params: Object.keys(queryParams).length ? queryParams : undefined,
  });
}

export async function getWorkProfile(personSlug: string): Promise<EmployeeWorkProfile> {
  return customFetch<EmployeeWorkProfile>({
    url: `/process-intel/work-profile/${personSlug}`,
    method: 'GET',
  });
}

export async function getAutomationOverview(): Promise<AutomationOverview> {
  return customFetch<AutomationOverview>({
    url: '/process-intel/automation-overview',
    method: 'GET',
  });
}

export async function getAutomationRoadmap(): Promise<AutomationRoadmap> {
  return customFetch<AutomationRoadmap>({
    url: '/process-intel/automation-roadmap',
    method: 'GET',
  });
}

export async function discoverTech(): Promise<DiscoveryResult> {
  return customFetch<DiscoveryResult>({
    url: '/process-intel/discover-tech',
    method: 'POST',
  });
}

export async function getTechRadar(): Promise<TechRadarResponse> {
  return customFetch<TechRadarResponse>({
    url: '/process-intel/tech-radar',
    method: 'GET',
  });
}

export async function getTechSolution(solutionId: number): Promise<TechSolution> {
  return customFetch<TechSolution>({
    url: `/process-intel/tech-radar/${solutionId}`,
    method: 'GET',
  });
}

export async function getTechRoadmap(): Promise<TechRoadmap> {
  return customFetch<TechRoadmap>({
    url: '/process-intel/tech-roadmap',
    method: 'GET',
  });
}

export async function updateTechStatus(
  solutionId: number,
  params: { status: string },
): Promise<TechSolution> {
  const queryParams: Record<string, string> = { status: params.status };
  return customFetch<TechSolution>({
    url: `/process-intel/tech-solution/${solutionId}/status`,
    method: 'POST',
    params: queryParams,
  });
}

export async function getTechAlignment(): Promise<TechAlignment> {
  return customFetch<TechAlignment>({
    url: '/process-intel/tech-strategic-alignment',
    method: 'GET',
  });
}
