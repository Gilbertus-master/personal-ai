'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchDecisions,
  createDecision,
  addOutcome,
  fetchDecisionPatterns,
  fetchDecisionIntelligence,
  runDecisionIntelligence,
} from '@gilbertus/api-client';
import type { OutcomeCreate } from '@gilbertus/api-client';

export function useDecisions(area?: string, limit?: number) {
  return useQuery({
    queryKey: ['decisions', area, limit],
    queryFn: () => fetchDecisions({ area, limit }),
    staleTime: 30_000,
  });
}

export function useDecisionPatterns() {
  return useQuery({
    queryKey: ['decision-patterns'],
    queryFn: () => fetchDecisionPatterns(),
    staleTime: 120_000,
  });
}

export function useDecisionIntelligence(months?: number) {
  return useQuery({
    queryKey: ['decision-intelligence', months],
    queryFn: () => fetchDecisionIntelligence({ months }),
    staleTime: 120_000,
  });
}

export function useCreateDecision() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: createDecision,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['decisions'] });
    },
  });
}

export function useAddOutcome() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: ({ decisionId, data }: { decisionId: number; data: OutcomeCreate }) =>
      addOutcome(decisionId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['decisions'] });
    },
  });
}

export function useRunIntelligence() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: runDecisionIntelligence,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['decision-intelligence'] });
    },
  });
}
