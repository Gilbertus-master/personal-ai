'use client';

import type { GoalProgress } from '@gilbertus/api-client';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';

interface GoalProgressChartProps {
  progress: GoalProgress[];
  targetValue: number;
  unit?: string;
  isLoading?: boolean;
}

interface TooltipPayloadItem {
  payload?: GoalProgress;
}

function CustomTooltip({
  active,
  payload,
  unit,
}: {
  active?: boolean;
  payload?: TooltipPayloadItem[];
  unit?: string;
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
      <p className="font-medium">{d.date}</p>
      <p style={{ color: '#6366f1' }}>
        Wartość: {d.value.toLocaleString('pl-PL')} {unit ?? ''}
      </p>
      {d.note && (
        <p className="mt-0.5 text-[var(--text-secondary)]">{d.note}</p>
      )}
    </div>
  );
}

export function GoalProgressChart({
  progress,
  targetValue,
  unit,
  isLoading = false,
}: GoalProgressChartProps) {
  if (isLoading) {
    return (
      <div
        className="animate-pulse rounded-lg"
        style={{ height: 300, backgroundColor: 'var(--surface)' }}
      />
    );
  }

  if (!progress?.length) {
    return (
      <div
        className="flex items-center justify-center rounded-lg text-sm"
        style={{
          height: 300,
          backgroundColor: 'var(--surface)',
          color: 'var(--text-secondary)',
        }}
      >
        Brak danych o postępie
      </div>
    );
  }

  return (
    <div style={{ width: '100%', height: 300 }}>
      <ResponsiveContainer>
        <AreaChart data={progress} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <defs>
            <linearGradient id="goalFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 12, fill: 'var(--text-secondary)' }}
            stroke="var(--border)"
          />
          <YAxis
            tick={{ fontSize: 12, fill: 'var(--text-secondary)' }}
            stroke="var(--border)"
            label={
              unit
                ? { value: unit, angle: -90, position: 'insideLeft', fill: 'var(--text-secondary)', fontSize: 12 }
                : undefined
            }
          />
          <Tooltip content={<CustomTooltip unit={unit} />} />
          <ReferenceLine
            y={targetValue}
            stroke="var(--warning)"
            strokeDasharray="6 4"
            label={{
              value: `Cel: ${targetValue.toLocaleString('pl-PL')}`,
              position: 'right',
              fill: 'var(--warning)',
              fontSize: 12,
            }}
          />
          <Area
            type="monotone"
            dataKey="value"
            stroke="#6366f1"
            strokeWidth={2}
            fill="url(#goalFill)"
            dot={{ r: 3, fill: '#6366f1' }}
            activeDot={{ r: 5 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
