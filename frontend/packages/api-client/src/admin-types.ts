export interface CronJob {
  job_name: string;
  schedule: string;
  command: string;
  description: string;
  category: string;
  log_file: string;
  enabled: boolean;
  username: string;
}

export interface CronListResponse {
  jobs: CronJob[];
}

export interface CronSummary {
  total: number;
  categories: { category: string; jobs: number; active_users: number }[];
  by_user: { username: string; enabled: number; disabled: number }[];
}

export interface CronToggleResponse {
  job_name: string;
  username: string;
  enabled: boolean;
}

export interface SystemStatus {
  db: {
    total_chunks: number;
    total_events: number;
    total_sources: number;
    data_volume_gb: number;
    tables: Record<string, number>;
  };
  embedding: {
    indexed_chunks: number;
    status: 'ok' | 'degraded' | 'error';
    qdrant_status: unknown;
  };
  sources: Record<string, number>;
  last_backup: string;
  services: Record<string, { status: 'ok' | 'error' }>;
  crons: {
    total: number;
    enabled: number;
    failed: string[];
    upcoming: unknown[];
  };
}

export interface BudgetItem {
  scope: string;
  limit_usd: number;
  spent_usd: number;
  pct: number;
  hard_limit: boolean;
  status: 'ok' | 'warning' | 'exceeded';
}

export interface BudgetAlert {
  scope: string;
  alert_type: string;
  message: string;
  created_at: string;
}

export interface BudgetStatus {
  budgets: BudgetItem[];
  daily_total: number;
  module_costs: Record<string, number>;
  alerts: BudgetAlert[];
}

export interface CodeFinding {
  id: number;
  file: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  category: string;
  title: string;
  description: string;
  attempts: number;
  last_attempt: string;
}

export interface AdminUser {
  id: number;
  email: string;
  name: string;
  role: string;
  level: number;
  department: string | null;
  active: boolean;
  created: string;
}

export interface CreateUserRequest {
  email: string;
  name: string;
  role: string;
  department?: string;
}

export interface CreateUserResponse {
  status: 'created';
  user_id: number;
  email: string;
  role: string;
}

export interface AuditLogEntry {
  id: number;
  user: string | null;
  action: string;
  resource: string;
  result: 'ok' | 'denied' | 'error' | 'governance_violation';
  ip: string;
  at: string;
}
