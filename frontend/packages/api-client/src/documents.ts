import { customFetch, getApiKey } from './base';
import type {
  DocumentDetail,
  DocumentListResponse,
  DocumentSearchParams,
  DocumentSearchResult,
  DocumentUploadResponse,
  IngestionDashboard,
} from './documents-types';

export async function searchDocuments(
  data: DocumentSearchParams,
): Promise<DocumentSearchResult> {
  return customFetch<DocumentSearchResult>({
    url: '/ask',
    method: 'POST',
    data,
  });
}

export async function fetchDocumentsList(params?: {
  source_type?: string;
  classification?: string;
  page?: number;
  per_page?: number;
}): Promise<DocumentListResponse> {
  const queryParams: Record<string, string> = {};
  if (params?.source_type) queryParams.source_type = params.source_type;
  if (params?.classification) queryParams.classification = params.classification;
  if (params?.page !== undefined) queryParams.page = String(params.page);
  if (params?.per_page !== undefined) queryParams.per_page = String(params.per_page);

  try {
    return await customFetch<DocumentListResponse>({
      url: '/documents',
      method: 'GET',
      params: Object.keys(queryParams).length ? queryParams : undefined,
    });
  } catch (error) {
    if (error instanceof Error && error.message.includes('404')) {
      console.warn('GET /documents not available yet — backend endpoint needs to be created');
      return { documents: [], meta: { total: 0, page: 1, per_page: 20 } };
    }
    throw error;
  }
}

export async function fetchDocumentDetail(
  documentId: number,
): Promise<DocumentDetail | null> {
  try {
    return await customFetch<DocumentDetail>({
      url: `/documents/${documentId}`,
      method: 'GET',
    });
  } catch (error) {
    if (error instanceof Error && error.message.includes('404')) {
      return null;
    }
    throw error;
  }
}

declare const process: { env: Record<string, string | undefined> } | undefined;

const BASE_URL =
  typeof process !== 'undefined'
    ? process.env.NEXT_PUBLIC_GILBERTUS_API_URL ?? 'http://127.0.0.1:8000'
    : 'http://127.0.0.1:8000';

export async function uploadDocument(
  file: File,
  classification?: string,
): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  if (classification) formData.append('classification', classification);

  // Cannot use customFetch — it JSON.stringifies the body. Use raw fetch for multipart.
  const headers: Record<string, string> = {};
  const key = getApiKey();
  if (key) headers['X-API-Key'] = key;

  const response = await fetch(`${BASE_URL}/documents/upload`, {
    method: 'POST',
    headers,
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }

  return response.json() as Promise<DocumentUploadResponse>;
}

export async function fetchIngestionDashboard(): Promise<IngestionDashboard> {
  return customFetch<IngestionDashboard>({
    url: '/ingestion/dashboard',
    method: 'GET',
  });
}
