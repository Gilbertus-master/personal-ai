export interface SessionInfo {
  auth_type: 'api_key' | 'azure_ad' | 'dev';
  role: string;
  role_level: number;
  permissions: string[];
  tenant?: string;
  last_login?: string;
}

export interface ApiKeyInfo {
  id: number;
  name: string;
  role: string;
  user_email: string;
  is_active: boolean;
  created_at: string;
  last_used_at: string | null;
}

export interface CreateApiKeyResponse {
  status: 'created';
  key_id: number;
  api_key: string;
  warning: string;
}
