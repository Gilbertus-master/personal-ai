'use client';

import { useMemo } from 'react';
import Link from 'next/link';
import { Users } from 'lucide-react';
import type { Person } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';

interface PeopleTableProps {
  people: Person[];
  searchQuery: string;
  sortBy: 'name' | 'last_contact' | 'status';
  sortOrder: 'asc' | 'desc';
  isLoading?: boolean;
}

const COLUMNS = ['', 'Imię i nazwisko', 'Rola', 'Organizacja', 'Status', 'Nastawienie', 'Ostatni kontakt'] as const;

function getInitials(firstName: string, lastName: string | null): string {
  const first = firstName.charAt(0).toUpperCase();
  const last = lastName ? lastName.charAt(0).toUpperCase() : '';
  return first + last;
}

function hashColor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  const hue = Math.abs(hash) % 360;
  return `hsl(${hue}, 55%, 45%)`;
}

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '\u2014';
  try {
    return new Intl.DateTimeFormat('pl-PL', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(dateStr));
  } catch {
    return '\u2014';
  }
}

function getSentimentStyle(sentiment: string | undefined) {
  switch (sentiment) {
    case 'positive':
      return { className: 'bg-green-500/15 text-green-400', label: 'Pozytywne' };
    case 'negative':
      return { className: 'bg-red-500/15 text-red-400', label: 'Negatywne' };
    default:
      return { className: 'bg-[var(--surface)] text-[var(--text-secondary)]', label: 'Neutralne' };
  }
}

function sortPeople(people: Person[], sortBy: string, sortOrder: 'asc' | 'desc'): Person[] {
  const sorted = [...people].sort((a, b) => {
    switch (sortBy) {
      case 'name': {
        const nameA = `${a.first_name} ${a.last_name ?? ''}`.toLowerCase();
        const nameB = `${b.first_name} ${b.last_name ?? ''}`.toLowerCase();
        return nameA.localeCompare(nameB, 'pl');
      }
      case 'last_contact': {
        const dateA = a.relationship?.last_contact_date ?? '';
        const dateB = b.relationship?.last_contact_date ?? '';
        return dateA.localeCompare(dateB);
      }
      case 'status': {
        const statusA = a.relationship?.status ?? '';
        const statusB = b.relationship?.status ?? '';
        return statusA.localeCompare(statusB, 'pl');
      }
      default:
        return 0;
    }
  });
  return sortOrder === 'desc' ? sorted.reverse() : sorted;
}

function SkeletonRows() {
  return (
    <>
      {Array.from({ length: 8 }).map((_, i) => (
        <tr key={i} className="border-b border-[var(--border)]">
          <td className="px-4 py-3">
            <div className="h-8 w-8 rounded-full bg-[var(--surface)] animate-pulse" />
          </td>
          {Array.from({ length: 6 }).map((_, j) => (
            <td key={j} className="px-4 py-3">
              <div className="h-4 rounded bg-[var(--surface)] animate-pulse" style={{ width: `${60 + j * 10}%` }} />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}

export function PeopleTable({ people, searchQuery, sortBy, sortOrder, isLoading }: PeopleTableProps) {
  const filtered = useMemo(() => {
    const query = searchQuery.toLowerCase();
    const matched = query
      ? people.filter((p) => {
          const fullName = `${p.first_name} ${p.last_name ?? ''}`.toLowerCase();
          return fullName.includes(query);
        })
      : people;
    return sortPeople(matched, sortBy, sortOrder);
  }, [people, searchQuery, sortBy, sortOrder]);

  return (
    <div className="border border-[var(--border)] rounded-lg overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--border)] bg-[var(--surface)]">
            {COLUMNS.map((col) => (
              <th key={col} className="px-4 py-3 text-left text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider">
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {isLoading ? (
            <SkeletonRows />
          ) : filtered.length === 0 ? (
            <tr>
              <td colSpan={COLUMNS.length} className="px-4 py-16 text-center">
                <div className="flex flex-col items-center gap-2 text-[var(--text-secondary)]">
                  <Users className="h-10 w-10 opacity-40" />
                  <span className="text-sm">Nie znaleziono osób</span>
                </div>
              </td>
            </tr>
          ) : (
            filtered.map((person) => {
              const fullName = `${person.first_name} ${person.last_name ?? ''}`.trim();
              const initials = getInitials(person.first_name, person.last_name);
              const bgColor = hashColor(fullName);
              const rel = person.relationship;
              const sentiment = getSentimentStyle(rel?.sentiment);
              const isActive = rel?.status === 'active';

              return (
                <Link key={person.id} href={`/people/${person.slug}`} className="contents">
                  <tr className="border-b border-[var(--border)] cursor-pointer hover:bg-[var(--surface-hover)] transition-colors">
                    {/* Avatar */}
                    <td className="px-4 py-3">
                      <div
                        className="h-8 w-8 rounded-full flex items-center justify-center text-xs font-semibold text-white shrink-0"
                        style={{ backgroundColor: bgColor }}
                      >
                        {initials}
                      </div>
                    </td>
                    {/* Name */}
                    <td className="px-4 py-3 font-medium text-[var(--text)]">{fullName}</td>
                    {/* Role */}
                    <td className="px-4 py-3 text-[var(--text-secondary)]">{rel?.current_role ?? '\u2014'}</td>
                    {/* Organization */}
                    <td className="px-4 py-3 text-[var(--text-secondary)]">{rel?.organization ?? '\u2014'}</td>
                    {/* Status */}
                    <td className="px-4 py-3">
                      <span className="flex items-center gap-1.5 text-[var(--text-secondary)]">
                        <span
                          className={cn('h-2 w-2 rounded-full shrink-0', isActive ? 'bg-green-500' : 'bg-gray-500')}
                        />
                        {rel?.status ?? '\u2014'}
                      </span>
                    </td>
                    {/* Sentiment */}
                    <td className="px-4 py-3">
                      <span className={cn('inline-block rounded-full px-2.5 py-0.5 text-xs font-medium', sentiment.className)}>
                        {sentiment.label}
                      </span>
                    </td>
                    {/* Last contact */}
                    <td className="px-4 py-3 text-[var(--text-secondary)]">{formatDate(rel?.last_contact_date)}</td>
                  </tr>
                </Link>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
