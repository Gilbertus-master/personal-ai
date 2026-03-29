'use client';

import {
  RbacGate,
  TenantOverview,
  OperatorTasks,
  CrossTenantAudit,
  ConfigPush,
  SyncTrigger,
} from '@gilbertus/ui';
import { useAdminStore } from '@/lib/stores/admin-store';
import {
  useBothTenantsStatus,
  useOperatorTasks,
  useCreateOperatorTask,
  useUpdateOperatorTask,
  useTenantAuditLog,
  useTenantConfig,
  usePushTenantConfig,
  useTriggerSync,
} from '@/lib/hooks/use-omnius-bridge';

export default function OmniusBridgePage() {
  return (
    <RbacGate
      roles={['gilbertus_admin']}
      fallback={<p className="p-6 text-[var(--text-secondary)]">Brak dostępu</p>}
    >
      <OmniusBridgeContent />
    </RbacGate>
  );
}

const tabs = [
  { id: 'overview', label: 'Przegląd' },
  { id: 'tasks', label: 'Zadania' },
  { id: 'audit', label: 'Audit' },
  { id: 'config', label: 'Konfiguracja' },
  { id: 'sync', label: 'Synchronizacja' },
] as const;

function OmniusBridgeContent() {
  const {
    omniusActiveTab: activeTab,
    setOmniusActiveTab: setActiveTab,
    omniusActiveTenant: tenant,
    setOmniusActiveTenant: setTenant,
  } = useAdminStore();

  const tenants = useBothTenantsStatus();
  const tasksQuery = useOperatorTasks(tenant);
  const createTask = useCreateOperatorTask(tenant);
  const updateTask = useUpdateOperatorTask(tenant);
  const audit = useTenantAuditLog(tenant);
  const config = useTenantConfig(tenant);
  const pushConfig = usePushTenantConfig(tenant);
  const triggerSync = useTriggerSync(tenant);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-[var(--text)]">Omnius Bridge</h1>

      {/* Tab bar */}
      <div className="flex gap-1 rounded-lg bg-[var(--surface)] p-1">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === t.id
                ? 'bg-[var(--accent)] text-white'
                : 'text-[var(--text-secondary)] hover:text-[var(--text)]'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Content */}
      {activeTab === 'overview' && (
        <TenantOverview reh={tenants.reh} refTenant={tenants.ref} />
      )}
      {activeTab === 'tasks' && (
        <OperatorTasks
          activeTenant={tenant}
          onTenantChange={setTenant}
          tasks={tasksQuery.data ?? []}
          isLoading={tasksQuery.isLoading}
          onCreate={(d) => createTask.mutate(d)}
          isCreating={createTask.isPending}
          onUpdateStatus={(id, d) => updateTask.mutate({ taskId: id, data: d })}
        />
      )}
      {activeTab === 'audit' && (
        <CrossTenantAudit
          activeTenant={tenant}
          onTenantChange={setTenant}
          entries={audit.data ?? []}
          isLoading={audit.isLoading}
        />
      )}
      {activeTab === 'config' && (
        <ConfigPush
          activeTenant={tenant}
          onTenantChange={setTenant}
          config={config.data ?? []}
          isLoading={config.isLoading}
          onPush={(k, v) => pushConfig.mutate({ key: k, value: v })}
          isPushing={pushConfig.isPending}
        />
      )}
      {activeTab === 'sync' && (
        <SyncTrigger
          onSync={(t, s) => triggerSync.mutate(s)}
          isSyncing={triggerSync.isPending}
        />
      )}
    </div>
  );
}
