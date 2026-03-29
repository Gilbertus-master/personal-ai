import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchOpportunities,
  scanOpportunities,
  fetchInefficiency,
  postCorrelation,
  fetchScenarios,
  createScenario,
  analyzeScenario,
  compareScenarios,
  fetchPredictions,
  fetchOrgHealth,
  assessOrgHealth,
} from '@gilbertus/api-client';
import type { CorrelationRequest, ScenarioCreateParams } from '@gilbertus/api-client';
import { useIntelligenceStore } from '../stores/intelligence-store';

export function useOpportunities() {
  const { opportunityStatus } = useIntelligenceStore();
  return useQuery({
    queryKey: ['opportunities', opportunityStatus],
    queryFn: () => fetchOpportunities({ status: opportunityStatus ?? undefined }),
  });
}

export function useScanOpportunities() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (hours?: number) => scanOpportunities(hours),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['opportunities'] }),
  });
}

export function useInefficiency() {
  return useQuery({
    queryKey: ['inefficiency'],
    queryFn: fetchInefficiency,
  });
}

export function useCorrelation() {
  return useMutation({
    mutationFn: (data: CorrelationRequest) => postCorrelation(data),
  });
}

export function useScenarios() {
  const { scenarioStatus } = useIntelligenceStore();
  return useQuery({
    queryKey: ['scenarios', scenarioStatus],
    queryFn: () => fetchScenarios({ status: scenarioStatus ?? undefined }),
  });
}

export function useCreateScenario() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: ScenarioCreateParams) => createScenario(params),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['scenarios'] }),
  });
}

export function useAnalyzeScenario() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (scenarioId: number) => analyzeScenario(scenarioId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['scenarios'] }),
  });
}

export function useCompareScenarios(ids: number[]) {
  return useQuery({
    queryKey: ['scenarios', 'compare', ids],
    queryFn: () => compareScenarios(ids),
    enabled: ids.length >= 2,
  });
}

export function usePredictions() {
  return useQuery({
    queryKey: ['predictions'],
    queryFn: fetchPredictions,
    refetchInterval: 300_000, // 5 min
  });
}

export function useOrgHealth(weeks?: number) {
  return useQuery({
    queryKey: ['org-health', weeks],
    queryFn: () => fetchOrgHealth(weeks),
  });
}

export function useAssessOrgHealth() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: assessOrgHealth,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['org-health'] }),
  });
}
