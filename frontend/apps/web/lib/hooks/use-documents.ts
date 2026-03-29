'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  searchDocuments,
  fetchDocumentsList,
  fetchDocumentDetail,
  fetchIngestionDashboard,
  uploadDocument,
} from '@gilbertus/api-client';
import type {
  DocumentSearchResult,
  DocumentListResponse,
  DocumentDetail,
  IngestionDashboard,
  DocumentUploadResponse,
} from '@gilbertus/api-client';

export function useDocumentSearch(
  query: string,
  sourceTypes?: string[],
  dateFrom?: string,
  dateTo?: string,
) {
  return useQuery<DocumentSearchResult>({
    queryKey: ['document-search', query, sourceTypes, dateFrom, dateTo],
    queryFn: () =>
      searchDocuments({
        query,
        source_types: sourceTypes,
        date_from: dateFrom,
        date_to: dateTo,
      }),
    enabled: query.length >= 2,
    staleTime: 30_000,
  });
}

export function useDocumentsList(params?: {
  source_type?: string;
  classification?: string;
  page?: number;
}) {
  return useQuery<DocumentListResponse>({
    queryKey: ['documents-list', params],
    queryFn: () => fetchDocumentsList(params),
    staleTime: 60_000,
  });
}

export function useDocumentDetail(id: number) {
  return useQuery<DocumentDetail | null>({
    queryKey: ['document-detail', id],
    queryFn: () => fetchDocumentDetail(id),
    enabled: !!id,
    staleTime: 60_000,
  });
}

export function useIngestionDashboard() {
  return useQuery<IngestionDashboard>({
    queryKey: ['ingestion-dashboard'],
    queryFn: fetchIngestionDashboard,
    staleTime: 30_000,
  });
}

export function useDocumentUpload() {
  const queryClient = useQueryClient();

  return useMutation<DocumentUploadResponse, Error, { file: File; classification?: string }>({
    mutationFn: ({ file, classification }) => uploadDocument(file, classification),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents-list'] });
      queryClient.invalidateQueries({ queryKey: ['ingestion-dashboard'] });
    },
  });
}
