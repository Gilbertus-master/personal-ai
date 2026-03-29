// GET /brief/today
export interface MorningBriefResponse {
  status: string;
  date: string | null;
  summary_id: number | null;
  period_start: string | null;
  period_end: string | null;
  events_count: number | null;
  open_loops_count: number | null;
  entities_count: number | null;
  summaries_count: number | null;
  text: string | null;
  meta: { latency_ms: number };
}

// GET /alerts
export interface AlertItem {
  alert_id: number;
  alert_type: string;
  severity: string;
  title: string;
  description: string;
  evidence: string | null;
  is_active: boolean;
  created_at: string | null;
}
export interface AlertsResponse {
  alerts: AlertItem[];
  meta: Record<string, any>;
}

// GET /status
export interface StatusResponse {
  db: {
    documents: number;
    chunks: number;
    entities: number;
    events: number;
    insights: number | null;
    summaries: number;
    alerts: number | null;
  };
  embeddings: { total: number; done: number; pending: number };
  sources: Array<{ source_type: string; document_count: number; newest_date: string }>;
  last_backup: string;
  services: {
    postgres: { status: string; error?: string };
    qdrant: { status: string; error?: string };
    whisper: { status: string; error?: string };
  };
  cron_jobs: any[];
  latency_ms: number;
}

// POST /timeline
export interface TimelineEvent {
  event_id: number;
  event_time: string | null;
  event_type: string;
  document_id: number;
  chunk_id: number;
  summary: string;
  entities: string[];
}
export interface TimelineRequest {
  event_type?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
}
export interface TimelineResponse {
  events: TimelineEvent[];
  meta: Record<string, any>;
}

// GET /commitments
export interface CommitmentItem {
  id: number;
  person_name: string;
  commitment_text: string;
  deadline: string | null;
  status: string;
  created_at: string;
}
export interface CommitmentsListResponse {
  commitments: CommitmentItem[];
}

// GET /costs/budget
export interface BudgetResponse {
  daily_total_usd: number;
  budgets: Array<{
    scope: string;
    limit_usd: number;
    spent_usd: number;
    pct: number;
    hard_limit: boolean;
    status: string;
  }>;
  alerts_today: Array<{
    scope: string;
    type: string;
    message: string;
    at: string;
  }>;
}

// Derived types for UI
export interface KpiCardData {
  label: string;
  value: number | string;
  trend?: 'up' | 'down' | 'flat';
  trendValue?: string;
  color?: 'default' | 'success' | 'warning' | 'danger';
}
