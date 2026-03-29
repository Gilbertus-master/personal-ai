import { customFetch } from './base';
import type {
  AskRequest,
  AskResponse,
  ConversationWindow,
} from './chat-types';

export async function askGilbertus(
  request: AskRequest,
  signal?: AbortSignal,
): Promise<AskResponse> {
  return customFetch<AskResponse>({
    url: '/ask',
    method: 'POST',
    data: request,
    signal,
  });
}

export async function getConversationWindows(): Promise<ConversationWindow[]> {
  return customFetch<ConversationWindow[]>({
    url: '/conversation/windows',
    method: 'GET',
  });
}

export async function getBriefToday(
  signal?: AbortSignal,
): Promise<{ brief: string }> {
  return customFetch<{ brief: string }>({
    url: '/brief/today',
    method: 'GET',
    signal,
  });
}

export async function getAlerts(
  signal?: AbortSignal,
): Promise<{ alerts: unknown[] }> {
  return customFetch<{ alerts: unknown[] }>({
    url: '/alerts',
    method: 'GET',
    signal,
  });
}

export async function getCommitments(
  signal?: AbortSignal,
): Promise<{ commitments: unknown[] }> {
  return customFetch<{ commitments: unknown[] }>({
    url: '/commitments',
    method: 'GET',
    signal,
  });
}

export async function getMeetingPrep(
  signal?: AbortSignal,
): Promise<{ prep: string }> {
  return customFetch<{ prep: string }>({
    url: '/meeting-prep',
    method: 'GET',
    signal,
  });
}

export async function postTimeline(
  params: { date_from?: string; date_to?: string },
  signal?: AbortSignal,
): Promise<{ timeline: unknown[] }> {
  return customFetch<{ timeline: unknown[] }>({
    url: '/timeline',
    method: 'POST',
    data: params,
    signal,
  });
}
