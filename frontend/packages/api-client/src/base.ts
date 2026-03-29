declare const process: { env: Record<string, string | undefined> } | undefined;

const BASE_URL =
  typeof process !== 'undefined'
    ? process.env.NEXT_PUBLIC_GILBERTUS_API_URL ?? 'http://127.0.0.1:8000'
    : 'http://127.0.0.1:8000';

let apiKey: string | null = null;

export function setApiKey(key: string): void {
  apiKey = key;
}

export function getApiKey(): string | null {
  return apiKey;
}

export function clearApiKey(): void {
  apiKey = null;
}

interface RequestConfig {
  url: string;
  method: string;
  params?: Record<string, string>;
  data?: unknown;
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

export async function customFetch<T>(config: RequestConfig): Promise<T> {
  const url = new URL(`${BASE_URL}${config.url}`);

  if (config.params) {
    for (const [key, value] of Object.entries(config.params)) {
      if (value !== undefined && value !== null) {
        url.searchParams.set(key, String(value));
      }
    }
  }

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...config.headers,
  };

  if (apiKey) {
    headers['X-API-Key'] = apiKey;
  }

  const response = await fetch(url.toString(), {
    method: config.method,
    headers,
    body: config.data ? JSON.stringify(config.data) : undefined,
    signal: config.signal,
  });

  if (response.status === 401) {
    clearApiKey();
    if (typeof window !== 'undefined') {
      window.location.href = '/login';
    }
    throw new Error('Unauthorized');
  }

  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}
