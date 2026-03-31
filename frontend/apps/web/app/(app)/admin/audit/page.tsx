'use client';

import { RbacGate, AuditLog } from '@gilbertus/ui';
import { useAuditLog } from '@/lib/hooks/use-admin';
import { useAdminStore } from '@/lib/stores/admin-store';

export default function AuditPage() {
  return (
    <RbacGate roles={['owner', 'gilbertus_admin']} fallback={<p className="p-6 text-[var(--text-secondary)]">Brak dostępu</p>}>
      <AuditPageContent />
    </RbacGate>
  );
}

function AuditPageContent() {
  const { data, isLoading } = useAuditLog();
  const store = useAdminStore();
  return (
    <AuditLog
      entries={data ?? []}
      isLoading={isLoading}
      filters={{
        user: store.auditUserFilter,
        action: store.auditActionFilter,
        result: store.auditResultFilter,
      }}
      onFilterChange={(f) => {
        if ('user' in f) store.setAuditUserFilter(f.user ?? null);
        if ('action' in f) store.setAuditActionFilter(f.action ?? null);
        if ('result' in f) store.setAuditResultFilter(f.result ?? null);
      }}
    />
  );
}
