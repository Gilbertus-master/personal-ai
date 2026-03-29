'use client';

import { useState, useCallback } from 'react';
import { usePluginProposals, useApprovePlugin, useRejectPlugin } from '@/lib/hooks/use-plugin-dev';
import { usePluginDevStore } from '@/lib/stores/plugin-dev-store';
import type { PluginProposal, GovernanceResult, ReviewResult } from '@gilbertus/api-client';

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  approved: 'bg-green-500/20 text-green-400 border-green-500/30',
  rejected: 'bg-red-500/20 text-red-400 border-red-500/30',
  developing: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  reviewing: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  deployed: 'bg-green-500/40 text-green-300 border-green-500/50',
};

const STATUS_LABELS: Record<string, string> = {
  pending: 'Oczekuje',
  approved: 'Zatwierdzony',
  rejected: 'Odrzucony',
  developing: 'W budowie',
  reviewing: 'Recenzja',
  deployed: 'Wdrozony',
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`px-2 py-0.5 rounded text-xs font-semibold uppercase border ${STATUS_COLORS[status] ?? 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30'}`}
    >
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

function GovernanceDetails({ gov }: { gov: GovernanceResult }) {
  return (
    <div className="space-y-2 text-sm">
      <h4 className="font-semibold text-zinc-300">Governance</h4>
      {gov.feasibility && (
        <div className="ml-2">
          <span className="text-zinc-400">Wykonalnosc: </span>
          <span className={gov.feasibility.possible ? 'text-green-400' : 'text-red-400'}>
            {gov.feasibility.possible ? 'TAK' : 'NIE'}
          </span>
          <span className="text-zinc-500"> ({gov.feasibility.score}) </span>
          <span className="text-zinc-400">— {gov.feasibility.reasoning}</span>
        </div>
      )}
      {gov.value && (
        <div className="ml-2">
          <span className="text-zinc-400">Wartosc: </span>
          <span className={gov.value.approved ? 'text-green-400' : 'text-red-400'}>
            {gov.value.approved ? 'TAK' : 'NIE'}
          </span>
          <span className="text-zinc-500"> ({gov.value.value_score}) </span>
          <span className="text-zinc-400">— {gov.value.reasoning}</span>
        </div>
      )}
      {gov.cost_estimate && (
        <div className="ml-2 text-zinc-400">
          Koszt: {gov.cost_estimate.development_time_hours}h dev, {gov.cost_estimate.complexity} zlozonosc
        </div>
      )}
      {gov.duplicate_check?.is_duplicate && (
        <div className="ml-2 text-red-400">
          DUPLIKAT: {gov.duplicate_check.similar_plugin} — {gov.duplicate_check.reasoning}
        </div>
      )}
      {gov.rejection_reason && (
        <div className="ml-2 text-red-400">
          Powod odrzucenia: {gov.rejection_reason}
        </div>
      )}
    </div>
  );
}

