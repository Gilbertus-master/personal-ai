'use client';

import { useEffect, useState } from 'react';
import { useSession } from 'next-auth/react';
import { useRole, usePermissions } from '@gilbertus/rbac';
import { useBrief, useAlerts, useStatus } from '@/lib/hooks/use-dashboard';

export default function TestDataPage() {
  const { data: session, status: sessionStatus } = useSession();
  const { role, roleLevel } = useRole();
  const { permissions } = usePermissions();

  // Direct fetch test
  const [directResult, setDirectResult] = useState<string>('loading...');
  useEffect(() => {
    const apiBase = `http://${window.location.hostname}:8000`;
    fetch(`${apiBase}/status`)
      .then(r => r.json())
      .then(d => setDirectResult(`OK — ${d.db?.documents} docs, ${d.db?.chunks} chunks`))
      .catch(e => setDirectResult(`ERROR: ${e.message}`));
  }, []);

  // React Query hooks (same as dashboard)
  const brief = useBrief();
  const alerts = useAlerts();
  const status = useStatus();

  // Check what BASE_URL customFetch uses
  const [baseUrl, setBaseUrl] = useState<string>('?');
  useEffect(() => {
    import('@gilbertus/api-client').then((mod: any) => {
      // Try to access the internal BASE_URL
      setBaseUrl(mod.getApiKey !== undefined ? 'module loaded' : 'no getApiKey');
    });
  }, []);

  return (
    <div className="space-y-4 max-w-3xl">
      <h1 className="text-2xl font-bold text-[var(--text)]">Debug: Data Loading</h1>

      <Section title="1. Session & Auth">
        <Row label="session status" value={sessionStatus} />
        <Row label="session data" value={JSON.stringify(session)?.substring(0, 200) ?? 'null'} />
        <Row label="role" value={role} />
        <Row label="roleLevel" value={String(roleLevel)} />
        <Row label="permissions count" value={String(permissions.length)} />
      </Section>

      <Section title="2. Direct Fetch (window.fetch)">
        <Row label="result" value={directResult} />
      </Section>

      <Section title="3. React Query: useBrief()">
        <Row label="status" value={brief.status} />
        <Row label="isLoading" value={String(brief.isLoading)} />
        <Row label="isFetching" value={String(brief.isFetching)} />
        <Row label="isError" value={String(brief.isError)} />
        <Row label="error" value={brief.error?.message ?? 'none'} />
        <Row label="data keys" value={brief.data ? Object.keys(brief.data).join(', ') : 'no data'} />
        <Row label="data preview" value={JSON.stringify(brief.data)?.substring(0, 150) ?? 'null'} />
      </Section>

      <Section title="4. React Query: useAlerts()">
        <Row label="status" value={alerts.status} />
        <Row label="isError" value={String(alerts.isError)} />
        <Row label="error" value={alerts.error?.message ?? 'none'} />
        <Row label="data" value={alerts.data ? `${alerts.data.alerts?.length ?? 0} alerts` : 'no data'} />
      </Section>

      <Section title="5. React Query: useStatus()">
        <Row label="status" value={status.status} />
        <Row label="isError" value={String(status.isError)} />
        <Row label="error" value={status.error?.message ?? 'none'} />
        <Row label="data" value={status.data ? `${status.data.db?.documents ?? '?'} docs` : 'no data'} />
      </Section>

      <Section title="6. API Client Module">
        <Row label="module" value={baseUrl} />
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
      <h3 className="mb-3 text-sm font-semibold text-[var(--accent)]">{title}</h3>
      <div className="space-y-1">{children}</div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  const isError = value.includes('ERROR') || value.includes('error') || value === 'true';
  const isOk = value.includes('OK') || value === 'success' || value === 'false' || value === 'owner';
  return (
    <div className="flex gap-2 text-sm font-mono">
      <span className="text-[var(--text-secondary)] min-w-[140px]">{label}:</span>
      <span className={isError ? 'text-red-400' : isOk ? 'text-green-400' : 'text-[var(--text)]'}>
        {value}
      </span>
    </div>
  );
}
