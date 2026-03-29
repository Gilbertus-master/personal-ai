export interface MarketInsight {
  id: number;
  type: 'price_change' | 'regulation' | 'tender' | 'trend' | 'risk';
  title: string;
  description: string;
  impact: string;
  relevance: number;
  companies: string[];
  created_at: string;
}

export interface MarketAlert {
  id: number;
  level: 'info' | 'warning' | 'critical';
  message: string;
  acknowledged: boolean;
  created_at: string;
  insight_title: string;
  insight_type: string;
  relevance: number;
}

export interface MarketSource {
  name: string;
  last_fetched: string | null;
  active: boolean;
  id?: number;
  url?: string;
  source_type?: 'rss' | 'api' | 'web';
}

export interface MarketDashboard {
  insights: MarketInsight[];
  alerts: MarketAlert[];
  stats: {
    by_type: Record<string, number>;
    total_insights: number;
    active_alerts: number;
  };
  sources: MarketSource[];
}

export interface Competitor {
  id: number;
  name: string;
  krs: string;
  industry: string;
  watch_level: 'active' | 'passive' | 'archived';
  recent_signals_30d: number;
  high_severity: number;
  latest_analysis?: string;
  analysis_date?: string;
}

export interface CompetitorSignal {
  id: number;
  competitor: string;
  type: 'krs_change' | 'hiring' | 'media' | 'tender' | 'financial';
  title: string;
  description: string;
  severity: 'low' | 'medium' | 'high';
  date: string | null;
  source_url: string;
}

export interface SwotAnalysis {
  competitor: string;
  swot: {
    strengths: string[];
    weaknesses: string[];
    threats: string[];
    opportunities: string[];
    summary: string;
  };
  signals_count: number;
}

export interface CompetitorsResponse {
  competitors: Competitor[];
  total: number;
  active_count: number;
}

export interface ScanResult {
  success: boolean;
  fetch?: {
    sources_checked: number;
    new_items: number;
  };
  analysis?: {
    insights_created: number;
    alerts_created: number;
  };
}

export interface CompetitorScanResult {
  success: boolean;
  signals_collected: Record<string, number>;
  competitors_analyzed: number;
  analysis_summaries: string[];
  landscape: Record<string, unknown>;
}