function ReviewDetails({ review }: { review: ReviewResult }) {
  return (
    <div className="space-y-2 text-sm">
      <h4 className="font-semibold text-zinc-300">Recenzja kodu</h4>
      <div className="ml-2">
        <span className="text-zinc-400">Wynik: </span>
        <span className={review.passed ? 'text-green-400' : 'text-red-400'}>
          {review.passed ? 'POZYTYWNY' : 'NEGATYWNY'}
        </span>
        <span className="text-zinc-500">
          {' '}| Bezpieczenstwo: {review.security_score} | Jakosc: {review.quality_score} | Testy: {review.tests_passed}/{review.tests_total}
        </span>
      </div>
      {review.findings?.length > 0 && (
        <div className="ml-2 space-y-1">
          {review.findings.map((f, i) => (
            <div
              key={i}
              className={
                f.severity === 'critical' || f.severity === 'high'
                  ? 'text-red-400'
                  : 'text-zinc-500'
              }
            >
              [{f.severity}] {f.title}: {f.description}
              {f.file && <span className="text-zinc-600"> ({f.file}:{f.line})</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function PluginsPage() {
  const store = usePluginDevStore();
  const { data: proposals, isLoading } = usePluginProposals({
    tenant: store.selectedTenant ?? undefined,
    status: store.statusFilter ?? undefined,
  });
  const approveMutation = useApprovePlugin();
  const rejectMutation = useRejectPlugin();
  const [rejectReason, setRejectReason] = useState('');
  const [showRejectInput, setShowRejectInput] = useState<number | null>(null);

  const handleApprove = useCallback(
    (id: number, tenant: string) => {
      approveMutation.mutate({ proposalId: id, data: { tenant } });
    },
    [approveMutation],
  );

  const handleReject = useCallback(
    (id: number, tenant: string) => {
      rejectMutation.mutate(
        { proposalId: id, data: { tenant, reason: rejectReason } },
        {
          onSuccess: () => {
            setRejectReason('');
            setShowRejectInput(null);
          },
        },
      );
    },
    [rejectMutation, rejectReason],
  );

  const tenants = ['reh', 'ref'];
  const statuses = ['pending', 'approved', 'rejected', 'developing', 'reviewing', 'deployed'];

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Wtyczki — Zarzadzanie propozycjami</h1>

      {/* Filters */}
      <div className="flex gap-4 mb-6">
        <div>
          <label className="text-xs text-zinc-500 uppercase block mb-1">Tenant</label>
          <select
            value={store.selectedTenant ?? ''}
            onChange={(e) => store.setTenant(e.target.value || null)}
            className="bg-zinc-800 border border-zinc-700 rounded px-3 py-1.5 text-sm text-zinc-200"
          >
            <option value="">Wszystkie</option>
            {tenants.map((t) => (
              <option key={t} value={t}>{t.toUpperCase()}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs text-zinc-500 uppercase block mb-1">Status</label>
          <select
            value={store.statusFilter ?? ''}
            onChange={(e) => store.setStatusFilter(e.target.value || null)}
            className="bg-zinc-800 border border-zinc-700 rounded px-3 py-1.5 text-sm text-zinc-200"
          >
            <option value="">Wszystkie</option>
            {statuses.map((s) => (
              <option key={s} value={s}>{STATUS_LABELS[s] ?? s}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="text-center text-zinc-500 py-12">Ladowanie...</div>
      ) : !proposals?.length ? (
        <div className="text-center text-zinc-500 py-12">Brak propozycji wtyczek.</div>
      ) : (
        <div className="border border-zinc-700 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-700 bg-zinc-800/50">
                <th className="text-left px-4 py-3 text-xs font-semibold text-zinc-500 uppercase">Tenant</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-zinc-500 uppercase">Tytul</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-zinc-500 uppercase">Autor</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-zinc-500 uppercase">Status</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-zinc-500 uppercase">Ocena</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-zinc-500 uppercase">Data</th>
              </tr>
            </thead>
            <tbody>
              {proposals.map((p: PluginProposal) => (
                <PluginRow
                  key={`${p.tenant}-${p.id}`}
                  proposal={p}
                  expanded={store.expandedProposalId === p.id}
                  onToggle={() => store.toggleExpanded(p.id)}
                  onApprove={() => handleApprove(p.id, p.tenant ?? 'reh')}
                  onStartReject={() => setShowRejectInput(p.id)}
                  showRejectInput={showRejectInput === p.id}
                  rejectReason={rejectReason}
                  onRejectReasonChange={setRejectReason}
                  onConfirmReject={() => handleReject(p.id, p.tenant ?? 'reh')}
                  onCancelReject={() => { setShowRejectInput(null); setRejectReason(''); }}
                  isApproving={approveMutation.isPending}
                  isRejecting={rejectMutation.isPending}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function PluginRow({
  proposal: p,
  expanded,
  onToggle,
  onApprove,
  onStartReject,
  showRejectInput,
  rejectReason,
  onRejectReasonChange,
  onConfirmReject,
  onCancelReject,
  isApproving,
  isRejecting,
}: {
  proposal: PluginProposal;
  expanded: boolean;
  onToggle: () => void;
  onApprove: () => void;
  onStartReject: () => void;
  showRejectInput: boolean;
  rejectReason: string;
  onRejectReasonChange: (v: string) => void;
  onConfirmReject: () => void;
  onCancelReject: () => void;
  isApproving: boolean;
  isRejecting: boolean;
}) {
  return (
    <>
      <tr
        onClick={onToggle}
        className={`border-b border-zinc-800 cursor-pointer hover:bg-zinc-800/50 ${expanded ? 'bg-zinc-800/30' : ''}`}
      >
        <td className="px-4 py-3 text-zinc-400 uppercase text-xs font-semibold">{p.tenant ?? '—'}</td>
        <td className="px-4 py-3 text-zinc-200">{p.title}</td>
        <td className="px-4 py-3 text-zinc-400">{p.proposed_by ?? '—'}</td>
        <td className="px-4 py-3"><StatusBadge status={p.status} /></td>
        <td className="px-4 py-3 text-zinc-400">{p.value_score != null ? p.value_score.toFixed(2) : '—'}</td>
        <td className="px-4 py-3 text-zinc-500">{p.created_at?.split('T')[0] ?? p.created_at?.split(' ')[0] ?? '—'}</td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={6} className="px-6 py-4 bg-zinc-900/50">
            <div className="space-y-4">
              {p.description && (
                <div className="text-sm">
                  <span className="text-zinc-400 font-semibold">Opis: </span>
                  <span className="text-zinc-300">{p.description}</span>
                </div>
              )}
              {p.expected_value && (
                <div className="text-sm">
                  <span className="text-zinc-400 font-semibold">Oczekiwana wartosc: </span>
                  <span className="text-zinc-300">{p.expected_value}</span>
                </div>
              )}

              {p.governance_result && <GovernanceDetails gov={p.governance_result} />}
              {p.review_result && <ReviewDetails review={p.review_result} />}

              {/* Actions for pending/reviewing proposals */}
              {(p.status === 'pending' || p.status === 'reviewing') && (
                <div className="flex items-center gap-3 pt-2">
                  <button
                    onClick={(e) => { e.stopPropagation(); onApprove(); }}
                    disabled={isApproving}
                    className="px-4 py-1.5 bg-green-600 hover:bg-green-700 text-white text-sm rounded disabled:opacity-50"
                  >
                    {isApproving ? 'Zatwierdzanie...' : 'Zatwierdz'}
                  </button>

                  {!showRejectInput ? (
                    <button
                      onClick={(e) => { e.stopPropagation(); onStartReject(); }}
                      className="px-4 py-1.5 bg-red-600 hover:bg-red-700 text-white text-sm rounded"
                    >
                      Odrzuc
                    </button>
                  ) : (
                    <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                      <input
                        type="text"
                        value={rejectReason}
                        onChange={(e) => onRejectReasonChange(e.target.value)}
                        placeholder="Powod odrzucenia..."
                        className="bg-zinc-800 border border-zinc-700 rounded px-3 py-1.5 text-sm text-zinc-200 w-64"
                      />
                      <button
                        onClick={onConfirmReject}
                        disabled={isRejecting}
                        className="px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white text-sm rounded disabled:opacity-50"
                      >
                        {isRejecting ? '...' : 'Potwierdz'}
                      </button>
                      <button
                        onClick={onCancelReject}
                        className="px-3 py-1.5 bg-zinc-700 hover:bg-zinc-600 text-white text-sm rounded"
                      >
                        Anuluj
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
