import { useQuery } from '@tanstack/react-query';
import {
  fetchSentimentAlerts,
  fetchNetwork,
  fetchResponseTracking,
  fetchBlindSpots,
  fetchDelegationStats,
  fetchCommitments,
} from '@gilbertus/api-client';

export function useSentimentAlertsSummary() {
  return useQuery({
    queryKey: ['sentiment-alerts'],
    queryFn: fetchSentimentAlerts,
  });
}

export function useCommitmentsSummary() {
  return useQuery({
    queryKey: ['commitments', 'open'],
    queryFn: () => fetchCommitments({ status: 'open', limit: 50 }),
  });
}

export function useDelegationRanking() {
  return useQuery({
    queryKey: ['delegation-stats'],
    queryFn: fetchDelegationStats,
  });
}

export function useResponseTracking(days?: number) {
  return useQuery({
    queryKey: ['response-tracking', days],
    queryFn: () => fetchResponseTracking(days ?? 30),
  });
}

export function useNetworkAnalysis() {
  return useQuery({
    queryKey: ['network'],
    queryFn: fetchNetwork,
  });
}

export function useBlindSpots() {
  return useQuery({
    queryKey: ['blind-spots'],
    queryFn: fetchBlindSpots,
  });
}
