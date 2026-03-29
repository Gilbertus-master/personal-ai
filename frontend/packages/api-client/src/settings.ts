import { customFetch } from './base';
import type { ApiKeyInfo, CreateApiKeyResponse } from './settings-types';

export async function getOwnApiKeys(
  signal?: AbortSignal,
): Promise<ApiKeyInfo[]> {
  return customFetch<ApiKeyInfo[]>({
    url: '/api/v1/admin/api-keys',
    method: 'GET',
    signal,
  });
}

export async function createApiKey(
  data: { name: string; role: string; user_email: string },
  signal?: AbortSignal,
): Promise<CreateApiKeyResponse> {
  return customFetch<CreateApiKeyResponse>({
    url: '/api/v1/admin/api-keys',
    method: 'POST',
    data,
    signal,
  });
}
