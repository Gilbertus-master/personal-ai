// === List / Directory ===
export interface Relationship {
  id: number;
  relationship_type: string;
  current_role: string | null;
  organization: string | null;
  status: string;
  contact_channel: string | null;
  can_contact_directly: boolean;
  sentiment: string;
  last_contact_date: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface Person {
  id: number;
  slug: string;
  first_name: string;
  last_name: string | null;
  aliases: string[];
  created_at: string;
  updated_at: string;
  relationship: Relationship | null;
}

export interface PeopleListResponse {
  people: Person[];
  meta: { count: number; latency_ms: number };
}

// === Full Profile ===
export interface RoleHistory {
  id: number;
  role: string;
  organization: string | null;
  date_from: string | null;
  date_to: string | null;
  notes: string | null;
}

export interface PersonTimelineEvent {
  id: number;
  event_date: string;
  event_type: string | null;
  description: string;
  source: string;
  created_at: string;
}

export interface OpenLoop {
  id: number;
  description: string;
  status: string;
  created_at: string;
  closed_at: string | null;
}

export interface PersonFull extends Person {
  roles_history: RoleHistory[];
  timeline: PersonTimelineEvent[];
  open_loops: OpenLoop[];
}

// === Scorecard ===
export interface Scorecard {
  person: {
    name: string;
    role: string | null;
    org: string | null;
    status: string | null;
    sentiment: string | null;
  };
  data_volume: { chunks: number; events: number };
  recent_events_30d: Array<{ type: string; time: string | null; summary: string }>;
  open_loops: string[];
  event_profile_3m: Record<string, number>;
  weekly_activity: Array<{ week: string; count: number }>;
}

// === Sentiment ===
export interface SentimentTrend {
  person_slug: string;
  weeks: number;
  trend: Array<{ week: string; score: number; label: string }>;
}

export interface SentimentAlert {
  person_slug: string;
  person_name: string;
  alert_type: string;
  message: string;
  created_at: string;
}

export interface SentimentAlertsResponse {
  alerts: SentimentAlert[];
}

// === Delegation ===
export interface DelegationScore {
  person_slug: string;
  score: number;
  metrics: Record<string, number>;
  months: number;
}

// === Network ===
export interface NetworkNode {
  id: string;
  name: string;
  role: string | null;
  org: string | null;
  event_count: number;
}

export interface NetworkEdge {
  source: string;
  target: string;
  weight: number;
}

export interface NetworkGraph {
  nodes: NetworkNode[];
  edges: NetworkEdge[];
}

// === Evaluation ===
export interface EvaluateRequest {
  person_slug: string;
  date_from?: string | null;
  date_to?: string | null;
}

export interface EvaluationResult {
  evaluation: string;
  latency_ms: number;
}

// === Wellbeing ===
export interface WellbeingResponse {
  weeks: number;
  data: Array<{ week: string; score: number; indicators: Record<string, number> }>;
}

// === Create / Update ===
export interface RelationshipCreate {
  relationship_type: string;
  current_role?: string | null;
  organization?: string | null;
  status?: string;
  contact_channel?: string | null;
  can_contact_directly?: boolean;
  sentiment?: string;
  last_contact_date?: string | null;
  notes?: string | null;
}

export interface PersonCreate {
  slug: string;
  first_name: string;
  last_name?: string | null;
  aliases?: string[] | null;
  relationship?: RelationshipCreate | null;
}

export interface PersonUpdate {
  first_name?: string;
  last_name?: string | null;
  aliases?: string[] | null;
}

export interface TimelineEventCreate {
  event_date: string;
  event_type?: string | null;
  description: string;
  source?: string;
}

export interface RoleHistoryCreate {
  role: string;
  organization?: string | null;
  date_from?: string | null;
  date_to?: string | null;
  notes?: string | null;
}

export interface OpenLoopCreate {
  description: string;
}

// === Response Tracking ===
export interface ResponseTrackingResponse {
  days: number;
  stats: Array<{
    person: string;
    channel: string;
    avg_response_hours: number;
    count: number;
  }>;
}

// === Blind Spots ===
export interface BlindSpotsResponse {
  blind_spots: Array<{
    area: string;
    severity: string;
    description: string;
    last_data: string | null;
  }>;
}

// === Delegation Stats (aggregate) ===
export interface DelegationStatsResponse {
  rankings: Array<{
    person: string;
    score: number;
    tasks_delegated: number;
    completion_rate: number;
  }>;
}
