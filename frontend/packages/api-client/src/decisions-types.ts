export type DecisionArea = 'business' | 'trading' | 'relationships' | 'wellbeing' | 'general';

export interface DecisionOutcome {
  id: number;
  decision_id: number;
  actual_outcome: string;
  rating: number;
  outcome_date: string;
  created_at: string;
}

export interface Decision {
  id: number;
  decision_text: string;
  context: string | null;
  expected_outcome: string | null;
  area: DecisionArea;
  confidence: number;
  decided_at: string;
  created_at: string;
  outcomes: DecisionOutcome[];
}

export interface DecisionCreate {
  decision_text: string;
  context?: string;
  expected_outcome?: string;
  area: DecisionArea;
  confidence: number;
  decided_at?: string;
}

export interface OutcomeCreate {
  actual_outcome: string;
  rating: number;
  outcome_date?: string;
}

export interface DecisionResponse {
  id: number;
  decision_text: string;
  context: string | null;
  expected_outcome: string | null;
  area: DecisionArea;
  confidence: number;
  decided_at: string;
  created_at: string;
}

export interface OutcomeResponse {
  id: number;
  decision_id: number;
  actual_outcome: string;
  rating: number;
  outcome_date: string;
  created_at: string;
}

export interface DecisionsListResponse {
  decisions: Decision[];
  meta: {
    count: number;
    area?: string;
    latency_ms: number;
  };
}

export interface PatternsResponse {
  insights: string;
  meta: {
    decision_count: number;
    areas: string[];
    latency_ms: number;
  };
}

export interface DecisionIntelligenceResponse {
  analysis: unknown;
  meta: {
    months: number;
    latency_ms: number;
  };
}
