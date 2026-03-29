// ── Type Aliases ──────────────────────────────────────────────────────────────

export type ComplianceAreaCode =
  | 'URE'
  | 'RODO'
  | 'AML'
  | 'KSH'
  | 'ESG'
  | 'LABOR'
  | 'TAX'
  | 'CONTRACT'
  | 'INTERNAL_AUDIT';

export type MatterType =
  | 'new_regulation'
  | 'regulation_change'
  | 'audit_finding'
  | 'incident'
  | 'license_renewal'
  | 'contract_review'
  | 'policy_update'
  | 'training_need'
  | 'complaint'
  | 'inspection'
  | 'risk_assessment'
  | 'other';

export type MatterStatus =
  | 'open'
  | 'researching'
  | 'analyzed'
  | 'action_plan_ready'
  | 'in_progress'
  | 'review'
  | 'completed'
  | 'closed'
  | 'on_hold';

export type MatterPhase =
  | 'initiation'
  | 'research'
  | 'analysis'
  | 'planning'
  | 'document_generation'
  | 'approval'
  | 'training'
  | 'communication'
  | 'verification'
  | 'monitoring'
  | 'closed';

export type Priority = 'low' | 'medium' | 'high' | 'critical';

export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';

export type Likelihood = 'very_low' | 'low' | 'medium' | 'high' | 'very_high';

export type Impact = 'negligible' | 'minor' | 'moderate' | 'major' | 'catastrophic';

export type RiskColor = 'green' | 'yellow' | 'orange' | 'red' | 'critical';

export type ObligationType =
  | 'reporting'
  | 'licensing'
  | 'documentation'
  | 'training'
  | 'audit'
  | 'notification'
  | 'registration'
  | 'inspection'
  | 'filing'
  | 'other';

export type Frequency =
  | 'one_time'
  | 'daily'
  | 'weekly'
  | 'monthly'
  | 'quarterly'
  | 'semi_annual'
  | 'annual'
  | 'biennial'
  | 'on_change'
  | 'on_demand';

export type ComplianceStatus =
  | 'compliant'
  | 'partially_compliant'
  | 'non_compliant'
  | 'unknown'
  | 'not_applicable';

export type DocType =
  | 'policy'
  | 'procedure'
  | 'form'
  | 'template'
  | 'register'
  | 'report'
  | 'certificate'
  | 'license'
  | 'contract_annex'
  | 'training_material'
  | 'communication'
  | 'regulation_text'
  | 'internal_regulation'
  | 'risk_assessment'
  | 'audit_report'
  | 'other';

export type DocStatus =
  | 'draft'
  | 'review'
  | 'approved'
  | 'active'
  | 'superseded'
  | 'expired'
  | 'archived';

export type SignatureStatus =
  | 'not_required'
  | 'pending'
  | 'partially_signed'
  | 'signed'
  | 'expired';

export type TrainingType =
  | 'mandatory'
  | 'awareness'
  | 'certification'
  | 'refresher'
  | 'onboarding';

export type TrainingStatus =
  | 'planned'
  | 'material_ready'
  | 'scheduled'
  | 'in_progress'
  | 'completed'
  | 'cancelled';

export type TrainingRecordStatus =
  | 'assigned'
  | 'notified'
  | 'started'
  | 'completed'
  | 'overdue'
  | 'exempted';

export type DeadlineType =
  | 'filing'
  | 'reporting'
  | 'license_renewal'
  | 'audit'
  | 'training'
  | 'review'
  | 'inspection'
  | 'payment'
  | 'document_expiry'
  | 'contract'
  | 'custom';

export type DeadlineStatus = 'pending' | 'in_progress' | 'completed' | 'overdue' | 'cancelled';

export type RaciRole = 'responsible' | 'accountable' | 'consulted' | 'informed';

export type RiskStatus = 'open' | 'mitigated' | 'accepted' | 'closed';

// ── Response Interfaces ──────────────────────────────────────────────────────

export interface ComplianceArea {
  code: ComplianceAreaCode;
  name_pl: string;
  name_en: string;
  governing_body: string;
  key_regulations: string[];
  risk_level: RiskLevel;
  responsible_person_id: number | null;
  status: ComplianceStatus;
}

export interface ComplianceMatter {
  id: number;
  title: string;
  matter_type: MatterType;
  area_code: ComplianceAreaCode;
  priority: Priority;
  status: MatterStatus;
  phase: MatterPhase;
  description?: string;
  legal_analysis?: string;
  risk_analysis?: Record<string, unknown>;
  obligations_report?: string;
  consequences_report?: string;
  action_plan?: Record<string, unknown>[];
  communication_plan?: Record<string, unknown>[];
  source_regulation?: string;
  created_at: string;
  updated_at: string;
  completed_at?: string;
}

