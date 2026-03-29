export type OmniusTenant = 'reh' | 'ref';

export interface OmniusTenantStatus {
  tenant: string;
  company: string;
  users: number;
  documents: number;
  chunks: number;
  pending_tasks: number;
}

export interface OperatorTask {
  id: number;
  title: string;
  description: string;
  source: string;
  status: 'pending' | 'in_progress' | 'done' | 'blocked';
  result: string | null;
  created: string;
  completed: string | null;
  assigned_to: string;
}

export interface CreateTaskRequest {
  title: string;
  description: string;
  source?: string;
  assigned_to?: string;
}

export interface UpdateTaskRequest {
  status: 'pending' | 'in_progress' | 'done' | 'blocked';
  result?: string;
}

export interface OmniusConfigEntry {
  key: string;
  value: unknown;
  pushed_by: string;
  updated_at: string;
}

export interface SyncTriggerResponse {
  status: 'queued';
  source: string;
}
