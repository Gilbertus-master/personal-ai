import { customFetch } from './base';
import type {
  ComplianceArea,
  ComplianceDashboard,
  ComplianceDeadline,
  ComplianceDocument,
  ComplianceMatter,
  ComplianceObligation,
  ComplianceRisk,
  ComplianceTraining,
  CreateMatterRequest,
  CreateObligationRequest,
  CreateRaciRequest,
  CreateTrainingRequest,
  GenerateDocRequest,
  RaciEntry,
  RiskHeatmapResponse,
  ScanResult,
  TrainingRecord,
  WeeklyReportResponse,
} from './compliance-types';

// ── Dashboard & Areas ────────────────────────────────────────────────────────

export async function fetchComplianceDashboard(): Promise<ComplianceDashboard> {
  return customFetch<ComplianceDashboard>({ url: '/compliance/dashboard', method: 'GET' });
}

export async function fetchComplianceAreas(): Promise<{ areas: ComplianceArea[] }> {
  return customFetch<{ areas: ComplianceArea[] }>({ url: '/compliance/areas', method: 'GET' });
}

export async function fetchComplianceArea(code: string): Promise<ComplianceArea> {
  return customFetch<ComplianceArea>({ url: `/compliance/areas/${code}`, method: 'GET' });
}

// ── Matters ──────────────────────────────────────────────────────────────────

export async function fetchMatters(params?: {
  status?: string;
  area_code?: string;
  priority?: string;
  limit?: number;
}): Promise<{ matters: ComplianceMatter[] }> {
  const queryParams: Record<string, string> = {};
  if (params?.status) queryParams.status = params.status;
  if (params?.area_code) queryParams.area_code = params.area_code;
  if (params?.priority) queryParams.priority = params.priority;
  if (params?.limit) queryParams.limit = String(params.limit);
  return customFetch<{ matters: ComplianceMatter[] }>({
    url: '/compliance/matters',
    method: 'GET',
    params: Object.keys(queryParams).length ? queryParams : undefined,
  });
}

export async function createMatter(data: CreateMatterRequest): Promise<ComplianceMatter> {
  return customFetch<ComplianceMatter>({ url: '/compliance/matters', method: 'POST', data });
}

export async function fetchMatter(id: number): Promise<ComplianceMatter> {
  return customFetch<ComplianceMatter>({ url: `/compliance/matters/${id}`, method: 'GET' });
}

export async function researchMatter(
  id: number,
  query?: string,
): Promise<Record<string, unknown>> {
  return customFetch<Record<string, unknown>>({
    url: `/compliance/matters/${id}/research`,
    method: 'POST',
    data: query ? { query } : undefined,
  });
}

export async function advanceMatter(
  id: number,
  forcePhase?: string,
): Promise<ComplianceMatter> {
  return customFetch<ComplianceMatter>({
    url: `/compliance/matters/${id}/advance`,
    method: 'POST',
    data: forcePhase ? { force_phase: forcePhase } : undefined,
  });
}

export async function generateMatterReport(id: number): Promise<{ report: string }> {
  return customFetch<{ report: string }>({
    url: `/compliance/matters/${id}/report`,
    method: 'POST',
  });
}

export async function generateCommPlan(
  id: number,
): Promise<Record<string, unknown>> {
  return customFetch<Record<string, unknown>>({
    url: `/compliance/matters/${id}/communication-plan`,
    method: 'POST',
  });
}

export async function executeComm(id: number): Promise<Record<string, unknown>> {
  return customFetch<Record<string, unknown>>({
    url: `/compliance/matters/${id}/execute-communication`,
    method: 'POST',
  });
}

// ── Obligations ──────────────────────────────────────────────────────────────

export async function fetchObligations(params?: {
  area_code?: string;
  status?: string;
  limit?: number;
}): Promise<{ obligations: ComplianceObligation[] }> {
  const queryParams: Record<string, string> = {};
  if (params?.area_code) queryParams.area_code = params.area_code;
  if (params?.status) queryParams.status = params.status;
  if (params?.limit) queryParams.limit = String(params.limit);
  return customFetch<{ obligations: ComplianceObligation[] }>({
    url: '/compliance/obligations',
    method: 'GET',
    params: Object.keys(queryParams).length ? queryParams : undefined,
  });
}

