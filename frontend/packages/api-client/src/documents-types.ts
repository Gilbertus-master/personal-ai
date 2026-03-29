export type SourceType =
  | 'email'
  | 'teams'
  | 'whatsapp'
  | 'document'
  | 'pdf'
  | 'plaud'
  | 'chatgpt'
  | 'calendar';

export interface DocumentSource {
  document_id: number;
  title: string;
  source_type: SourceType;
  created_at: string;
  classification?: string;
}

export interface DocumentSearchMatch {
  chunk_id: number;
  document_id: number;
  score: number;
  text: string;
}

export interface DocumentSearchResult {
  answer: string;
  sources: DocumentSource[];
  matches: DocumentSearchMatch[];
  meta: {
    question_type: string;
    latency_ms: number;
    cache_hit: boolean;
  };
}

export interface DocumentSearchParams {
  query: string;
  source_types?: string[];
  date_from?: string;
  date_to?: string;
  top_k?: number;
  mode?: string;
}

export interface DocumentListItem {
  id: number;
  title: string;
  source_type: SourceType;
  classification: string;
  created_at: string;
  chunk_count?: number;
}

export interface DocumentListResponse {
  documents: DocumentListItem[];
  meta: {
    total: number;
    page: number;
    per_page: number;
  };
}

export interface DocumentDetail {
  id: number;
  title: string;
  source_type: SourceType;
  classification: string;
  created_at: string;
  chunks: { id: number; text: string; position: number }[];
  entities?: unknown[];
  events?: unknown[];
}

export interface DocumentUploadResponse {
  success: boolean;
  document_id: number;
  message: string;
}

export interface IngestionDashboard {
  sources: Record<string, { total: number; last_imported: string | null }>;
  extraction_backlogs: Record<string, number>;
  dlq_stats: { total: number; by_error: Record<string, number> };
  guardian_alerts: { total: number; critical: number };
}
