'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRole } from '@gilbertus/rbac';
import { RbacGate } from '@gilbertus/ui';
import { cn } from '@gilbertus/ui';
import {
  useSentimentAlertsSummary,
  useCommitmentsSummary,
  useDelegationRanking,
  useResponseTracking,
  useNetworkAnalysis,
  useBlindSpots,
} from '@/lib/hooks/use-people-intelligence';

type PeopleIntelTab = 'sentiment' | 'commitments' | 'delegation' | 'response' | 'network';

const TABS: { id: PeopleIntelTab; label: string }[] = [
  { id: 'sentiment', label: 'Nastroje' },
  { id: 'commitments', label: 'Zobowiazania' },
  { id: 'delegation', label: 'Delegowanie' },
  { id: 'response', label: 'Czas reakcji' },
  { id: 'network', label: 'Siec kontaktow' },
];

function Skeleton() {
  return (
    <div className="animate-pulse space-y-3">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="h-10 bg-[var(--surface)] rounded-lg" />
      ))}
    </div>
  );
}

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
      <p className="text-xs font-medium text-[var(--text-secondary)]">{label}</p>
      <p className="text-2xl font-bold text-[var(--text)] mt-1">{value}</p>
      {sub && <p className="text-xs text-[var(--text-secondary)] mt-0.5">{sub}</p>}
    </div>
  );
}