export async function fetchOverdueObligations(): Promise<ComplianceObligation[]> {
  return customFetch<ComplianceObligation[]>({
    url: '/compliance/obligations/overdue',
    method: 'GET',
  });
}

export async function createObligation(
  data: CreateObligationRequest,
): Promise<ComplianceObligation> {
  return customFetch<ComplianceObligation>({
    url: '/compliance/obligations',
    method: 'POST',
    data,
  });
}

export async function fulfillObligation(
  id: number,
  evidenceDescription?: string,
): Promise<ComplianceObligation> {
  return customFetch<ComplianceObligation>({
    url: `/compliance/obligations/${id}/fulfill`,
    method: 'POST',
    data: evidenceDescription ? { evidence_description: evidenceDescription } : undefined,
  });
}

// ── Deadlines ────────────────────────────────────────────────────────────────

export async function fetchDeadlines(params?: {
  days_ahead?: number;
  area_code?: string;
}): Promise<{ deadlines: ComplianceDeadline[] }> {
  const queryParams: Record<string, string> = {};
  if (params?.days_ahead !== undefined) queryParams.days_ahead = String(params.days_ahead);
  if (params?.area_code) queryParams.area_code = params.area_code;
  return customFetch<{ deadlines: ComplianceDeadline[] }>({
    url: '/compliance/deadlines',
    method: 'GET',
    params: Object.keys(queryParams).length ? queryParams : undefined,
  });
}

export async function fetchOverdueDeadlines(): Promise<ComplianceDeadline[]> {
  return customFetch<ComplianceDeadline[]>({
    url: '/compliance/deadlines/overdue',
    method: 'GET',
  });
}

// ── Documents ────────────────────────────────────────────────────────────────

export async function fetchDocuments(params?: {
  area_code?: string;
  doc_type?: string;
  status?: string;
  limit?: number;
}): Promise<{ documents: ComplianceDocument[] }> {
  const queryParams: Record<string, string> = {};
  if (params?.area_code) queryParams.area_code = params.area_code;
  if (params?.doc_type) queryParams.doc_type = params.doc_type;
  if (params?.status) queryParams.status = params.status;
  if (params?.limit) queryParams.limit = String(params.limit);
  return customFetch<{ documents: ComplianceDocument[] }>({
    url: '/compliance/documents',
    method: 'GET',
    params: Object.keys(queryParams).length ? queryParams : undefined,
  });
}

export async function fetchStaleDocuments(days?: number): Promise<ComplianceDocument[]> {
  const queryParams: Record<string, string> = {};
  if (days !== undefined) queryParams.days = String(days);
  return customFetch<ComplianceDocument[]>({
    url: '/compliance/documents/stale',
    method: 'GET',
    params: Object.keys(queryParams).length ? queryParams : undefined,
  });
}

export async function generateDocument(data: GenerateDocRequest): Promise<ComplianceDocument> {
  return customFetch<ComplianceDocument>({
    url: '/compliance/documents/generate',
    method: 'POST',
    data,
  });
}

export async function approveDocument(
  id: number,
  approvedBy?: string,
): Promise<ComplianceDocument> {
  return customFetch<ComplianceDocument>({
    url: `/compliance/documents/${id}/approve`,
    method: 'POST',
    data: approvedBy ? { approved_by: approvedBy } : undefined,
  });
}

export async function signDocument(
  id: number,
  signerName: string,
): Promise<ComplianceDocument> {
  return customFetch<ComplianceDocument>({
    url: `/compliance/documents/${id}/sign`,
    method: 'POST',
    data: { signer_name: signerName },
  });
}

// ── Trainings ────────────────────────────────────────────────────────────────

