import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getFinanceDashboard,
  addFinanceMetric,
  addBudget,
  estimateCost,
  getCostBudget,
  getGoals,
  getGoalDetail,
  createGoal,
  updateGoalProgress,
} from '@gilbertus/api-client';
import type {
  AddMetricRequest,
  AddBudgetRequest,
  CreateGoalRequest,
  UpdateGoalProgressRequest,
} from '@gilbertus/api-client';

// ── Query hooks ─────────────────────────────────────────────────────────────

export function useFinanceDashboard(company?: string) {
  return useQuery({
    queryKey: ['finance-dashboard', company],
    queryFn: () => getFinanceDashboard({ company }),
    staleTime: 60_000,
  });
}

export function useCostBudget() {
  return useQuery({
    queryKey: ['cost-budget'],
    queryFn: getCostBudget,
    staleTime: 30_000,
  });
}

export function useGoals() {
  return useQuery({
    queryKey: ['goals'],
    queryFn: getGoals,
  });
}

export function useGoalDetail(goalId: number) {
  return useQuery({
    queryKey: ['goal-detail', goalId],
    queryFn: () => getGoalDetail(goalId),
    enabled: !!goalId,
  });
}

// ── Mutation hooks ──────────────────────────────────────────────────────────

export function useAddFinanceMetric() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: AddMetricRequest) => addFinanceMetric(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['finance-dashboard'] }),
  });
}

export function useAddBudget() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: AddBudgetRequest) => addBudget(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['finance-dashboard'] }),
  });
}

export function useEstimateCost() {
  return useMutation({
    mutationFn: (data: { description: string }) => estimateCost(data),
  });
}

export function useCreateGoal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateGoalRequest) => createGoal(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['goals'] }),
  });
}

export function useUpdateGoalProgress() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: { goalId: number; data: UpdateGoalProgressRequest }) =>
      updateGoalProgress(params.goalId, params.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['goals'] });
      qc.invalidateQueries({ queryKey: ['goal-detail'] });
    },
  });
}
