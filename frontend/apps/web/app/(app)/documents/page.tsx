'use client';

import { useState, useCallback } from 'react';
import { RbacGate } from '@gilbertus/ui';
import {
  SearchBar,
  SourceTypeFilter,
  DocumentResultCard,
  DocumentsTable,
  UploadModal,
  IngestionStatus,
  DocumentDetailPanel,
} from '@gilbertus/ui/documents';
import {
  useDocumentSearch,
  useDocumentsList,
  useDocumentDetail,
  useIngestionDashboard,
  useDocumentUpload,
} from '@/lib/hooks/use-documents';
import { useDocumentsStore } from '@/lib/stores/documents-store';

export default function DocumentsPage() {
  const store = useDocumentsStore();

  // Queries
  const {
    data: searchResults,
    isLoading: searchLoading,
  } = useDocumentSearch(
    store.searchQuery,
    store.sourceTypeFilter.length > 0 ? store.sourceTypeFilter : undefined,
    store.dateFrom ?? undefined,
    store.dateTo ?? undefined,
  );
  const {
    data: documentsListData,
    isLoading: listLoading,
    error: listError,
  } = useDocumentsList(
    store.browseSourceType
      ? { source_type: store.browseSourceType }
      : undefined,
  );
  const { data: documentDetail, isLoading: detailLoading } = useDocumentDetail(
    store.selectedDocumentId ?? 0,
  );
  const { data: ingestionData, isLoading: ingestionLoading } =
    useIngestionDashboard();

  // Mutations
  const uploadMutation = useDocumentUpload();

  // Local modal state
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState(false);

  const handleUpload = useCallback(
    (file: File, classification?: string) => {
      uploadMutation.mutate(
        { file, classification },
        {
          onSuccess: () => {
            setUploadOpen(false);
            setUploadSuccess(true);
            store.setActiveTab('ingestion');
            setTimeout(() => setUploadSuccess(false), 3000);
          },
        },
      );
    },
    [uploadMutation, store],
  );

  const tabs = [
    { id: 'search' as const, label: 'Szukaj' },
    { id: 'browse' as const, label: 'Przeglądaj' },
    { id: 'ingestion' as const, label: 'Ingestion' },
  ];

  const isBrowse404 =
    listError && 'status' in (listError as unknown as Record<string, unknown>) &&
    (listError as unknown as Record<string, unknown>).status === 404;

  return (
    <RbacGate permission="documents">
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold" style={{ color: 'var(--text)' }}>
            Dokumenty
          </h1>
          <RbacGate roles={['ceo', 'board', 'director']}>
            <button
              onClick={() => setUploadOpen(true)}
              className="rounded-md px-4 py-1.5 text-sm font-medium transition-colors"
              style={{ backgroundColor: 'var(--accent)', color: '#fff' }}
            >
              Wgraj dokument
            </button>
          </RbacGate>
        </div>

        {/* Success banner */}
        {uploadSuccess && (
          <div className="rounded-lg border border-green-500/30 bg-green-500/10 px-4 py-2.5 text-sm text-green-400">
            Dokument wgrany
          </div>
        )}

        {/* Tabs */}
        <div>
          <div
            className="inline-flex rounded-md border"
            style={{ borderColor: 'var(--border)' }}
          >
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => store.setActiveTab(tab.id)}
                className="px-4 py-1.5 text-sm font-medium transition-colors first:rounded-l-md last:rounded-r-md"
                style={{
                  backgroundColor:
                    store.activeTab === tab.id ? 'var(--accent)' : 'var(--surface)',
                  color: store.activeTab === tab.id ? '#fff' : 'var(--text-secondary)',
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Search tab */}
        {store.activeTab === 'search' && (
          <div className="space-y-4">
            <SearchBar
              query={store.searchQuery}
              onChange={store.setSearchQuery}
              isLoading={searchLoading}
            />
            <SourceTypeFilter
              selected={store.sourceTypeFilter}
              onChange={store.setSourceTypeFilter}
            />
            <div className="flex gap-4">
              <input
                type="date"
                value={store.dateFrom ?? ''}
                onChange={(e) =>
                  store.setDateRange(e.target.value || null, store.dateTo)
                }
                className="rounded-md border px-3 py-1.5 text-sm"
                style={{
                  backgroundColor: 'var(--surface)',
                  borderColor: 'var(--border)',
                  color: 'var(--text)',
                }}
                placeholder="Od"
              />
              <input
                type="date"
                value={store.dateTo ?? ''}
                onChange={(e) =>
                  store.setDateRange(store.dateFrom, e.target.value || null)
                }
                className="rounded-md border px-3 py-1.5 text-sm"
                style={{
                  backgroundColor: 'var(--surface)',
                  borderColor: 'var(--border)',
                  color: 'var(--text)',
                }}
                placeholder="Do"
              />
            </div>

            {searchResults && (
              <div className="mt-2 space-y-4">
                {searchResults.answer && (
                  <div
                    className="rounded-lg p-4 text-sm whitespace-pre-wrap"
                    style={{
                      backgroundColor: 'var(--surface)',
                      color: 'var(--text)',
                    }}
                  >
                    {searchResults.answer}
                  </div>
                )}
                {searchResults.matches?.map((match, i) => (
                  <DocumentResultCard
                    key={match.chunk_id ?? i}
                    source={searchResults.sources?.[i]}
                    match={match}
                    onClick={(id) => store.setSelectedDocumentId(id)}
                  />
                ))}
              </div>
            )}

            {store.searchQuery.length >= 2 && !searchLoading && !searchResults?.matches?.length && (
              <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                Brak wynikow dla podanego zapytania.
              </p>
            )}
          </div>
        )}

        {/* Browse tab */}
        {store.activeTab === 'browse' && (
          <div className="space-y-4">
            <SourceTypeFilter
              selected={store.browseSourceType ? [store.browseSourceType] : []}
              onChange={(types) => store.setBrowseSourceType(types[0] || null)}
            />

            {isBrowse404 ? (
              <div
                className="rounded-lg border px-4 py-3 text-sm"
                style={{
                  borderColor: 'var(--border)',
                  backgroundColor: 'var(--surface)',
                  color: 'var(--text-secondary)',
                }}
              >
                Ta funkcja wymaga aktualizacji backendu. Endpoint w przygotowaniu.
              </div>
            ) : (
              <DocumentsTable
                documents={documentsListData?.documents ?? []}
                onRowClick={(id) => store.setSelectedDocumentId(id)}
                isLoading={listLoading}
              />
            )}
          </div>
        )}

        {/* Ingestion tab */}
        {store.activeTab === 'ingestion' && (
          <IngestionStatus
            dashboard={ingestionData ?? { sources: {}, extraction_backlogs: {}, dlq_stats: { total: 0, by_error: {} }, guardian_alerts: { total: 0, critical: 0 } }}
            isLoading={ingestionLoading}
          />
        )}

        {/* Upload modal */}
        <UploadModal
          open={uploadOpen}
          onClose={() => setUploadOpen(false)}
          onUpload={handleUpload}
          isUploading={uploadMutation.isPending}
        />

        {/* Document detail panel */}
        {store.selectedDocumentId && (
          <DocumentDetailPanel
            document={documentDetail ?? null}
            isLoading={detailLoading}
            onClose={() => store.setSelectedDocumentId(null)}
          />
        )}
      </div>
    </RbacGate>
  );
}
