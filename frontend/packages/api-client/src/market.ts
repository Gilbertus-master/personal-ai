import { customFetch } from './base';
import type {
  MarketDashboard,
  ScanResult,
  MarketInsight,
  MarketAlert,
  MarketSource,
  CompetitorsResponse,
  CompetitorScanResult,
  SwotAnalysis,
  CompetitorSignal,
} from './market-types';

export async function getMarketDashboard(params?: {
  days?: number;
}): Promise<MarketDashboard> {
  const queryParams: Record<string, string> = {};
  if (params?.days !== undefined) queryParams.days = String(params.days);
  return customFetch<MarketDashboard>({
    url: '/market/dashboard',
    method: 'GET',
    params: Object.keys(queryParams).length ? queryParams : undefined,
  });
}

export async function scanMarket(): Promise<ScanResult> {
  return customFetch<ScanResult>({ url: '/market/scan', method: 'POST' });
}

export async function getMarketInsights(params?: {
  insight_type?: string;
  min_relevance?: number;
  limit?: number;
}): Promise<MarketInsight[]> {
  const queryParams: Record<string, string> = {};
  if (params?.insight_type) queryParams.insight_type = params.insight_type;
  if (params?.min_relevance !== undefined) queryParams.min_relevance = String(params.min_relevance);
  if (params?.limit !== undefined) queryParams.limit = String(params.limit);
  return customFetch<MarketInsight[]>({
    url: '/market/insights',
    method: 'GET',
    params: Object.keys(queryParams).length ? queryParams : undefined,
  });
}

export async function getMarketAlerts(params?: {
  acknowledged?: boolean;
}): Promise<MarketAlert[]> {
  const queryParams: Record<string, string> = {};
  if (params?.acknowledged !== undefined) queryParams.acknowledged = String(params.acknowledged);
  return customFetch<MarketAlert[]>({
    url: '/market/alerts',
    method: 'GET',
    params: Object.keys(queryParams).length ? queryParams : undefined,
  });
}

export async function addMarketSource(params: {
  name: string;
  url: string;
  source_type?: string;
}): Promise<MarketSource> {
  const queryParams: Record<string, string> = {
    name: params.name,
    url: params.url,
  };
  if (params.source_type) queryParams.source_type = params.source_type;
  return customFetch<MarketSource>({
    url: '/market/sources',
    method: 'POST',
    params: queryParams,
  });
}

export async function getCompetitors(): Promise<CompetitorsResponse> {
  return customFetch<CompetitorsResponse>({ url: '/competitors', method: 'GET' });
}

export async function addCompetitor(params: {
  name: string;
  krs_number?: string;
  industry?: string;
  watch_level?: string;
}): Promise<{ id: number; name: string; watch_level: string }> {
  const queryParams: Record<string, string> = { name: params.name };
  if (params.krs_number) queryParams.krs_number = params.krs_number;
  if (params.industry) queryParams.industry = params.industry;
  if (params.watch_level) queryParams.watch_level = params.watch_level;
  return customFetch<{ id: number; name: string; watch_level: string }>({
    url: '/competitors',
    method: 'POST',
    params: queryParams,
  });
}

export async function scanCompetitors(): Promise<CompetitorScanResult> {
  return customFetch<CompetitorScanResult>({ url: '/competitors/scan', method: 'POST' });
}

export async function getCompetitorAnalysis(competitorId: number): Promise<SwotAnalysis> {
  return customFetch<SwotAnalysis>({
    url: `/competitors/${competitorId}/analysis`,
    method: 'GET',
  });
}

export async function getCompetitorSignals(params?: {
  competitor_id?: number;
  signal_type?: string;
  days?: number;
}): Promise<CompetitorSignal[]> {
  const queryParams: Record<string, string> = {};
  if (params?.competitor_id !== undefined) queryParams.competitor_id = String(params.competitor_id);
  if (params?.signal_type) queryParams.signal_type = params.signal_type;
  if (params?.days !== undefined) queryParams.days = String(params.days);
  return customFetch<CompetitorSignal[]>({
    url: '/competitors/signals',
    method: 'GET',
    params: Object.keys(queryParams).length ? queryParams : undefined,
  });
}
