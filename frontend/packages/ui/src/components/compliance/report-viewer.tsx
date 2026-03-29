'use client';

import type { WeeklyReportResponse } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';
import { AreaFilter } from './area-filter';

export interface ReportViewerProps {
  activeTab: 'daily' | 'weekly' | 'area';
  onTabChange: (tab: 'daily' | 'weekly' | 'area') => void;
  // Daily
  dailyReport: string | null | undefined;
  isDailyLoading?: boolean;
  // Weekly
  weeklyReport: WeeklyReportResponse | null | undefined;
  isWeeklyLoading?: boolean;
  // Area
  areaCode: string | null;
  onAreaCodeChange: (v: string | null) => void;
  areaReport: string | null | undefined;
  isAreaLoading?: boolean;
}

const TABS = [
  { key: 'daily' as const, label: 'Dzienny' },
  { key: 'weekly' as const, label: 'Tygodniowy' },
  { key: 'area' as const, label: 'Obszar' },
] as const;

function formatDate(dateStr: string): string {
  try {
    return new Intl.DateTimeFormat('pl-PL', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(dateStr));
  } catch {
    return dateStr;
  }
}

function LoadingSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 8 }).map((_, i) => (
        <div
          key={i}
          className="h-4 rounded bg-[var(--surface)] animate-pulse"
          style={{ width: `${60 + Math.random() * 40}%` }}
        />
      ))}
    </div>
  );
}

