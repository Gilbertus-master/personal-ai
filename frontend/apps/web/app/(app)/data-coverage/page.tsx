'use client';

import { useEffect, useState } from 'react';

interface HeatmapData {
  months: string[];
  source_types: string[];
  data: Record<string, Record<string, number>>;
  thresholds: { low: number; medium: number; high: number };
  error?: string;
}

const SOURCE_LABELS: Record<string, string> = {
  email: 'Email',
  teams: 'Teams',
  whatsapp: 'WhatsApp',
  whatsapp_live: 'WA Live',
  audio_transcript: 'Audio',
  chatgpt: 'ChatGPT',
  document: 'Dokumenty',
  spreadsheet: 'Arkusze',
  calendar: 'Kalendarz',
  claude_code_full: 'Claude Code',
};

function getCellColor(count: number, thresholds: HeatmapData['thresholds']): string {
  if (count === 0) return 'bg-red-950 text-red-400';
  if (count < thresholds.low) return 'bg-red-900/60 text-red-300';
  if (count < thresholds.medium) return 'bg-yellow-900/60 text-yellow-300';
  return 'bg-green-900/60 text-green-300';
}

const API_BASE =
  typeof window !== 'undefined'
    ? (process.env.NEXT_PUBLIC_GILBERTUS_API_URL ?? 'http://127.0.0.1:8000')
    : 'http://127.0.0.1:8000';

export default function DataCoveragePage() {
  const [data, setData] = useState<HeatmapData | null>(null);
  const [loading, setLoading] = useState(true);
  const [years, setYears] = useState(3);

  useEffect(() => {
    setLoading(true);
    fetch(`${API_BASE}/coverage/heatmap?years=${years}`)
      .then((r) => r.json())
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [years]);

  if (loading) return <div className="p-8 text-[var(--text-muted)]">Ladowanie...</div>;
  if (!data || data.error) return <div className="p-8 text-red-400">Blad pobierania danych</div>;

  const recentMonths = data.months.slice(-24);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Pokrycie danych</h1>
          <p className="text-[var(--text-muted)] text-sm mt-1">
            Ile dokumentow mamy per zrodlo per miesiac
          </p>
        </div>
        <select
          value={years}
          onChange={(e) => setYears(Number(e.target.value))}
          className="px-3 py-1.5 rounded-md bg-[var(--surface-secondary)] text-sm border border-[var(--border)]"
        >
          <option value={1}>Ostatni rok</option>
          <option value={2}>Ostatnie 2 lata</option>
          <option value={3}>Ostatnie 3 lata</option>
        </select>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 text-xs">
        <span className="px-2 py-1 rounded bg-red-950 text-red-400">0 - brak</span>
        <span className="px-2 py-1 rounded bg-red-900/60 text-red-300">1-9 - minimalne</span>
        <span className="px-2 py-1 rounded bg-yellow-900/60 text-yellow-300">10-49 - czesciowe</span>
        <span className="px-2 py-1 rounded bg-green-900/60 text-green-300">50+ - dobre</span>
      </div>

      {/* Heatmap */}
      <div className="overflow-x-auto">
        <table className="text-xs border-collapse min-w-max">
          <thead>
            <tr>
              <th className="text-left px-2 py-1 text-[var(--text-muted)] w-28">Zrodlo</th>
              {recentMonths.map((m) => (
                <th key={m} className="px-1 py-1 text-[var(--text-muted)] text-center min-w-[36px]">
                  {m.slice(5)}
                  <br />
                  <span className="text-[10px] opacity-50">{m.slice(0, 4)}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.source_types.map((sourceType) => (
              <tr key={sourceType} className="hover:bg-[var(--surface-hover)]">
                <td className="px-2 py-1 text-[var(--text-muted)] font-medium">
                  {SOURCE_LABELS[sourceType] || sourceType}
                </td>
                {recentMonths.map((month) => {
                  const count = data.data[sourceType]?.[month] ?? 0;
                  return (
                    <td
                      key={month}
                      className={`px-1 py-1 text-center rounded-sm mx-0.5 ${getCellColor(count, data.thresholds)}`}
                      title={`${sourceType} ${month}: ${count} dok.`}
                    >
                      {count > 0 ? count : '-'}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Summary of gaps */}
      <div className="text-sm text-[var(--text-muted)]">
        {Object.entries(data.data).map(([st, months]) => {
          const gapMonths = recentMonths.filter(
            (m) => !months[m] || months[m] < data.thresholds.low,
          );
          if (gapMonths.length === 0) return null;
          return (
            <p key={st}>
              <strong>{SOURCE_LABELS[st] || st}</strong>: brakuje danych w {gapMonths.length}{' '}
              miesiacach
            </p>
          );
        })}
      </div>
    </div>
  );
}
