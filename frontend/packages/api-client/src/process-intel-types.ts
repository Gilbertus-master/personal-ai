// Process Intelligence types

export interface BusinessLine {
  id: number;
  name: string;
  description: string;
  key_entities: string[];
  importance: 'low' | 'medium' | 'high' | 'critical';
  signals: number;
  status: 'active' | 'archived' | 'merged';
  discovered_at: string;
}

export interface DiscoveredProcess {
  id: number;
  name: string;
  description: string;
  process_type:
    | 'decision'
    | 'approval'
    | 'reporting'
    | 'trading'
    | 'compliance'
    | 'communication'
    | 'operational';
  frequency: 'daily' | 'weekly' | 'monthly' | 'quarterly' | 'ad_hoc';
  participants: string[];
  steps: string[];
  tools_used: string[];
  automation_potential: number;
  automation_notes: string;
  status: 'discovered' | 'confirmed' | 'automated' | 'archived';
}

export interface AppInventoryItem {
  name: string;
  category: string;
  mentions: number;
  replacement: string;
  status: 'not_planned' | 'planned' | 'partial' | 'replaced' | 'not_replaceable';
}

export interface AppDeepAnalysis extends AppInventoryItem {
  id: number;
  vendor: string;
  discovery_sources: string[];
  supported_processes: string[];
  user_details: { user: string; role: string; usage_frequency: string }[];
  data_flow_types: string[];
  cost_monthly_pln: number;
  cost_yearly_pln: number;
  replacement_feasibility: number;
  replacement_plan: string;
  tco_analysis: string;
}

export interface AppCostSummary {
  total_monthly_pln: number;
  total_yearly_pln: number;
  cost_breakdown: unknown[];
}

export interface AppRankingItem {
  rank: number;
  app_name: string;
  replacement_priority: string;
  annual_savings: number;
  feasibility: number;
  [key: string]: unknown;
}

export interface DataFlow {
  flow: string;
  source: string;
  channel: string;
  frequency: 'daily' | 'weekly' | 'monthly' | 'occasional';
  volume: number;
  automation: 'manual' | 'semi_auto' | 'automated' | 'gilbertus';
  bottleneck: 'low' | 'medium' | 'high';
}

export interface OptimizationsSummary {
  total_plans: number;
  total_time_savings_hours: number;
  total_cost_savings_pln: number;
  plans: unknown[];
}

export interface WorkActivity {
  activity: string;
  category: string;
  frequency: string;
  hours_per_week: number;
  automation_potential: number;
}

export interface AutomationTask {
  task: string;
  gilbertus_module: string;
  dev_hours: number;
  savings_monthly_pln: number;
  priority: string;
}

export interface EmployeeWorkProfile {
  person_name: string;
  person_role: string;
  work_activities: WorkActivity[];
  automatable_pct: number;
  replaceability_score: number;
  automation_roadmap: AutomationTask[];
}

export interface AutomationOverview {
  total_employees: number;
  analyzed: number;
  avg_automatable_pct: number;
  top_automation_candidates: unknown[];
}

export interface AutomationRoadmap {
  total_initiatives: number;
  roadmap: { quarter: string; initiatives: unknown[] }[];
}

export interface TechSolution {
  id: number;
  name: string;
  solution_type: 'build' | 'buy' | 'extend';
  estimated_dev_hours: number;
  estimated_cost_pln: number;
  estimated_annual_savings_pln: number;
  roi_ratio: number;
  payback_months: number;
  strategic_alignment_score: number;
  status: 'proposed' | 'approved' | 'in_development' | 'deployed' | 'rejected';
  risk_notes: string;
}

export interface TechRadarResponse {
  by_type: Record<string, TechSolution[]>;
  by_status: Record<string, TechSolution[]>;
  top_10_by_roi: TechSolution[];
  total_solutions: number;
  total_estimated_savings_pln: number;
}

export interface TechRoadmap {
  roadmap: { quarter: string; solutions: TechSolution[] }[];
  total_quarters: number;
  total_dev_hours: number;
}

export interface TechAlignment {
  strategic_goals: {
    goal_id: number;
    goal_name: string;
    supporting_solutions: TechSolution[];
  }[];
  total_alignment_coverage: number;
}

export interface DiscoveryResult {
  message: string;
  business_lines?: number;
  processes?: number;
  apps_found?: number;
  new?: number;
  timestamp: string;
}

export interface ProcessIntelDashboard {
  business_lines: { business_lines: BusinessLine[] };
  apps: AppInventoryItem[];
  optimizations: OptimizationsSummary;
  workforce_automation?: unknown;
  tech_radar?: unknown;
}