export interface ComplianceObligation {
  id: number;
  area_code: ComplianceAreaCode;
  title: string;
  obligation_type: ObligationType;
  frequency: Frequency;
  next_deadline?: string;
  responsible_person_id?: number;
  compliance_status: ComplianceStatus;
  penalty_description?: string;
  penalty_max_pln?: number;
  created_at: string;
}

export interface ComplianceDeadline {
  id: number;
  title: string;
  date: string;
  type: DeadlineType;
  status: DeadlineStatus;
  recurrence: Frequency;
  area_code: ComplianceAreaCode;
  area_name: string;
  days_overdue?: number;
}

export interface ComplianceDocument {
  id: number;
  title: string;
  doc_type: DocType;
  area_code: ComplianceAreaCode;
  matter_id?: number;
  version: string;
  generated_by: string;
  approved_by?: string;
  approved_at?: string;
  valid_from?: string;
  valid_until?: string;
  review_due?: string;
  signature_status: SignatureStatus;
  status: DocStatus;
  created_at: string;
}

export interface ComplianceTraining {
  id: number;
  title: string;
  area_code: ComplianceAreaCode;
  matter_id?: number;
  training_type: TrainingType;
  content_summary?: string;
  target_audience: string[];
  deadline?: string;
  status: TrainingStatus;
  created_at: string;
}

export interface TrainingRecord {
  person_id: number;
  person_name: string;
  status: TrainingRecordStatus;
  notified_at?: string;
  completed_at?: string;
  score?: number;
}

export interface ComplianceRisk {
  id: number;
  risk_title: string;
  risk_description?: string;
  likelihood: Likelihood;
  impact: Impact;
  risk_score: number;
  color: RiskColor;
  current_controls?: string;
  mitigation_plan?: string;
  status: RiskStatus;
  matter_id?: number;
  area_code: ComplianceAreaCode;
  matter_title?: string;
  created_at: string;
}

export interface RaciEntry {
  id: number;
  area_code?: ComplianceAreaCode;
  matter_id?: number;
  person_id: number;
  person_name: string;
  role: RaciRole;
  notes?: string;
}

export interface ComplianceDashboard {
  total_obligations: number;
  compliant_count: number;
  non_compliant_count: number;
  open_matters: number;
  overdue_deadlines: number;
  at_risk_areas: number;
  overall_risk_score: number;
}

export interface RiskHeatmapArea {
  code: ComplianceAreaCode;
  name: string;
  risk_count: number;
  avg_score: number;
  max_score: number;
  critical_count: number;
  color: RiskColor;
}

export interface RiskHeatmapResponse {
  areas: RiskHeatmapArea[];
  total_risks: number;
  overall_avg: number;
}

export interface WeeklyReportArea {
  code: ComplianceAreaCode;
  name: string;
  obligations: {
    compliant: number;
    partially_compliant: number;
    non_compliant: number;
  };
  matters: {
    opened: number;
    closed: number;
  };
  deadlines: {
    met: number;
    missed: number;
  };
  documents: {
    generated: number;
    approved: number;
  };
  open_risks: number;
}

export interface WeeklyReportResponse {
  generated_at: string;
  areas: WeeklyReportArea[];
  whatsapp_sent: boolean;
}

export interface ScanResult {
  scanned_chunks: number;
  regulatory_found: number;
  matters_created: number;
  details: {
    title: string;
    area_code: ComplianceAreaCode;
    matter_type: MatterType;
    priority: Priority;
    matter_id: number;
    action: string;
  }[];
}

// ── Request Interfaces ───────────────────────────────────────────────────────

export interface CreateMatterRequest {
  title: string;
  matter_type: MatterType;
  area_code: ComplianceAreaCode;
  description?: string;
  priority?: Priority;
  contract_id?: number;
  source_regulation?: string;
}

export interface CreateObligationRequest {
  area_code: ComplianceAreaCode;
  title: string;
  obligation_type: ObligationType;
  frequency?: Frequency;
  next_deadline?: string;
  responsible_person_id?: number;
  description?: string;
  penalty_description?: string;
  penalty_max_pln?: number;
}

export interface GenerateDocRequest {
  matter_id: number;
  doc_type: DocType;
  title?: string;
  template_hint?: string;
  signers?: { name: string; role: string }[];
  valid_months?: number;
}

export interface CreateTrainingRequest {
  title: string;
  area_code: ComplianceAreaCode;
  matter_id?: number;
  training_type?: TrainingType;
  content_summary?: string;
  target_audience?: string[];
  deadline?: string;
  generate_material?: boolean;
}

export interface CreateRaciRequest {
  area_code?: ComplianceAreaCode;
  matter_id?: number;
  person_id: number;
  role?: RaciRole;
  notes?: string;
}
