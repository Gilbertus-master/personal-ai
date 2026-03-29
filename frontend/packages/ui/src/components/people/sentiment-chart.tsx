'use client';

import type { SentimentTrend } from '@gilbertus/api-client';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

interface SentimentChartProps {
  data?: SentimentTrend;
  isLoading?: boolean;
}

function scoreToCssColor(score: number): string {
  if (score >= 0.3) return '#22c55e';
  if (score <= -0.3) return '#ef4444';
  return '#a1a1aa';
}

interface TooltipPayloadItem {
  payload?: { week?: string; score?: number; label?: string };
}

function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: TooltipPayloadItem[];
}) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  if (!d) return null;
  return (
    <div
      className="rounded-lg px-3 py-2 text-sm shadow-lg"
      style={{
        backgroundColor: 'var(--surface)',
        border: '1px solid var(--border)',
        color: 'var(--text)',
      }}
    >
      <p className="font-medium">{d.week}</p>
      <p style={{ color: scoreToCssColor(d.score ?? 0) }}>
        {d.score?.toFixed(2)} &mdash; {d.label}
      </p>
    </div>
  );
}

export function SentimentChart({ data, isLoading = false }: SentimentChartProps) {
  if (isLoading) {
    return (
      <div
        className="animate-pulse rounded-lg"
        style={{ height: 300, backgroundColor: 'var(--surface)' }}
      />
    );
  }

  if (!data?.trend?.length) {
    return (
      <div
        className="flex items-center justify-center rounded-lg text-sm"
        style={{
          height: 300,
          backgroundColor: 'var(--surface)',
          color: 'var(--text-secondary)',
        }}
      >
        Brak danych o nastawieniu
      </div>
    );
  }

  return (
    <div style={{ width: '100%', height: 300 }}>
      <ResponsiveContainer>
        <LineChart data={data.trend} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis
            dataKey="week"
            tick={{ fontSize: 12, fill: 'var(--text-secondary)' }}
            stroke="var(--border)"
          />
          <YAxis
            domain={[-1, 1]}
            tick={{ fontSize: 12, fill: 'var(--text-secondary)' }}
            stroke="var(--border)"
            tickFormatter={(v: number) => v.toFixed(1)}
          />
          <Tooltip content={<CustomTooltip />} />
          <Line
            type="monotone"
            dataKey="score"
            stroke="#6366f1"
            strokeWidth={2}
            dot={(props) => {
              const { cx, cy, payload } = props as { cx?: number; cy?: number; payload?: { score: number } };
              if (cx == null || cy == null || !payload) return <circle r={0} />;
              return (
                <circle
                  key={`dot-${cx}`}
                  cx={cx}
                  cy={cy}
                  r={4}
                  fill={scoreToCssColor(payload.score)}
                  stroke="none"
                />
              );
            }}
            activeDot={{ r: 6 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