export async function fetchTrainings(params?: {
  status?: string;
  area_code?: string;
  limit?: number;
}): Promise<{ trainings: ComplianceTraining[] }> {
  const queryParams: Record<string, string> = {};
  if (params?.status) queryParams.status = params.status;
  if (params?.area_code) queryParams.area_code = params.area_code;
  if (params?.limit) queryParams.limit = String(params.limit);
  return customFetch<{ trainings: ComplianceTraining[] }>({
    url: '/compliance/trainings',
    method: 'GET',
    params: Object.keys(queryParams).length ? queryParams : undefined,
  });
}

export async function fetchTrainingStatus(
  id: number,
): Promise<{ training: ComplianceTraining; records: TrainingRecord[] }> {
  return customFetch<{ training: ComplianceTraining; records: TrainingRecord[] }>({
    url: `/compliance/trainings/${id}/status`,
    method: 'GET',
  });
}

export async function createTraining(data: CreateTrainingRequest): Promise<ComplianceTraining> {
  return customFetch<ComplianceTraining>({
    url: '/compliance/trainings',
    method: 'POST',
    data,
  });
}

export async function completeTraining(
  id: number,
  personId: number,
  score?: number,
): Promise<TrainingRecord> {
  return customFetch<TrainingRecord>({
    url: `/compliance/trainings/${id}/complete`,
    method: 'POST',
    data: { person_id: personId, score },
  });
}

// ── Risks ────────────────────────────────────────────────────────────────────

export async function fetchRisks(params?: {
  area_code?: string;
  status?: string;
  limit?: number;
}): Promise<{ risks: ComplianceRisk[] }> {
  const queryParams: Record<string, string> = {};
  if (params?.area_code) queryParams.area_code = params.area_code;
  if (params?.status) queryParams.status = params.status;
  if (params?.limit) queryParams.limit = String(params.limit);
  return customFetch<{ risks: ComplianceRisk[] }>({
    url: '/compliance/risks',
    method: 'GET',
    params: Object.keys(queryParams).length ? queryParams : undefined,
  });
}

export async function fetchRiskHeatmap(): Promise<RiskHeatmapResponse> {
  return customFetch<RiskHeatmapResponse>({
    url: '/compliance/risks/heatmap',
    method: 'GET',
  });
}

// ── RACI ─────────────────────────────────────────────────────────────────────

export async function fetchRaci(params?: {
  matter_id?: number;
  area_code?: string;
}): Promise<{ raci: RaciEntry[] }> {
  const queryParams: Record<string, string> = {};
  if (params?.matter_id !== undefined) queryParams.matter_id = String(params.matter_id);
  if (params?.area_code) queryParams.area_code = params.area_code;
  return customFetch<{ raci: RaciEntry[] }>({
    url: '/compliance/raci',
    method: 'GET',
    params: Object.keys(queryParams).length ? queryParams : undefined,
  });
}

export async function upsertRaci(
  data: CreateRaciRequest,
): Promise<{ raci_id: number; person_id: number; role: string }> {
  return customFetch<{ raci_id: number; person_id: number; role: string }>({
    url: '/compliance/raci',
    method: 'POST',
    data,
  });
}

// ── Reports ──────────────────────────────────────────────────────────────────

export async function fetchDailyReport(): Promise<{ report: string | null }> {
  return customFetch<{ report: string | null }>({
    url: '/compliance/reports/daily',
    method: 'GET',
  });
}

export async function fetchWeeklyReport(): Promise<WeeklyReportResponse> {
  return customFetch<WeeklyReportResponse>({
    url: '/compliance/reports/weekly',
    method: 'GET',
  });
}

export async function fetchAreaReport(code: string): Promise<Record<string, unknown>> {
  return customFetch<Record<string, unknown>>({
    url: `/compliance/reports/area/${code}`,
    method: 'GET',
  });
}

// ── Regulatory Scan ──────────────────────────────────────────────────────────

export async function scanRegulatory(hours?: number): Promise<ScanResult> {
  const queryParams: Record<string, string> = {};
  if (hours !== undefined) queryParams.hours = String(hours);
  return customFetch<ScanResult>({
    url: '/compliance/scan',
    method: 'POST',
    params: Object.keys(queryParams).length ? queryParams : undefined,
  });
}
