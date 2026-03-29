// ── Finance & Costs Types ───────────────────────────────────────────────────

export interface FinanceAlert {
  alert_type: string;
  description: string;
  severity: string;
  created_at: string;
}

export interface BudgetUtilization {
  category: string;
  planned: number;
  actual: number;
  pct: number;
  currency: string;
}

export interface CompanyFinance {
  latest_metrics: Record<
    string,
    { value: number; currency: string; period_start: string; source: string }
  >;
  budget_utilization: BudgetUtilization[];
  alerts: FinanceAlert[];
}

export interface ApiCosts {
  monthly: { month: string; total_usd: number; api_calls: number }[];
  avg_monthly_usd: number;
  trend: string;
  current_month_forecast_usd: number;
}

export interface FinanceDashboard {
  companies: Record<string, CompanyFinance>;
  active_alerts: number;
  api_costs: ApiCosts;
  total_budget_utilization: number;
}

// ── Cost Budget ─────────────────────────────────────────────────────────────

export interface BudgetScope {
  scope: string;
  limit_usd: number;
  spent_usd: number;
  pct: number;
  hard_limit: boolean;
  status: 'ok' | 'warning' | 'exceeded';
}

export interface CostAlert {
  scope: string;
  type: string;
  message: string;
  at: string;
}

export interface CostBudget {
  daily_total_usd: number;
  budgets: BudgetScope[];
  alerts_today: CostAlert[];
}

// ── Strategic Goals ─────────────────────────────────────────────────────────

export interface GoalProgress {
  date: string;
  value: number;
  note?: string;
}

export interface StrategicGoal {
  id: number;
  title: string;
  description: string;
  company: string;
  area: 'business' | 'trading' | 'operations' | 'people' | 'technology' | 'wellbeing';
  target_value: number;
  current_value: number;
  unit: string;
  deadline: string;
  status: 'on_track' | 'at_risk' | 'behind' | 'achieved' | 'cancelled';
  pct_complete: number;
  sub_goals?: StrategicGoal[];
  dependencies?: number[];
  progress?: GoalProgress[];
}

export interface GoalsSummary {
  total_goals: number;
  by_status: Record<string, number>;
  by_area: Record<string, number>;
  top_risks: unknown[];
  recently_achieved: unknown[];
  upcoming_deadlines: unknown[];
}

// ── Cost Estimate ───────────────────────────────────────────────────────────

export interface CostEstimate {
  direct_cost_pln: number;
  roi_ratio: number;
  payback_months: number;
  recommendation: string;
  [key: string]: unknown;
}

// ── Request types ───────────────────────────────────────────────────────────

export interface AddMetricRequest {
  company: string;
  metric_type: string;
  value: number;
  period_start: string;
  period_end: string;
  source?: string;
}

export interface AddBudgetRequest {
  company: string;
  category: string;
  planned_amount: number;
  period_start: string;
  period_end: string;
}

export interface CreateGoalRequest {
  title: string;
  target_value: number;
  unit?: string;
  deadline?: string;
  company?: string;
  area?: string;
}

export interface UpdateGoalProgressRequest {
  value: number;
  note?: string;
}