export function ReportViewer({
  activeTab,
  onTabChange,
  dailyReport,
  isDailyLoading,
  weeklyReport,
  isWeeklyLoading,
  areaCode,
  onAreaCodeChange,
  areaReport,
  isAreaLoading,
}: ReportViewerProps) {
  return (
    <div className="space-y-4">
      {/* Tab Navigation */}
      <div className="flex gap-0 border-b border-[var(--border)]">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => onTabChange(tab.key)}
            className={cn(
              'px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px',
              activeTab === tab.key
                ? 'border-[var(--accent)] text-[var(--text)]'
                : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text)]',
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Daily Tab */}
      {activeTab === 'daily' && (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6">
          {isDailyLoading ? (
            <LoadingSkeleton />
          ) : dailyReport ? (
            <pre className="whitespace-pre-wrap text-sm text-[var(--text)] font-sans leading-relaxed">
              {dailyReport}
            </pre>
          ) : (
            <p className="text-[var(--text-secondary)] text-sm text-center py-8">
              Brak raportu dziennego. Raport generowany jest w godzinach roboczych.
            </p>
          )}
        </div>
      )}

      {/* Weekly Tab */}
      {activeTab === 'weekly' && (
        <div className="space-y-4">
          {isWeeklyLoading ? (
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6">
              <LoadingSkeleton />
            </div>
          ) : weeklyReport ? (
            <>
              <div className="flex items-center justify-between text-sm text-[var(--text-secondary)]">
                <span>Wygenerowano: {formatDate(weeklyReport.generated_at)}</span>
                {weeklyReport.whatsapp_sent && (
                  <span className="text-green-400 text-xs font-medium">WhatsApp wysłany</span>
                )}
              </div>

              <div className="border border-[var(--border)] rounded-lg overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[var(--border)] bg-[var(--surface)]">
                      <th className="px-3 py-2.5 text-left text-xs font-medium text-[var(--text-secondary)] uppercase">
                        Obszar
                      </th>
                      <th className="px-3 py-2.5 text-center text-xs font-medium text-green-400 uppercase">
                        Zgodne
                      </th>
                      <th className="px-3 py-2.5 text-center text-xs font-medium text-yellow-400 uppercase">
                        Częściowo
                      </th>
                      <th className="px-3 py-2.5 text-center text-xs font-medium text-red-400 uppercase">
                        Niezgodne
                      </th>
                      <th className="px-3 py-2.5 text-center text-xs font-medium text-blue-400 uppercase">
                        Otw. sprawy
                      </th>
                      <th className="px-3 py-2.5 text-center text-xs font-medium text-gray-400 uppercase">
                        Zamk. sprawy
                      </th>
                      <th className="px-3 py-2.5 text-center text-xs font-medium text-green-400 uppercase">
                        Term. OK
                      </th>
                      <th className="px-3 py-2.5 text-center text-xs font-medium text-red-400 uppercase">
                        Term. miss
                      </th>
                      <th className="px-3 py-2.5 text-center text-xs font-medium text-blue-400 uppercase">
                        Dok. gen.
                      </th>
                      <th className="px-3 py-2.5 text-center text-xs font-medium text-green-400 uppercase">
                        Dok. zatw.
                      </th>
                      <th className="px-3 py-2.5 text-center text-xs font-medium text-orange-400 uppercase">
                        Ryzyka
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {weeklyReport.areas.map((area) => (
                      <tr key={area.code} className="border-b border-[var(--border)]">
                        <td className="px-3 py-2.5 text-sm font-medium text-[var(--text)]">
                          {area.name}
                        </td>
                        <td className="px-3 py-2.5 text-center text-[var(--text)]">
                          {area.obligations.compliant}
                        </td>
                        <td className="px-3 py-2.5 text-center text-[var(--text)]">
                          {area.obligations.partially_compliant}
                        </td>
                        <td className="px-3 py-2.5 text-center text-[var(--text)]">
                          {area.obligations.non_compliant}
                        </td>
                        <td className="px-3 py-2.5 text-center text-[var(--text)]">
                          {area.matters.opened}
                        </td>
                        <td className="px-3 py-2.5 text-center text-[var(--text)]">
                          {area.matters.closed}
                        </td>
                        <td className="px-3 py-2.5 text-center text-[var(--text)]">
                          {area.deadlines.met}
                        </td>
                        <td className="px-3 py-2.5 text-center text-[var(--text)]">
                          {area.deadlines.missed}
                        </td>
                        <td className="px-3 py-2.5 text-center text-[var(--text)]">
                          {area.documents.generated}
                        </td>
                        <td className="px-3 py-2.5 text-center text-[var(--text)]">
                          {area.documents.approved}
                        </td>
                        <td className="px-3 py-2.5 text-center text-[var(--text)]">
                          {area.open_risks}
                        </td>
                      </tr>
                    ))}
                    {/* Summary row */}
                    <tr className="bg-[var(--surface)] font-semibold">
                      <td className="px-3 py-2.5 text-sm text-[var(--text)]">Razem</td>
                      <td className="px-3 py-2.5 text-center text-[var(--text)]">
                        {weeklyReport.areas.reduce((s, a) => s + a.obligations.compliant, 0)}
                      </td>
                      <td className="px-3 py-2.5 text-center text-[var(--text)]">
                        {weeklyReport.areas.reduce(
                          (s, a) => s + a.obligations.partially_compliant,
                          0,
                        )}
                      </td>
                      <td className="px-3 py-2.5 text-center text-[var(--text)]">
                        {weeklyReport.areas.reduce((s, a) => s + a.obligations.non_compliant, 0)}
                      </td>
                      <td className="px-3 py-2.5 text-center text-[var(--text)]">
                        {weeklyReport.areas.reduce((s, a) => s + a.matters.opened, 0)}
                      </td>
                      <td className="px-3 py-2.5 text-center text-[var(--text)]">
                        {weeklyReport.areas.reduce((s, a) => s + a.matters.closed, 0)}
                      </td>
                      <td className="px-3 py-2.5 text-center text-[var(--text)]">
                        {weeklyReport.areas.reduce((s, a) => s + a.deadlines.met, 0)}
                      </td>
                      <td className="px-3 py-2.5 text-center text-[var(--text)]">
                        {weeklyReport.areas.reduce((s, a) => s + a.deadlines.missed, 0)}
                      </td>
                      <td className="px-3 py-2.5 text-center text-[var(--text)]">
                        {weeklyReport.areas.reduce((s, a) => s + a.documents.generated, 0)}
                      </td>
                      <td className="px-3 py-2.5 text-center text-[var(--text)]">
                        {weeklyReport.areas.reduce((s, a) => s + a.documents.approved, 0)}
                      </td>
                      <td className="px-3 py-2.5 text-center text-[var(--text)]">
                        {weeklyReport.areas.reduce((s, a) => s + a.open_risks, 0)}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 text-center text-[var(--text-secondary)] text-sm">
              Brak raportu tygodniowego.
            </div>
          )}
        </div>
      )}

      {/* Area Tab */}
      {activeTab === 'area' && (
        <div className="space-y-4">
          <AreaFilter value={areaCode} onChange={onAreaCodeChange} className="w-64" />

          {!areaCode ? (
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 text-center text-[var(--text-secondary)] text-sm">
              Wybierz obszar, aby wyświetlić raport.
            </div>
          ) : isAreaLoading ? (
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6">
              <LoadingSkeleton />
            </div>
          ) : areaReport ? (
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6">
              <pre className="whitespace-pre-wrap text-sm text-[var(--text)] font-sans leading-relaxed">
                {areaReport}
              </pre>
            </div>
          ) : (
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 text-center text-[var(--text-secondary)] text-sm">
              Brak raportu dla wybranego obszaru.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
