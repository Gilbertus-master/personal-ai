export interface PluginProposal {
  id: number;
  title: string;
  description?: string;
  expected_value?: string;
  proposed_by: string;
  status: 'pending' | 'approved' | 'rejected' | 'developing' | 'reviewing' | 'deployed';
  value_score: number | null;
  governance_result?: GovernanceResult;
  review_result?: ReviewResult;
  sandbox_session_id?: string;
  tenant?: string;
  created_at: string;
}

export interface GovernanceResult {
  feasibility?: {
    possible: boolean;
    reasoning: string;
    score: number;
  };
  value?: {
    approved: boolean;
    value_score: number;
    reasoning: string;
  };
  cost_estimate?: {
    development_time_hours: number;
    api_cost_per_invocation_usd: number;
    maintenance_hours_per_month: number;
    complexity: string;
    reasoning: string;
  };
  duplicate_check?: {
    is_duplicate: boolean;
    similar_plugin: string | null;
    similarity_score: number;
    reasoning: string;
  };
  overall_approved: boolean;
  overall_score: number;
  rejection_reason?: string;
}

export interface ReviewResult {
  passed: boolean;
  security_score: number;
  quality_score: number;
  tests_passed: number;
  tests_total: number;
  findings: ReviewFinding[];
  error?: string;
}

export interface ReviewFinding {
  severity: 'critical' | 'high' | 'medium' | 'low';
  category: string;
  title: string;
  description: string;
  file?: string;
  line?: number;
}

export interface PluginApproveRequest {
  tenant: string;
}

export interface PluginRejectRequest {
  tenant: string;
  reason: string;
}

export interface PluginApproveResponse {
  status: string;
  proposal_id: number;
}
