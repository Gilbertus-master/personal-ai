import { customFetch } from './base';
import type {
  ActivityLogEntry,
  ActivityLogRecord,
  AnnotateParams,
  Annotation,
  ResearchParams,
  ResearchResult,
} from './activity-types';

export async function logActivity(entry: ActivityLogEntry): Promise<{ id: number; created_at: string }> {
  return customFetch({
    url: '/activity/log',
    method: 'POST',
    data: entry,
  });
}

export async function getActivityLog(params?: {
  user_id?: string;
  limit?: number;
  action_type?: string;
}): Promise<ActivityLogRecord[]> {
  const qp: Record<string, string> = {};
  if (params?.user_id) qp.user_id = params.user_id;
  if (params?.limit) qp.limit = String(params.limit);
  if (params?.action_type) qp.action_type = params.action_type;
  return customFetch({
    url: '/activity/log',
    method: 'GET',
    params: Object.keys(qp).length ? qp : undefined,
  });
}

export async function annotateItem(params: AnnotateParams): Promise<{ id: number; created_at: string }> {
  return customFetch({
    url: '/items/annotate',
    method: 'POST',
    data: params,
  });
}

export async function getItemAnnotations(item_type: string, item_id: string): Promise<Annotation[]> {
  return customFetch({
    url: `/items/${encodeURIComponent(item_type)}/${encodeURIComponent(item_id)}/annotations`,
    method: 'GET',
  });
}

export async function researchItem(params: ResearchParams): Promise<ResearchResult> {
  return customFetch({
    url: '/items/research',
    method: 'POST',
    data: params,
  });
}
