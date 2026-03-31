'use client';

import { useState } from 'react';
import { Plus } from 'lucide-react';
import { RbacGate } from '@gilbertus/ui';
import { DocumentsTable, DocumentActions, GenerateDocModal } from '@gilbertus/ui/compliance';
import {
  useDocuments,
  useStaleDocuments,
  useMatters,
  useGenerateDocument,
  useApproveDocument,
  useSignDocument,
} from '@/lib/hooks/use-compliance';
import { useComplianceStore } from '@/lib/stores/compliance-store';

export default function DocumentsPage() {
  const [showGenerate, setShowGenerate] = useState(false);
  const documents = useDocuments();
  const staleDocuments = useStaleDocuments();
  const matters = useMatters();
  const generateDocument = useGenerateDocument();
  const approveDocument = useApproveDocument();
  const signDocument = useSignDocument();
  const store = useComplianceStore();

  return (
    <RbacGate roles={['owner', 'ceo', 'board', 'director', 'gilbertus_admin']}>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-[var(--text)]">Dokumenty compliance</h1>
          <RbacGate roles={['owner', 'ceo', 'gilbertus_admin']}>
            <button
              onClick={() => setShowGenerate(true)}
              className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium text-white transition-colors"
              style={{ backgroundColor: 'var(--accent)' }}
            >
              <Plus size={16} />
              Generuj dokument
            </button>
          </RbacGate>
        </div>

        <DocumentsTable
          documents={documents.data?.documents ?? []}
          staleDocuments={staleDocuments.data ?? []}
          isLoading={documents.isLoading}
          showStaleOnly={store.showStaleOnly}
          areaFilter={store.docArea}
          docTypeFilter={store.docType}
          statusFilter={store.docStatus}
          onAreaChange={store.setDocArea}
          onDocTypeChange={store.setDocType}
          onStatusChange={store.setDocStatus}
          onStaleToggle={store.setShowStaleOnly}
          renderActions={(doc) => (
            <RbacGate roles={['owner', 'ceo', 'gilbertus_admin']}>
              <DocumentActions
                documentId={doc.id}
                currentStatus={doc.status}
                signatureStatus={doc.signature_status}
                onApprove={(id) => approveDocument.mutate({ id })}
                onSign={(id, signerName) => signDocument.mutate({ id, signerName })}
                isApproving={approveDocument.isPending}
                isSigning={signDocument.isPending}
              />
            </RbacGate>
          )}
        />

        <GenerateDocModal
          isOpen={showGenerate}
          onClose={() => setShowGenerate(false)}
          onSubmit={(data) => {
            generateDocument.mutate(data, {
              onSuccess: () => setShowGenerate(false),
            });
          }}
          isSubmitting={generateDocument.isPending}
          matters={matters.data?.matters ?? []}
        />
      </div>
    </RbacGate>
  );
}
