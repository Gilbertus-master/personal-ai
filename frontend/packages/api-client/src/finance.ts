import { customFetch } from './base';
import type {
  AddBudgetRequest,
  AddMetricRequest,
  CostBudget,
  CostEstimate,
  CreateGoalRequest,
  FinanceDashboard,
  GoalsSummary,
  StrategicGoal,
  UpdateGoalProgressRequest,
} from './finance-types';

// ── Finance Dashboard ───────────────────────────────────────────────────────

export async function getFinanceDashboard(params?: {
  company?: string;
}): Promise<FinanceDashboard> {
  const queryParams: Record<string, string> = {};
  if (params?.company) queryParams.company = params.company;
  return customFetch<FinanceDashboard>({
    url: '/finance',
    method: 'GET',
    params: Object.keys(queryParams).length ? queryParams : undefined,
  });
}

export async function addFinanceMetric(
  data: AddMetricRequest,
): Promise<Record<string, unknown>> {
  return customFetch<Record<string, unknown>>({
    url: '/finance/metric',
    method: 'POST',
    data,
  });
}

export async function addBudget(
  data: AddBudgetRequest,
): Promise<Record<string, unknown>> {
  return customFetch<Record<string, unknown>>({
    url: '/finance/budget',
    method: 'POST',
    data,
  });
}

export async function estimateCost(data: {
  description: string;
}): Promise<CostEstimate> {
  return customFetch<CostEstimate>({
    url: '/finance/estimate-cost',
    method: 'POST',
    data,
  });
}

// ── Cost Budget ─────────────────────────────────────────────────────────────

export async function getCostBudget(): Promise<CostBudget> {
  return customFetch<CostBudget>({
    url: '/costs/budget',
    method: 'GET',
  });
}

// ── Strategic Goals ─────────────────────────────────────────────────────────

export async function getGoals(): Promise<GoalsSummary> {
  return customFetch<GoalsSummary>({
    url: '/goals',
    method: 'GET',
  });
}

export async function getGoalDetail(goalId: number): Promise<StrategicGoal> {
  return customFetch<StrategicGoal>({
    url: `/goals/${goalId}`,
    method: 'GET',
  });
}

export async function createGoal(
  data: CreateGoalRequest,
): Promise<StrategicGoal> {
  return customFetch<StrategicGoal>({
    url: '/goals',
    method: 'POST',
    data,
  });
}

export async function updateGoalProgress(
  goalId: number,
  data: UpdateGoalProgressRequest,
): Promise<Record<string, unknown>> {
  return customFetch<Record<string, unknown>>({
    url: `/goals/${goalId}/progress`,
    method: 'POST',
    data,
  });
}
