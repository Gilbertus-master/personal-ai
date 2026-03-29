import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchComplianceDashboard,
  fetchComplianceAreas,
  fetchComplianceArea,
  fetchMatters,
  fetchMatter,
  createMatter,
  researchMatter,
  advanceMatter,
  generateMatterReport,
  generateCommPlan,
  executeComm,
  fetchObligations,
  fetchOverdueObligations,
  createObligation,
  fulfillObligation,
  fetchDeadlines,
  fetchOverdueDeadlines,
  fetchDocuments,
  fetchStaleDocuments,
  generateDocument,
  approveDocument,
  signDocument,
  fetchTrainings,
  fetchTrainingStatus,
  createTraining,
  completeTraining,
  fetchRisks,
  fetchRiskHeatmap,
  fetchRaci,
  upsertRaci,
  fetchDailyReport,
  fetchWeeklyReport,
  fetchAreaReport,
  scanRegulatory,
} from '@gilbertus/api-client';
import type {
  CreateMatterRequest,
  CreateObligationRequest,
  CreateTrainingRequest,
  CreateRaciRequest,
  GenerateDocRequest,
} from '@gilbertus/api-client';
import { useComplianceStore } from '../stores/compliance-store';

// ── Dashboard & Areas ───────────────────────────────────────────────────────

export function useComplianceDashboard() {
  return useQuery({
    queryKey: ['compliance', 'dashboard'],
    queryFn: fetchComplianceDashboard,
  });
}

export function useComplianceAreas() {
  return useQuery({
    queryKey: ['compliance', 'areas'],
    queryFn: fetchComplianceAreas,
  });
}

export function useComplianceArea(code: string) {
  return useQuery({
    queryKey: ['compliance', 'areas', code],
    queryFn: () => fetchComplianceArea(code),
    enabled: !!code,
  });
}

// ── Matters ─────────────────────────────────────────────────────────────────

export function useMatters() {
  const { matterStatus, matterArea, matterPriority } = useComplianceStore();
  return useQuery({
    queryKey: ['compliance', 'matters', matterStatus, matterArea, matterPriority],
    queryFn: () =>
      fetchMatters({
        status: matterStatus ?? undefined,
        area_code: matterArea ?? undefined,
        priority: matterPriority ?? undefined,
      }),
  });
}

export function useMatter(id: number) {
  return useQuery({
    queryKey: ['compliance', 'matters', id],
    queryFn: () => fetchMatter(id),
    enabled: !!id,
  });
}

export function useCreateMatter() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateMatterRequest) => createMatter(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['compliance', 'matters'] }),
  });
}

export function useResearchMatter() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ matterId, query }: { matterId: number; query?: string }) =>
      researchMatter(matterId, query),
    onSuccess: (_data, { matterId }) =>
      qc.invalidateQueries({ queryKey: ['compliance', 'matters', matterId] }),
  });
}

export function useAdvanceMatter() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ matterId, forcePhase }: { matterId: number; forcePhase?: string }) =>
      advanceMatter(matterId, forcePhase),
    onSuccess: (_data, { matterId }) =>
      qc.invalidateQueries({ queryKey: ['compliance', 'matters', matterId] }),
  });
}

export function useMatterReport() {
  return useMutation({
    mutationFn: (matterId: number) => generateMatterReport(matterId),
  });
}

export function useCommPlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (matterId: number) => generateCommPlan(matterId),
    onSuccess: (_data, matterId) =>
      qc.invalidateQueries({ queryKey: ['compliance', 'matters', matterId] }),
  });
}

export function useExecuteComm() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (matterId: number) => executeComm(matterId),
    onSuccess: (_data, matterId) =>
      qc.invalidateQueries({ queryKey: ['compliance', 'matters', matterId] }),
  });
}

// ── Obligations ─────────────────────────────────────────────────────────────

export function useObligations() {
  const { obligationArea, obligationStatus } = useComplianceStore();
  return useQuery({
    queryKey: ['compliance', 'obligations', obligationArea, obligationStatus],
    queryFn: () =>
      fetchObligations({
        area_code: obligationArea ?? undefined,
        status: obligationStatus ?? undefined,
      }),
  });
}

export function useOverdueObligations() {
  return useQuery({
    queryKey: ['compliance', 'obligations', 'overdue'],
    queryFn: fetchOverdueObligations,
  });
}

export function useCreateObligation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateObligationRequest) => createObligation(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['compliance', 'obligations'] }),
  });
}

export function useFulfillObligation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, evidence }: { id: number; evidence?: string }) =>
      fulfillObligation(id, evidence),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['compliance', 'obligations'] }),
  });
}

