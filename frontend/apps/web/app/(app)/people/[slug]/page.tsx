'use client';

import { useParams, useRouter } from 'next/navigation';
import { useRole } from '@gilbertus/rbac';
import {
  ProfileHeader,
  ScorecardKpis,
  PersonTimeline,
  OpenLoops,
  RolesHistory,
  RbacGate,
} from '@gilbertus/ui';
import {
  usePerson,
  useScorecard,
  useSentiment,
  useDelegation,
  useAddTimeline,
  useAddRole,
  useAddLoop,
  useCloseLoop,
  useEvaluatePerson,
} from '@/lib/hooks/use-people';
import { usePeopleStore } from '@/lib/stores/people-store';
import type { EvaluateRequest } from '@gilbertus/api-client';

interface TabDef {
  id: 'timeline' | 'loops' | 'roles' | 'sentiment' | 'delegation';
  label: string;
  boardOnly?: boolean;
}

const TABS: TabDef[] = [
  { id: 'timeline', label: 'Historia' },
  { id: 'loops', label: 'Otwarte w\u0105tki' },
  { id: 'roles', label: 'Role' },
  { id: 'sentiment', label: 'Sentyment', boardOnly: true },
  { id: 'delegation', label: 'Delegacja', boardOnly: true },
];

export default function PersonProfilePage() {
  const { slug } = useParams<{ slug: string }>();
  const router = useRouter();
  const { role } = useRole();
  const store = usePeopleStore();

  const isCeo = role === 'ceo' || role === 'gilbertus_admin';
  const isBoardPlus = isCeo || role === 'board';

  const person = usePerson(slug);
  const scorecard = useScorecard(slug);
  const sentiment = useSentiment(slug, store.activeTab === 'sentiment' && isBoardPlus);
  const delegation = useDelegation(slug, store.activeTab === 'delegation');

  const addTimeline = useAddTimeline(slug);
  const addRole = useAddRole(slug);
  const addLoop = useAddLoop(slug);
  const closeLoop = useCloseLoop(slug);
  const evaluate = useEvaluatePerson();

  const visibleTabs = TABS.filter((tab) => !tab.boardOnly || isBoardPlus);

  if (person.isLoading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 animate-pulse rounded bg-[var(--bg-hover)]" />
        <div className="h-24 animate-pulse rounded-lg bg-[var(--bg-hover)]" />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-24 animate-pulse rounded-lg bg-[var(--bg-hover)]" />
          ))}
        </div>
      </div>
    );
  }

  if (person.error || !person.data) {
    return (
      <div className="space-y-4">
        <a
          href="/people"
          className="text-sm text-[var(--text-secondary)] hover:text-[var(--text)]"
        >
          \u2190 Ludzie
        </a>
        <p className="text-sm text-red-400">
          Nie znaleziono osoby lub wyst\u0105pi\u0142 b\u0142\u0105d.
        </p>
      </div>
    );
  }

  const data = person.data;

  return (
    <RbacGate
      roles={['gilbertus_admin', 'ceo', 'board', 'director']}
      fallback={
        <div className="text-sm text-[var(--text-muted)]">Brak dost\u0119pu do tego profilu.</div>
      }
    >
      <div className="space-y-6">
        <ProfileHeader
          person={data}
          canEdit={isCeo}
          canEvaluate={isCeo}
          onEdit={() => router.push(`/people/${slug}?edit=true`)}
          onEvaluate={() => {
            evaluate.mutate({ person_slug: slug } satisfies EvaluateRequest);
          }}
        />

        <ScorecardKpis
          scorecard={scorecard.data}
          isLoading={scorecard.isLoading}
        />

        {/* Tab navigation */}
        <div className="flex gap-1 border-b border-[var(--border)]">
          {visibleTabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => store.setActiveTab(tab.id)}
              className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
                store.activeTab === tab.id
                  ? 'border-blue-500 text-blue-400'
                  : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text)]'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div>
          {store.activeTab === 'timeline' && (
            <PersonTimeline
              events={data.timeline}
              canAdd={isCeo}
              onAdd={(eventData) => addTimeline.mutate(eventData)}
            />
          )}

          {store.activeTab === 'loops' && (
            <OpenLoops
              loops={data.open_loops}
              canAdd={isCeo}
              canClose={isCeo}
              onAdd={(desc) => addLoop.mutate({ description: desc })}
              onClose={(loopId) => closeLoop.mutate(loopId)}
            />
          )}

          {store.activeTab === 'roles' && (
            <RolesHistory
              roles={data.roles_history}
              canAdd={isCeo}
              onAdd={(roleData) => addRole.mutate(roleData)}
            />
          )}

          {store.activeTab === 'sentiment' && isBoardPlus && (
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
              {sentiment.isLoading && (
                <p className="text-sm text-[var(--text-muted)]">\u0141adowanie danych sentymentu...</p>
              )}
              {sentiment.data && (
                <div className="space-y-3">
                  <h3 className="text-sm font-medium text-[var(--text)]">Trend sentymentu (8 tyg.)</h3>
                  <div className="flex gap-2 flex-wrap">
                    {sentiment.data.trend.map((point) => (
                      <div
                        key={point.week}
                        className="rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-center"
                      >
                        <p className="text-xs text-[var(--text-muted)]">{point.week}</p>
                        <p className={`text-sm font-bold ${
                          point.score > 0 ? 'text-emerald-400' : point.score < 0 ? 'text-red-400' : 'text-zinc-400'
                        }`}>
                          {point.score > 0 ? '+' : ''}{point.score.toFixed(1)}
                        </p>
                        <p className="text-xs text-[var(--text-secondary)]">{point.label}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {!sentiment.isLoading && !sentiment.data && (
                <p className="text-sm text-[var(--text-muted)]">Brak danych sentymentu.</p>
              )}
            </div>
          )}

          {store.activeTab === 'delegation' && (
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
              {delegation.isLoading && (
                <p className="text-sm text-[var(--text-muted)]">\u0141adowanie wyniku delegacji...</p>
              )}
              {delegation.data && (
                <div className="space-y-3">
                  <h3 className="text-sm font-medium text-[var(--text)]">Wynik delegacji</h3>
                  <p className={`text-3xl font-bold ${
                    delegation.data.score >= 7 ? 'text-emerald-400' : delegation.data.score >= 4 ? 'text-amber-400' : 'text-red-400'
                  }`}>
                    {delegation.data.score.toFixed(1)}/10
                  </p>
                  {Object.keys(delegation.data.metrics).length > 0 && (
                    <div className="grid grid-cols-2 gap-2">
                      {Object.entries(delegation.data.metrics).map(([key, val]) => (
                        <div key={key} className="rounded border border-[var(--border)] bg-[var(--bg)] px-3 py-2">
                          <p className="text-xs text-[var(--text-muted)]">{key}</p>
                          <p className="text-sm font-medium text-[var(--text)]">{val}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
              {!delegation.isLoading && !delegation.data && (
                <p className="text-sm text-[var(--text-muted)]">Brak danych delegacji.</p>
              )}
            </div>
          )}
        </div>
      </div>
    </RbacGate>
  );
}
