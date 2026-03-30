export interface ActivityLogEntry {
  action_type: string;
  item_id: string;
  item_type: string;
  item_title?: string;
  item_context?: string;
  payload?: Record<string, unknown>;
}

export interface ActivityLogRecord {
  id: number;
  user_id: string;
  action_type: string;
  item_id: string;
  item_type: string;
  item_title: string | null;
  item_context: string | null;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface AnnotateParams {
  item_id: string;
  item_type: string;
  annotation_type: string;
  content?: string;
  rating?: number;
  is_false_positive?: boolean;
  forward_to?: string;
}

export interface Annotation {
  id: number;
  item_id: string;
  item_type: string;
  user_id: string;
  annotation_type: string;
  content: string | null;
  rating: number | null;
  is_false_positive: boolean;
  research_result: string | null;
  forward_to: string | null;
  created_at: string;
}

export interface ResearchParams {
  item_id: string;
  item_type: string;
  item_title: string;
  item_content?: string;
  context?: string;
}

export interface ResearchResult {
  id: number;
  research_result: string;
}
