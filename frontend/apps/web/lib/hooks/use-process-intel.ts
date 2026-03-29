import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getProcessDashboard,
  getBusinessLines,
  discoverBusinessLines,
  getProcesses,
  mineProcesses,
  getApps,
  scanApps,
  scanAppsDeep,
  getAppAnalysis,
  getAppDetail,
  getAppCosts,
  getAppRanking,
  getFlows,
  mapFlows,
  getOptimizations,
  generateOptimizations,
  analyzeEmployee,
  analyzeAllEmployees,
  getWorkProfile,
  getAutomationOverview,
  getAutomationRoadmap,
  discoverTech,
  getTechRadar,
  getTechSolution,
  getTechRoadmap,
  getTechAlignment,
  updateTechStatus,
} from '@gilbertus/api-client';

// ── Query hooks ─────────────────────────────────────────────────────────────

export function useProcessDashboard() {
  return useQuery({
    queryKey: ['process-dashboard'],
    queryFn: getProcessDashboard,
    staleTime: 60_000,
  });
}

export function useBusinessLines() {
  return useQuery({
    queryKey: ['business-lines'],
    queryFn: getBusinessLines,
  });
}

export function useProcesses(type?: string) {
  return useQuery({
    queryKey: ['processes', type],
    queryFn: () => getProcesses({ process_type: type }),
  });
}

export function useApps() {
  return useQuery({
    queryKey: ['apps'],
    queryFn: getApps,
  });
}

export function useAppAnalysis() {
  return useQuery({
    queryKey: ['app-analysis'],
    queryFn: getAppAnalysis,
  });
}

export function useAppDetail(appId: number) {
  return useQuery({
    queryKey: ['app-detail', appId],
    queryFn: () => getAppDetail(appId),
    enabled: !!appId,
  });
}

export function useAppRanking() {
  return useQuery({
    queryKey: ['app-ranking'],
    queryFn: getAppRanking,
  });
}

export function useFlows() {
  return useQuery({
    queryKey: ['flows'],
    queryFn: getFlows,
  });
}

export function useOptimizations() {
  return useQuery({
    queryKey: ['optimizations'],
    queryFn: getOptimizations,
  });
}

export function useAutomationOverview() {
  return useQuery({
    queryKey: ['automation-overview'],
    queryFn: getAutomationOverview,
  });
}

export function useAutomationRoadmap() {
  return useQuery({
    queryKey: ['automation-roadmap'],
    queryFn: getAutomationRoadmap,
  });
}

export function useWorkProfile(slug: string) {
  return useQuery({
    queryKey: ['work-profile', slug],
    queryFn: () => getWorkProfile(slug),
    enabled: !!slug,
  });
}

export function useTechRadar() {
  return useQuery({
    queryKey: ['tech-radar'],
    queryFn: getTechRadar,
  });
}

export function useTechSolution(id: number) {
  return useQuery({
    queryKey: ['tech-solution', id],
    queryFn: () => getTechSolution(id),
    enabled: !!id,
  });
}

export function useTechRoadmap() {
  return useQuery({
    queryKey: ['tech-roadmap'],
    queryFn: getTechRoadmap,
  });
}

export function useTechAlignment() {
  return useQuery({
    queryKey: ['tech-alignment'],
    queryFn: getTechAlignment,
  });
}

// ── Mutation hooks ──────────────────────────────────────────────────────────

export function useDiscoverBusinessLines() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: discoverBusinessLines,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['business-lines'] });
      qc.invalidateQueries({ queryKey: ['process-dashboard'] });
    },
  });
}

export function useMineProcesses() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: mineProcesses,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['processes'] });
      qc.invalidateQueries({ queryKey: ['process-dashboard'] });
    },
  });
}

export function useScanApps() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: scanApps,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['apps'] });
      qc.invalidateQueries({ queryKey: ['process-dashboard'] });
    },
  });
}

export function useScanAppsDeep() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: scanAppsDeep,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['apps'] });
      qc.invalidateQueries({ queryKey: ['app-analysis'] });
      qc.invalidateQueries({ queryKey: ['process-dashboard'] });
    },
  });
}

export function useAppCosts() {
  return useMutation({
    mutationFn: getAppCosts,
  });
}

export function useMapFlows() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: mapFlows,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['flows'] });
    },
  });
}

export function useGenerateOptimizations() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: generateOptimizations,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['optimizations'] });
      qc.invalidateQueries({ queryKey: ['process-dashboard'] });
    },
  });
}

export function useAnalyzeEmployee() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (personSlug: string) => analyzeEmployee(personSlug),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['work-profile'] });
      qc.invalidateQueries({ queryKey: ['automation-overview'] });
    },
  });
}

export function useAnalyzeAllEmployees() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params?: { organization?: string }) => analyzeAllEmployees(params),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['automation-overview'] });
      qc.invalidateQueries({ queryKey: ['automation-roadmap'] });
    },
  });
}

export function useDiscoverTech() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: discoverTech,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tech-radar'] });
      qc.invalidateQueries({ queryKey: ['tech-roadmap'] });
    },
  });
}

export function useUpdateTechStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: { solutionId: number; status: string }) =>
      updateTechStatus(params.solutionId, { status: params.status }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tech-radar'] });
      qc.invalidateQueries({ queryKey: ['tech-solution'] });
    },
  });
}
