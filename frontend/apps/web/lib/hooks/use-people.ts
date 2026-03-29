import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchPeople,
  fetchPerson,
  fetchScorecard,
  fetchSentiment,
  fetchDelegation,
  fetchNetwork,
  triggerEvaluation,
  createPerson,
  updatePerson,
  addTimelineEvent,
  addRoleHistory,
  addOpenLoop,
  closeOpenLoop,
  fetchWellbeing,
  fetchSentimentAlerts,
} from '@gilbertus/api-client';
import type {
  PersonCreate,
  PersonUpdate,
  EvaluateRequest,
  TimelineEventCreate,
  RoleHistoryCreate,
  OpenLoopCreate,
} from '@gilbertus/api-client';
import { usePeopleStore } from '../stores/people-store';

// List hook with client-side search/filter
export function usePeople() {
  const { filterType, filterStatus } = usePeopleStore();
  return useQuery({
    queryKey: ['people', filterType, filterStatus],
    queryFn: () => fetchPeople({ type: filterType ?? undefined, status: filterStatus ?? undefined }),
  });
}

// Profile hook
export function usePerson(slug: string) {
  return useQuery({
    queryKey: ['person', slug],
    queryFn: () => fetchPerson(slug),
    enabled: !!slug,
  });
}

// Scorecard hook
export function useScorecard(slug: string) {
  return useQuery({
    queryKey: ['scorecard', slug],
    queryFn: () => fetchScorecard(slug),
    enabled: !!slug,
  });
}

// Sentiment hook (lazy — only when tab selected)
export function useSentiment(slug: string, enabled: boolean, weeks?: number) {
  return useQuery({
    queryKey: ['sentiment', slug, weeks],
    queryFn: () => fetchSentiment(slug, weeks ?? 8),
    enabled: enabled && !!slug,
  });
}

// Delegation hook (lazy)
export function useDelegation(slug: string, enabled: boolean, months?: number) {
  return useQuery({
    queryKey: ['delegation', slug, months],
    queryFn: () => fetchDelegation(slug, months ?? 3),
    enabled: enabled && !!slug,
  });
}

// Network hook
export function useNetwork() {
  return useQuery({
    queryKey: ['network'],
    queryFn: fetchNetwork,
  });
}

// Wellbeing hook
export function useWellbeing(weeks?: number) {
  return useQuery({
    queryKey: ['wellbeing', weeks],
    queryFn: () => fetchWellbeing(weeks ?? 8),
  });
}

// Sentiment alerts
export function useSentimentAlerts() {
  return useQuery({
    queryKey: ['sentiment-alerts'],
    queryFn: fetchSentimentAlerts,
  });
}

// === Mutations ===

export function useCreatePerson() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: PersonCreate) => createPerson(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['people'] }),
  });
}

export function useUpdatePerson(slug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: PersonUpdate) => updatePerson(slug, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['people'] });
      qc.invalidateQueries({ queryKey: ['person', slug] });
    },
  });
}

export function useEvaluatePerson() {
  return useMutation({
    mutationFn: (data: EvaluateRequest) => triggerEvaluation(data),
  });
}

export function useAddTimeline(slug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: TimelineEventCreate) => addTimelineEvent(slug, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['person', slug] }),
  });
}

export function useAddRole(slug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: RoleHistoryCreate) => addRoleHistory(slug, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['person', slug] }),
  });
}

export function useAddLoop(slug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: OpenLoopCreate) => addOpenLoop(slug, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['person', slug] }),
  });
}

export function useCloseLoop(slug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (loopId: number) => closeOpenLoop(slug, loopId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['person', slug] }),
  });
}
