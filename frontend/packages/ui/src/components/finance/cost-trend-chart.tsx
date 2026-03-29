'use client';

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';

interface CostDataPoint {
  month: string;
  total_usd: number;
  api_calls: number;
}

interface CostTrendChartProps {
  data: CostDataPoint[];
  forecast?: number;
  isLoading?: boolean;
}

interface TooltipPayloadItem {
  payload?: CostDataPoint;
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
      <p className="font-medium">{d.month}</p>
      <p style={{ color: '#6366f1' }}>
        Koszt: ${d.total_usd.toLocaleString('en-US', { minimumFractionDigits: 2 })}
      </p>
      <p style={{ color: 'var(--text-secondary)' }}>
        Wywołania API: {d.api_calls.toLocaleString('pl-PL')}
      </p>
    </div>
  );
}

export function CostTrendChart({ data, forecast, isLoading = false }: CostTrendChartProps) {
  if (isLoading) {
    return (
      <div
        className="animate-pulse rounded-lg"
        style={{ height: 300, backgroundColor: 'var(--surface)' }}
      />
    );
  }

  if (!data?.length) {
    return (
      <div
        className="flex items-center justify-center rounded-lg text-sm"
        style={{
          height: 300,
          backgroundColor: 'var(--surface)',
          color: 'var(--text-secondary)',
        }}
      >
        Brak danych o kosztach
      </div>
    );
  }

  return (
    <div style={{ width: '100%', height: 300 }}>
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis
            dataKey="month"
            tick={{ fontSize: 12, fill: 'var(--text-secondary)' }}
            stroke="var(--border)"
          />
          <YAxis
            yAxisId="usd"
            tick={{ fontSize: 12, fill: 'var(--text-secondary)' }}
            stroke="var(--border)"
            tickFormatter={(v: number) => `$${v}`}
          />
          <YAxis
            yAxisId="calls"
            orientation="right"
            tick={{ fontSize: 12, fill: 'var(--text-secondary)' }}
            stroke="var(--border)"
          />
          <Tooltip content={<CustomTooltip />} />
          <Line
            yAxisId="usd"
            type="monotone"
            dataKey="total_usd"
            stroke="#6366f1"
            strokeWidth={2}
            dot={{ r: 3, fill: '#6366f1' }}
            activeDot={{ r: 5 }}
          />
          <Line
            yAxisId="calls"
            type="monotone"
            dataKey="api_calls"
            stroke="var(--text-muted)"
            strokeWidth={1.5}
            strokeDasharray="5 3"
            dot={false}
          />
          {forecast != null && (
            <ReferenceLine
              yAxisId="usd"
              y={forecast}
              stroke="var(--warning)"
              strokeDasharray="6 4"
              label={{
                value: `Prognoza: $${forecast}`,
                position: 'right',
                fill: 'var(--warning)',
                fontSize: 12,
              }}
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
