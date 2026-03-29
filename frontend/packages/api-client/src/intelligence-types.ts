// === Opportunities ===
export interface Opportunity {
  id: number;
  type: string;
  description: string;
  value_pln: number;
  effort_hours: number;
  roi: number;
  confidence: number;
  status: string;
  created: string;
}

export interface OpportunityScanResult {
  status: 'ok' | 'no_data';
  events_scanned: number;
  chunks_scanned: number;
  opportunities_found: number;
  opportunities_saved: number;
  notification: string | null;
}

// === Inefficiency ===
export interface RepeatingTask {
  type: string;
  pattern: string;
  weeks_seen: number;
  total: number;
  avg_confidence: number;
  est_hours_per_month: number;
  automation_potential: 'high' | 'medium';
}

export interface EscalationBottleneck {
  person: string;
  escalations: number;
  interpretation: string;
}

export interface MeetingOverload {
  person: string;
  date: string;
  meetings: number;
  interpretation: string;
}

export interface InefficiencyReport {
  generated_at: string;
  repeating_tasks: RepeatingTask[];
  escalation_bottlenecks: EscalationBottleneck[];
  meeting_overload: MeetingOverload[];
  summary: {
    repeating_patterns: number;
    bottleneck_people: number;
    overloaded_days: number;
    est_automation_hours_per_month: number;
    est_automation_savings_pln: number;
  };
}

// === Correlation ===
export type CorrelationType = 'temporal' | 'person' | 'anomaly' | 'report';

export interface CorrelationRequest {
  correlation_type: CorrelationType;
  event_type_a?: string | null;
  event_type_b?: string | null;
  person?: string | null;
  window?: 'week' | 'month';
}

export interface CorrelationResult {
  correlation_type: CorrelationType;
  data: unknown;
  latency_ms?: number;
}

// === Scenarios ===
export interface Scenario {
  id: number;
  title: string;
  description: string;
  type: 'risk' | 'opportunity' | 'strategic';
  status: 'draft' | 'analyzed' | 'archived';
  trigger: string | null;
  created_by: string;
  created_at: string;
  analyzed_at: string | null;
  total_impact_pln: number;
  outcome_count: number;
}

export interface ScenarioOutcome {
  dimension: 'revenue' | 'costs' | 'people' | 'operations' | 'reputation';
  impact_description: string;
  impact_value_pln: number;
  probability: number;
  time_horizon: '1m' | '3m' | '6m' | '1y' | '3y';
  mitigation: string;
}

export interface ScenarioAnalysis {
  scenario_id: number;
  title: string;
  outcomes: ScenarioOutcome[];
  total_impact_pln: number;
  latency_ms: number;
}

export interface ScenarioCreateParams {
  title: string;
  description: string;
  scenario_type?: 'risk' | 'opportunity' | 'strategic';
}

// === Predictions ===
export interface EscalationRisk {
  person_name: string;
  alert_type: 'escalation_risk';
  risk: 'low' | 'medium' | 'high';
  probability: number;
  recent_conflicts: number;
  prediction: string | null;
}

export interface CommunicationGap {
  person_name: string;
  alert_type: 'communication_gap';
  silence_days: number;
  baseline_events_per_week: number;
  prediction: string;
}

export interface DeadlineRisk {
  commitment_id: number;
  description: string;
  days_until_deadline: number;
  alert_type: 'deadline_risk';
  prediction: string;
}

export interface PredictiveAlerts {
  escalation_risks: EscalationRisk[];
  communication_gaps: CommunicationGap[];
  deadline_risks: DeadlineRisk[];
  total_alerts: number;
  new_stored: number;
  status: 'ok';
}

// === Org Health ===
export interface OrgHealthDimension {
  score: number;
  value: number;
  weight: number;
  label: string;
}

export interface OrgHealth {
  current_score: number;
  trend: 'improving' | 'declining' | 'stable';
  history: Array<{ week: string; score: number }>;
  best_week: { week: string; score: number };
  worst_week: { week: string; score: number };
}

export interface OrgHealthAssessment {
  id: number | null;
  week_start: string;
  overall_score: number;
  trend_vs_last_week: number | null;
  dimensions: Record<string, OrgHealthDimension>;
  top_risks: string[];
  top_improvements: string[];
}
