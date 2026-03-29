import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getMarketDashboard,
  scanMarket,
  getMarketInsights,
  getMarketAlerts,
  addMarketSource,
  getCompetitors,
  addCompetitor,
  scanCompetitors,
  getCompetitorAnalysis,
  getCompetitorSignals,
} from '@gilbertus/api-client';
import type { MarketSource, CompetitorSignal } from '@gilbertus/api-client';

// === Query hooks ===

export function useMarketDashboard(days?: number) {
  return useQuery({
    queryKey: ['market-dashboard', days],
    queryFn: () => getMarketDashboard(days !== undefined ? { days } : undefined),
    staleTime: 60_000,
  });
}

export function useMarketInsights(type?: string, minRelevance?: number, limit?: number) {
  return useQuery({
    queryKey: ['market-insights', type, minRelevance, limit],
    queryFn: () =>
      getMarketInsights({
        insight_type: type,
        min_relevance: minRelevance,
        limit,
      }),
  });
}

export function useMarketAlerts(acknowledged?: boolean) {
  return useQuery({
    queryKey: ['market-alerts', acknowledged],
    queryFn: () => getMarketAlerts(acknowledged !== undefined ? { acknowledged } : undefined),
  });
}

export function useCompetitors() {
  return useQuery({
    queryKey: ['competitors'],
    queryFn: getCompetitors,
  });
}

export function useCompetitorAnalysis(competitorId: number) {
  return useQuery({
    queryKey: ['competitor-analysis', competitorId],
    queryFn: () => getCompetitorAnalysis(competitorId),
    enabled: !!competitorId,
  });
}

export function useCompetitorSignals(params?: {
  competitor_id?: number;
  signal_type?: string;
  days?: number;
}) {
  return useQuery({
    queryKey: ['competitor-signals', params],
    queryFn: () => getCompetitorSignals(params),
  });
}

// === Mutation hooks ===

export function useScanMarket() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: scanMarket,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['market-dashboard'] });
      qc.invalidateQueries({ queryKey: ['market-insights'] });
      qc.invalidateQueries({ queryKey: ['market-alerts'] });
    },
  });
}

export function useAddMarketSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; url: string; source_type?: string }) =>
      addMarketSource(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['market-dashboard'] }),
  });
}

export function useAddCompetitor() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      name: string;
      krs_number?: string;
      industry?: string;
      watch_level?: string;
    }) => addCompetitor(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['competitors'] }),
  });
}

export function useScanCompetitors() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: scanCompetitors,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['competitors'] });
      qc.invalidateQueries({ queryKey: ['competitor-signals'] });
    },
  });
}