function SentimentTab() {
  const { data, isLoading } = useSentimentAlertsSummary();
  if (isLoading) return <Skeleton />;
  const alerts = data?.alerts ?? [];
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Alerty nastrojow" value={alerts.length} />
        <StatCard
          label="Spadki nastrojow"
          value={alerts.filter((a) => a.alert_type === 'large_drop').length}
        />
        <StatCard
          label="Trendy spadkowe"
          value={alerts.filter((a) => a.alert_type === 'sustained_decline').length}
        />
      </div>
      {alerts.length === 0 ? (
        <p className="text-sm text-[var(--text-secondary)]">Brak alertow nastrojow. Wszystko stabilne.</p>
      ) : (
        <div className="rounded-xl border border-[var(--border)] overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-[var(--surface)]">
                <th className="text-left px-4 py-2.5 font-medium text-[var(--text-secondary)]">Osoba</th>
                <th className="text-left px-4 py-2.5 font-medium text-[var(--text-secondary)]">Typ</th>
                <th className="text-left px-4 py-2.5 font-medium text-[var(--text-secondary)]">Opis</th>
              </tr>
            </thead>
            <tbody>
              {alerts.map((a, i) => (
                <tr key={i} className="border-t border-[var(--border)]">
                  <td className="px-4 py-2.5 font-medium text-[var(--text)]">
                    <Link href={`/people/${a.person_slug}`} className="hover:text-[var(--accent)]">
                      {a.person_name}
                    </Link>
                  </td>
                  <td className="px-4 py-2.5">
                    <span
                      className={cn(
                        'inline-block rounded-full px-2 py-0.5 text-xs font-medium',
                        a.alert_type === 'large_drop'
                          ? 'bg-red-500/10 text-red-500'
                          : 'bg-amber-500/10 text-amber-500',
                      )}
                    >
                      {a.alert_type === 'large_drop' ? 'Duzy spadek' : 'Trend spadkowy'}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-[var(--text-secondary)]">{a.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function CommitmentsTab() {
  const { data, isLoading } = useCommitmentsSummary();
  if (isLoading) return <Skeleton />;
  const commitments = data?.commitments ?? [];
  const overdue = commitments.filter((c: Record<string, unknown>) => c.status === 'overdue');
  const open = commitments.filter((c: Record<string, unknown>) => c.status === 'open');
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Otwarte" value={open.length} />
        <StatCard label="Zaległe" value={overdue.length} />
        <StatCard label="Razem" value={commitments.length} />
      </div>
      {commitments.length === 0 ? (
        <p className="text-sm text-[var(--text-secondary)]">Brak otwartych zobowiazan.</p>
      ) : (
        <div className="rounded-xl border border-[var(--border)] overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-[var(--surface)]">
                <th className="text-left px-4 py-2.5 font-medium text-[var(--text-secondary)]">Osoba</th>
                <th className="text-left px-4 py-2.5 font-medium text-[var(--text-secondary)]">Zobowiazanie</th>
                <th className="text-left px-4 py-2.5 font-medium text-[var(--text-secondary)]">Status</th>
                <th className="text-left px-4 py-2.5 font-medium text-[var(--text-secondary)]">Termin</th>
              </tr>
            </thead>
            <tbody>
              {commitments.slice(0, 20).map((c: Record<string, unknown>, i: number) => (
                <tr key={i} className="border-t border-[var(--border)]">
                  <td className="px-4 py-2.5 font-medium text-[var(--text)]">{String(c.committed_by ?? c.person ?? '-')}</td>
                  <td className="px-4 py-2.5 text-[var(--text-secondary)] max-w-md truncate">{String(c.description ?? c.commitment ?? '')}</td>
                  <td className="px-4 py-2.5">
                    <span
                      className={cn(
                        'inline-block rounded-full px-2 py-0.5 text-xs font-medium',
                        c.status === 'overdue'
                          ? 'bg-red-500/10 text-red-500'
                          : 'bg-emerald-500/10 text-emerald-500',
                      )}
                    >
                      {String(c.status)}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-[var(--text-secondary)]">{String(c.due_date ?? c.deadline ?? '-')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function DelegationTab() {
  const { data, isLoading } = useDelegationRanking();
  if (isLoading) return <Skeleton />;
  const rankings = data?.rankings ?? [];
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Osob ocenionych" value={rankings.length} />
        <StatCard
          label="Sredni wynik"
          value={
            rankings.length > 0
              ? (rankings.reduce((s, r) => s + r.score, 0) / rankings.length).toFixed(1)
              : '-'
          }
        />
      </div>
      {rankings.length === 0 ? (
        <p className="text-sm text-[var(--text-secondary)]">Brak danych o delegowaniu.</p>
      ) : (
        <div className="rounded-xl border border-[var(--border)] overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-[var(--surface)]">
                <th className="text-left px-4 py-2.5 font-medium text-[var(--text-secondary)]">Osoba</th>
                <th className="text-left px-4 py-2.5 font-medium text-[var(--text-secondary)]">Wynik</th>
                <th className="text-left px-4 py-2.5 font-medium text-[var(--text-secondary)]">Zlecenia</th>
                <th className="text-left px-4 py-2.5 font-medium text-[var(--text-secondary)]">Realizacja</th>
              </tr>
            </thead>
            <tbody>
              {rankings.map((r, i) => (
                <tr key={i} className="border-t border-[var(--border)]">
                  <td className="px-4 py-2.5 font-medium text-[var(--text)]">{r.person}</td>
                  <td className="px-4 py-2.5">
                    <span
                      className={cn(
                        'font-medium',
                        r.score >= 7 ? 'text-emerald-500' : r.score >= 4 ? 'text-amber-500' : 'text-red-500',
                      )}
                    >
                      {r.score.toFixed(1)}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-[var(--text-secondary)]">{r.tasks_delegated}</td>
                  <td className="px-4 py-2.5 text-[var(--text-secondary)]">{(r.completion_rate * 100).toFixed(0)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function ResponseTab() {
  const { data, isLoading } = useResponseTracking(30);
  if (isLoading) return <Skeleton />;
  const stats = data?.stats ?? [];
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Osob" value={new Set(stats.map((s) => s.person)).size} />
        <StatCard
          label="Sredni czas (h)"
          value={
            stats.length > 0
              ? (stats.reduce((s, r) => s + r.avg_response_hours, 0) / stats.length).toFixed(1)
              : '-'
          }
        />
      </div>
      {stats.length === 0 ? (
        <p className="text-sm text-[var(--text-secondary)]">Brak danych o czasach reakcji.</p>
      ) : (
        <div className="rounded-xl border border-[var(--border)] overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-[var(--surface)]">
                <th className="text-left px-4 py-2.5 font-medium text-[var(--text-secondary)]">Osoba</th>
                <th className="text-left px-4 py-2.5 font-medium text-[var(--text-secondary)]">Kanal</th>
                <th className="text-left px-4 py-2.5 font-medium text-[var(--text-secondary)]">Sredni czas (h)</th>
                <th className="text-left px-4 py-2.5 font-medium text-[var(--text-secondary)]">Wiadomosci</th>
              </tr>
            </thead>
            <tbody>
              {stats.slice(0, 20).map((s, i) => (
                <tr key={i} className="border-t border-[var(--border)]">
                  <td className="px-4 py-2.5 font-medium text-[var(--text)]">{s.person}</td>
                  <td className="px-4 py-2.5 text-[var(--text-secondary)]">{s.channel}</td>
                  <td className="px-4 py-2.5">
                    <span
                      className={cn(
                        'font-medium',
                        s.avg_response_hours <= 4 ? 'text-emerald-500' : s.avg_response_hours <= 24 ? 'text-amber-500' : 'text-red-500',
                      )}
                    >
                      {s.avg_response_hours.toFixed(1)}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-[var(--text-secondary)]">{s.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function NetworkTab() {
  const { data, isLoading } = useNetworkAnalysis();
  const blindSpots = useBlindSpots();
  if (isLoading) return <Skeleton />;
  const nodes = data?.nodes ?? [];
  const edges = data?.edges ?? [];
  const spots = blindSpots.data?.blind_spots ?? [];

  // Find nodes with most connections (hubs) and least (isolated)
  const nodeDegrees = new Map<string, number>();
  edges.forEach((e) => {
    nodeDegrees.set(e.source, (nodeDegrees.get(e.source) ?? 0) + 1);
    nodeDegrees.set(e.target, (nodeDegrees.get(e.target) ?? 0) + 1);
  });
  const sorted = [...nodeDegrees.entries()].sort((a, b) => b[1] - a[1]);
  const hubs = sorted.slice(0, 5);
  const isolated = nodes.filter((n) => !nodeDegrees.has(n.id) || (nodeDegrees.get(n.id) ?? 0) <= 1);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Osoby w sieci" value={nodes.length} />
        <StatCard label="Polaczenia" value={edges.length} />
        <StatCard label="Izolowani" value={isolated.length} />
        <StatCard label="Slepe punkty" value={spots.length} />
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Hubs */}
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
          <h3 className="font-medium text-[var(--text)] mb-3">Wezly komunikacji (top 5)</h3>
          {hubs.length === 0 ? (
            <p className="text-sm text-[var(--text-secondary)]">Brak danych</p>
          ) : (
            <ul className="space-y-2">
              {hubs.map(([id, degree]) => {
                const node = nodes.find((n) => n.id === id);
                return (
                  <li key={id} className="flex items-center justify-between text-sm">
                    <span className="text-[var(--text)]">{node?.name ?? id}</span>
                    <span className="text-[var(--text-secondary)]">{degree} polaczen</span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {/* Blind Spots */}
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
          <h3 className="font-medium text-[var(--text)] mb-3">Slepe punkty</h3>
          {spots.length === 0 ? (
            <p className="text-sm text-[var(--text-secondary)]">Brak wykrytych slepych punktow</p>
          ) : (
            <ul className="space-y-2">
              {spots.map((s, i) => (
                <li key={i} className="flex items-start gap-2 text-sm">
                  <span
                    className={cn(
                      'mt-0.5 h-2 w-2 rounded-full shrink-0',
                      s.severity === 'high' ? 'bg-red-500' : s.severity === 'medium' ? 'bg-amber-500' : 'bg-zinc-400',
                    )}
                  />
                  <div>
                    <span className="font-medium text-[var(--text)]">{s.area}</span>
                    <p className="text-[var(--text-secondary)]">{s.description}</p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

function PeopleIntelligenceContent() {
  const [activeTab, setActiveTab] = useState<PeopleIntelTab>('sentiment');

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/people" className="text-[var(--text-secondary)] hover:text-[var(--text)] transition-colors">
          Ludzie
        </Link>
        <span className="text-[var(--text-secondary)]">/</span>
        <h1 className="text-2xl font-bold text-[var(--text)]">Wywiad personalny</h1>
      </div>

      {/* Tab bar */}
      <div className="flex items-center gap-1 border-b border-[var(--border)]">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              'px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px',
              activeTab === tab.id
                ? 'border-[var(--accent)] text-[var(--accent)]'
                : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text)] hover:border-[var(--border)]',
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'sentiment' && <SentimentTab />}
      {activeTab === 'commitments' && <CommitmentsTab />}
      {activeTab === 'delegation' && <DelegationTab />}
      {activeTab === 'response' && <ResponseTab />}
      {activeTab === 'network' && <NetworkTab />}
    </div>
  );
}

export default function PeopleIntelligencePage() {
  return (
    <RbacGate
      roles={['owner', 'ceo', 'board', 'gilbertus_admin']}
      fallback={
        <div className="flex items-center justify-center h-64 text-[var(--text-secondary)]">
          Brak dostepu do wywiadu personalnego
        </div>
      }
    >
      <PeopleIntelligenceContent />
    </RbacGate>
  );
}
