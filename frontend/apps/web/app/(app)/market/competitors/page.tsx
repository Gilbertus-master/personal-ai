'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Radar, Plus, Search, X } from 'lucide-react';
import { useCompetitors, useAddCompetitor, useScanCompetitors } from '@/lib/hooks/use-market';
import { RbacGate, CompetitorTable, cn } from '@gilbertus/ui';

type WatchLevel = 'active' | 'passive' | 'archived';

function CompetitorsContent() {
  const router = useRouter();
  const competitors = useCompetitors();
  const addMutation = useAddCompetitor();
  const scanMutation = useScanCompetitors();

  const [showDialog, setShowDialog] = useState(false);
  const [form, setForm] = useState({
    name: '',
    krs_number: '',
    industry: 'energia',
    watch_level: 'active' as WatchLevel,
  });

  const data = competitors.data;
  const list = data?.competitors ?? [];
  const total = data?.total ?? 0;
  const activeCount = data?.active_count ?? 0;
  const totalSignals = list.reduce((sum, c) => sum + c.recent_signals_30d, 0);

  function handleAdd() {
    if (!form.name.trim()) return;
    addMutation.mutate(
      {
        name: form.name.trim(),
        krs_number: form.krs_number.trim() || undefined,
        industry: form.industry,
        watch_level: form.watch_level,
      },
      {
        onSuccess: () => {
          setShowDialog(false);
          setForm({ name: '', krs_number: '', industry: 'energia', watch_level: 'active' });
        },
      },
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-[var(--text)]">Konkurencja</h1>
        <div className="flex items-center gap-2">
          <button
            onClick={() => scanMutation.mutate()}
            disabled={scanMutation.isPending}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
              'bg-[var(--surface)] border border-[var(--border)] text-[var(--text)] hover:bg-[var(--surface-hover)]',
              scanMutation.isPending && 'opacity-50 cursor-not-allowed',
            )}
          >
            <Search size={14} className={scanMutation.isPending ? 'animate-spin' : ''} />
            {scanMutation.isPending ? 'Skanowanie...' : 'Skanuj'}
          </button>
          <button
            onClick={() => setShowDialog(true)}
            className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:opacity-90"
          >
            <Plus size={14} />
            Dodaj
          </button>
        </div>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Konkurenci', value: total },
          { label: 'Aktywni', value: activeCount },
          { label: 'Sygnały (30d)', value: totalSignals },
        ].map((kpi) => (
          <div
            key={kpi.label}
            className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4"
          >
            <p className="text-xs text-[var(--text-secondary)]">{kpi.label}</p>
            <p className="mt-1 text-2xl font-bold text-[var(--text)]">{kpi.value}</p>
          </div>
        ))}
      </div>

      {/* Table */}
      {competitors.isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-12 animate-pulse rounded-lg bg-[var(--surface)]" />
          ))}
        </div>
      ) : (
        <CompetitorTable
          competitors={list}
          onRowClick={(id) => router.push(`/market/competitors/${id}`)}
        />
      )}

      {/* Add dialog */}
      {showDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-md rounded-xl border border-[var(--border)] bg-[var(--bg)] p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-[var(--text)]">Dodaj konkurenta</h2>
              <button
                onClick={() => setShowDialog(false)}
                className="text-[var(--text-secondary)] hover:text-[var(--text)]"
              >
                <X size={18} />
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
                  Nazwa *
                </label>
                <input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="Nazwa firmy"
                  className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-secondary)] focus:border-[var(--accent)] focus:outline-none"
                />
              </div>

              <div>
                <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
                  KRS
                </label>
                <input
                  value={form.krs_number}
                  onChange={(e) => setForm({ ...form, krs_number: e.target.value })}
                  placeholder="Numer KRS"
                  className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-secondary)] focus:border-[var(--accent)] focus:outline-none"
                />
              </div>

              <div>
                <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
                  Branża
                </label>
                <input
                  value={form.industry}
                  onChange={(e) => setForm({ ...form, industry: e.target.value })}
                  className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-secondary)] focus:border-[var(--accent)] focus:outline-none"
                />
              </div>

              <div>
                <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
                  Monitoring
                </label>
                <select
                  value={form.watch_level}
                  onChange={(e) => setForm({ ...form, watch_level: e.target.value as WatchLevel })}
                  className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text)] focus:border-[var(--accent)] focus:outline-none"
                >
                  <option value="active">Aktywny</option>
                  <option value="passive">Pasywny</option>
                  <option value="archived">Archiwalny</option>
                </select>
              </div>
            </div>

            <div className="mt-5 flex justify-end gap-2">
              <button
                onClick={() => setShowDialog(false)}
                className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--surface)]"
              >
                Anuluj
              </button>
              <button
                onClick={handleAdd}
                disabled={!form.name.trim() || addMutation.isPending}
                className={cn(
                  'rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white transition-colors hover:opacity-90',
                  (!form.name.trim() || addMutation.isPending) && 'opacity-50 cursor-not-allowed',
                )}
              >
                {addMutation.isPending ? 'Dodawanie...' : 'Dodaj'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function CompetitorsPage() {
  return (
    <RbacGate
      roles={['owner', 'board', 'ceo', 'gilbertus_admin']}
      permission="data:read:all"
      fallback={
        <div className="flex items-center justify-center h-full">
          <p className="text-[var(--text-secondary)]">Brak dostępu do danych konkurencji</p>
        </div>
      }
    >
      <CompetitorsContent />
    </RbacGate>
  );
}
