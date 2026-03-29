'use client';

import { useState, useMemo, useCallback } from 'react';
import {
  RbacGate,
  DecisionCard,
  DecisionFilters,
  CreateDecisionModal,
  OutcomeModal,
  PatternsPanel,
  DecisionIntelligence,
} from '@gilbertus/ui';
import type { DecisionCreate, OutcomeCreate } from '@gilbertus/api-client';
import {
  useDecisions,
  useDecisionPatterns,
  useDecisionIntelligence,
  useCreateDecision,
  useAddOutcome,
  useRunIntelligence,
} from '@/lib/hooks/use-decisions';
import { useDecisionsStore } from '@/lib/stores/decisions-store';

function JournalSkeleton() {
  return (
    <div className="space-y-3 animate-pulse">
      {[1, 2, 3, 4].map((i) => (
        <div
          key={i}
          className="h-14 rounded-lg"
          style={{ backgroundColor: 'var(--surface-hover)' }}
        />
      ))}
    </div>
  );
}

export default function DecisionsPage() {
  const store = useDecisionsStore();

  // Queries
  const { data: decisionsData, isLoading: decisionsLoading, error: decisionsError } =
    useDecisions(store.areaFilter ?? undefined, store.listLimit);
  const { data: patterns, isLoading: patternsLoading } = useDecisionPatterns();
  const { data: intelligence, isLoading: intelligenceLoading } =
    useDecisionIntelligence(store.intelligenceMonths);

  // Mutations
  const createMutation = useCreateDecision();
  const outcomeMutation = useAddOutcome();
  const runIntelMutation = useRunIntelligence();

  // Local modal state
  const [createOpen, setCreateOpen] = useState(false);
  const [outcomeDecisionId, setOutcomeDecisionId] = useState<number | null>(null);

  // Success banners
  const [createSuccess, setCreateSuccess] = useState(false);
  const [outcomeSuccess, setOutcomeSuccess] = useState(false);

  // Client-side search filter
  const filteredDecisions = useMemo(() => {
    const list = decisionsData?.decisions ?? [];
    const q = store.searchQuery.toLowerCase().trim();
    if (!q) return list;
    return list.filter(
      (d) =>
        d.decision_text.toLowerCase().includes(q) ||
        d.context?.toLowerCase().includes(q) ||
        d.expected_outcome?.toLowerCase().includes(q),
    );
  }, [decisionsData?.decisions, store.searchQuery]);

  // Find decision text for outcome modal
  const outcomeDecision = useMemo(
    () => decisionsData?.decisions?.find((d) => d.id === outcomeDecisionId),
    [decisionsData?.decisions, outcomeDecisionId],
  );

  const handleCreate = useCallback(
    (data: DecisionCreate) => {
      createMutation.mutate(data, {
        onSuccess: () => {
          setCreateOpen(false);
          setCreateSuccess(true);
          setTimeout(() => setCreateSuccess(false), 3000);
        },
      });
    },
    [createMutation],
  );

  const handleOutcome = useCallback(
    (data: OutcomeCreate) => {
      if (outcomeDecisionId == null) return;
      outcomeMutation.mutate(
        { decisionId: outcomeDecisionId, data },
        {
          onSuccess: () => {
            setOutcomeDecisionId(null);
            setOutcomeSuccess(true);
            setTimeout(() => setOutcomeSuccess(false), 3000);
          },
        },
      );
    },
    [outcomeMutation, outcomeDecisionId],
  );

  return (
    <RbacGate roles={['ceo']} permission="decisions">
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold" style={{ color: 'var(--text)' }}>
            Decyzje
          </h1>
          <button
            onClick={() => setCreateOpen(true)}
            className="rounded-md px-4 py-1.5 text-sm font-medium transition-colors"
            style={{ backgroundColor: 'var(--accent)', color: '#fff' }}
          >
            Nowa decyzja
          </button>
        </div>

        {/* Success banners */}
        {createSuccess && (
          <div className="rounded-lg border border-green-500/30 bg-green-500/10 px-4 py-2.5 text-sm text-green-400">
            Decyzja zapisana
          </div>
        )}
        {outcomeSuccess && (
          <div className="rounded-lg border border-green-500/30 bg-green-500/10 px-4 py-2.5 text-sm text-green-400">
            Wynik zapisany
          </div>
        )}

        {/* Error */}
        {decisionsError && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-2.5 text-sm text-red-400">
            Nie udalo sie zaladowac decyzji
          </div>
        )}

        {/* Tabs */}
        <div>
          <div
            className="inline-flex rounded-md border"
            style={{ borderColor: 'var(--border)' }}
          >
            {(
              [
                { id: 'journal', label: 'Dziennik' },
                { id: 'patterns', label: 'Wzorce AI' },
                { id: 'intelligence', label: 'Intelligence' },
              ] as const
            ).map((tab) => (
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

        {/* Tab content */}
        {store.activeTab === 'journal' && (
          <div className="space-y-4">
            <DecisionFilters
              areaFilter={store.areaFilter}
              onAreaChange={store.setAreaFilter}
              searchQuery={store.searchQuery}
              onSearchChange={store.setSearchQuery}
            />

            {decisionsLoading ? (
              <JournalSkeleton />
            ) : filteredDecisions.length === 0 ? (
              <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                Brak decyzji do wyswietlenia.
              </p>
            ) : (
              <div className="space-y-2">
                {filteredDecisions.map((d) => (
                  <DecisionCard
                    key={d.id}
                    decision={d}
                    expanded={store.expandedDecisionId === d.id}
                    onToggle={() =>
                      store.setExpandedDecisionId(
                        store.expandedDecisionId === d.id ? null : d.id,
                      )
                    }
                    onAddOutcome={(id) => setOutcomeDecisionId(id)}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {store.activeTab === 'patterns' && (
          <PatternsPanel
            insights={patterns?.insights}
            isLoading={patternsLoading}
            meta={patterns?.meta}
          />
        )}

        {store.activeTab === 'intelligence' && (
          <DecisionIntelligence
            data={intelligence}
            isLoading={intelligenceLoading}
            months={store.intelligenceMonths}
            onMonthsChange={store.setIntelligenceMonths}
            onRunAnalysis={() => runIntelMutation.mutate()}
            isRunning={runIntelMutation.isPending}
          />
        )}

        {/* Modals */}
        <CreateDecisionModal
          open={createOpen}
          onClose={() => setCreateOpen(false)}
          onSubmit={handleCreate}
          isLoading={createMutation.isPending}
        />
        <OutcomeModal
          open={outcomeDecisionId != null}
          onClose={() => setOutcomeDecisionId(null)}
          onSubmit={handleOutcome}
          decisionText={outcomeDecision?.decision_text ?? ''}
          isLoading={outcomeMutation.isPending}
        />
      </div>
    </RbacGate>
  );
}
