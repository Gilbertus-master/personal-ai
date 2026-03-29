'use client';

import { useRole } from '@gilbertus/rbac';
import { RbacGate, PeopleToolbar, PeopleTable } from '@gilbertus/ui';
import { usePeople } from '@/lib/hooks/use-people';
import { usePeopleStore } from '@/lib/stores/people-store';

export default function PeoplePage() {
  const { role } = useRole();
  const store = usePeopleStore();
  const { data, isLoading } = usePeople();

  const count = data?.meta?.count ?? 0;

  return (
    <RbacGate
      roles={['ceo', 'board', 'director']}
      fallback={
        <div className="flex items-center justify-center h-64 text-[var(--text-secondary)]">
          Brak dostępu do modułu Ludzie
        </div>
      }
    >
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-[var(--text)]">Ludzie</h1>
            {!isLoading && (
              <span className="rounded-full bg-[var(--surface)] px-2.5 py-0.5 text-xs font-medium text-[var(--text-secondary)]">
                {count}
              </span>
            )}
          </div>
          {role === 'ceo' && (
            <button className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 transition-opacity">
              Dodaj osobę
            </button>
          )}
        </div>

        <PeopleToolbar
          searchQuery={store.searchQuery}
          onSearchChange={store.setSearchQuery}
          filterType={store.filterType}
          onFilterTypeChange={store.setFilterType}
          filterStatus={store.filterStatus}
          onFilterStatusChange={store.setFilterStatus}
          sortBy={store.sortBy}
          onSortChange={store.setSortBy}
          sortOrder={store.sortOrder}
          onSortOrderToggle={store.toggleSortOrder}
          onResetFilters={store.resetFilters}
        />

        <PeopleTable
          people={data?.people ?? []}
          searchQuery={store.searchQuery}
          sortBy={store.sortBy}
          sortOrder={store.sortOrder}
          isLoading={isLoading}
        />
      </div>
    </RbacGate>
  );
}