// ── Deadlines ───────────────────────────────────────────────────────────────

export function useDeadlines() {
  const { daysAhead, deadlineArea } = useComplianceStore();
  return useQuery({
    queryKey: ['compliance', 'deadlines', daysAhead, deadlineArea],
    queryFn: () =>
      fetchDeadlines({
        days_ahead: daysAhead,
        area_code: deadlineArea ?? undefined,
      }),
  });
}

export function useOverdueDeadlines() {
  return useQuery({
    queryKey: ['compliance', 'deadlines', 'overdue'],
    queryFn: fetchOverdueDeadlines,
  });
}

// ── Documents ───────────────────────────────────────────────────────────────

export function useDocuments() {
  const { docArea, docType, docStatus } = useComplianceStore();
  return useQuery({
    queryKey: ['compliance', 'documents', docArea, docType, docStatus],
    queryFn: () =>
      fetchDocuments({
        area_code: docArea ?? undefined,
        doc_type: docType ?? undefined,
        status: docStatus ?? undefined,
      }),
  });
}

export function useStaleDocuments() {
  return useQuery({
    queryKey: ['compliance', 'documents', 'stale'],
    queryFn: () => fetchStaleDocuments(),
  });
}

export function useGenerateDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: GenerateDocRequest) => generateDocument(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['compliance', 'documents'] }),
  });
}

export function useApproveDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, approvedBy }: { id: number; approvedBy?: string }) =>
      approveDocument(id, approvedBy),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['compliance', 'documents'] }),
  });
}

export function useSignDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, signerName }: { id: number; signerName: string }) =>
      signDocument(id, signerName),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['compliance', 'documents'] }),
  });
}

// ── Trainings ───────────────────────────────────────────────────────────────

export function useTrainings() {
  const { trainingArea, trainingStatus } = useComplianceStore();
  return useQuery({
    queryKey: ['compliance', 'trainings', trainingArea, trainingStatus],
    queryFn: () =>
      fetchTrainings({
        area_code: trainingArea ?? undefined,
        status: trainingStatus ?? undefined,
      }),
  });
}

export function useTrainingStatus(id: number) {
  return useQuery({
    queryKey: ['compliance', 'trainings', id, 'status'],
    queryFn: () => fetchTrainingStatus(id),
    enabled: !!id,
  });
}

export function useCreateTraining() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateTrainingRequest) => createTraining(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['compliance', 'trainings'] }),
  });
}

export function useCompleteTraining() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      trainingId,
      personId,
      score,
    }: {
      trainingId: number;
      personId: number;
      score?: number;
    }) => completeTraining(trainingId, personId, score),
    onSuccess: (_data, { trainingId }) =>
      qc.invalidateQueries({ queryKey: ['compliance', 'trainings', trainingId, 'status'] }),
  });
}

// ── Risks ───────────────────────────────────────────────────────────────────

export function useRisks() {
  const { riskArea, riskStatus } = useComplianceStore();
  return useQuery({
    queryKey: ['compliance', 'risks', riskArea, riskStatus],
    queryFn: () =>
      fetchRisks({
        area_code: riskArea ?? undefined,
        status: riskStatus ?? undefined,
      }),
  });
}

export function useRiskHeatmap() {
  return useQuery({
    queryKey: ['compliance', 'risks', 'heatmap'],
    queryFn: fetchRiskHeatmap,
  });
}

// ── RACI ────────────────────────────────────────────────────────────────────

export function useRaci() {
  const { raciArea } = useComplianceStore();
  return useQuery({
    queryKey: ['compliance', 'raci', raciArea],
    queryFn: () => fetchRaci({ area_code: raciArea ?? undefined }),
  });
}

export function useUpsertRaci() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateRaciRequest) => upsertRaci(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['compliance', 'raci'] }),
  });
}

// ── Reports ─────────────────────────────────────────────────────────────────

export function useDailyReport() {
  return useQuery({
    queryKey: ['compliance', 'report', 'daily'],
    queryFn: fetchDailyReport,
  });
}

export function useWeeklyReport() {
  return useQuery({
    queryKey: ['compliance', 'report', 'weekly'],
    queryFn: fetchWeeklyReport,
  });
}

export function useAreaReport(code: string) {
  return useQuery({
    queryKey: ['compliance', 'report', 'area', code],
    queryFn: () => fetchAreaReport(code),
    enabled: !!code,
  });
}

// ── Regulatory Scan ─────────────────────────────────────────────────────────

export function useScanRegulatory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (hours?: number) => scanRegulatory(hours),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['compliance', 'matters'] });
      qc.invalidateQueries({ queryKey: ['compliance', 'dashboard'] });
    },
  });
}
