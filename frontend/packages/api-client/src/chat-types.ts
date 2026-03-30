export interface AskRequest {
  query: string;
  top_k?: number;
  source_types?: string[];
  source_names?: string[];
  date_from?: string;
  date_to?: string;
  mode?: string;
  include_sources?: boolean;
  answer_style?: string;
  answer_length?: 'short' | 'medium' | 'long' | 'auto';
  allow_quotes?: boolean;
  debug?: boolean;
  channel?: string;
  session_id?: string;
  model_preference?: 'cheap' | 'balanced' | 'best';
}

export interface AskResponse {
  answer: string;
  sources?: SourceItem[];
  matches?: MatchItem[];
  meta: AskResponseMeta;
  run_id?: number;
}

export interface SourceItem {
  document_id: number;
  title: string;
  source_type: string;
  source_name: string;
  created_at: string;
}

export interface MatchItem {
  chunk_id: number;
  document_id: number;
  score: number;
  source_type: string;
  source_name: string;
  title: string;
  created_at: string;
  text: string;
}

export interface AskResponseMeta {
  question_type: string;
  analysis_depth: string;
  used_fallback: boolean;
  retrieved_count: number;
  normalized_query: string;
  date_from: string;
  date_to: string;
  answer_style: string;
  answer_length: string;
  channel: string;
  debug: boolean;
  latency_ms: number;
  cache_hit: boolean;
}

export interface ConversationWindow {
  channel_key: string;
  message_count: number;
  total_chars: number;
  last_active: string;
  created_at: string;
}
