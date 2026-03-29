'use client';

import { useMemo } from 'react';
import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { Calendar, Clock, Focus } from 'lucide-react';
import type { CalendarAnalytics, MeetingROI } from '@gilbertus/api-client';

export interface CalendarAnalyticsProps {
  analytics: CalendarAnalytics | undefined;
  roi: MeetingROI | undefined;
  isLoading: boolean;
}

const PIE_COLORS = ['var(--accent)', 'var(--success)', 'var(--border)'];

function KpiCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
}) {
  return (
    <div
      className="rounded-lg border p-4 flex items-center gap-3"
      style={{
        backgroundColor: 'var(--surface)',
        borderColor: 'var(--border)',
      }}
    >
      <div
        className="rounded-lg p-2"
        style={{ backgroundColor: 'var(--surface-hover)' }}
      >
        {icon}
      </div>
      <div>
        <div className="text-lg font-bold" style={{ color: 'var(--text)' }}>
          {value}
        </div>
        <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>
          {label}
        </div>
      </div>
    </div>
  );
}

function roiColor(score: number): string {
  if (score >= 7) return 'var(--success)';
  if (score >= 4) return 'var(--warning)';
  return 'var(--danger)';
}

function AnalyticsSkeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="grid grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="h-20 rounded-lg"
            style={{ backgroundColor: 'var(--surface)' }}
          />
        ))}
      </div>
      <div
        className="h-64 rounded-lg"
        style={{ backgroundColor: 'var(--surface)' }}
      />
    </div>
  );
}

export function CalendarAnalyticsPanel({
  analytics,
  roi,
  isLoading,
}: CalendarAnalyticsProps) {
  const pieData = useMemo(() => {
    if (!analytics) return [];
    const free =
      Math.max(0, 14 * 5 - analytics.total_hours - analytics.focus_time_hours); // ~70h work week estimate
    return [
      { name: 'Spotkania', value: Math.round(analytics.total_hours * 10) / 10 },
      { name: 'Czas skupienia', value: Math.round(analytics.focus_time_hours * 10) / 10 },
      { name: 'Wolny', value: Math.round(free * 10) / 10 },
    ];
  }, [analytics]);

  const barData = useMemo(() => {
    if (!analytics?.meetings_by_day) return [];
    const dayLabels: Record<string, string> = {
      monday: 'Pon',
      tuesday: 'Wt',
      wednesday: 'Śr',
      thursday: 'Czw',
      friday: 'Pt',
      saturday: 'Sob',
      sunday: 'Ndz',
    };
    return Object.entries(analytics.meetings_by_day).map(([day, count]) => ({
      day: dayLabels[day.toLowerCase()] ?? day,
      count,
    }));
  }, [analytics]);

  const sortedRoi = useMemo(() => {
    if (!roi?.meetings) return [];
    return [...roi.meetings].sort((a, b) => b.roi_score - a.roi_score);
  }, [roi]);

  if (isLoading) return <AnalyticsSkeleton />;
  if (!analytics) return null;

  return (
    <div className="space-y-6">
      {/* KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <KpiCard
          icon={<Calendar size={20} style={{ color: 'var(--accent)' }} />}
          label="Spotkania"
          value={analytics.total_meetings}
        />
        <KpiCard
          icon={<Clock size={20} style={{ color: 'var(--warning)' }} />}
          label="Godziny"
          value={`${Math.round(analytics.total_hours * 10) / 10}h`}
        />
        <KpiCard
          icon={<Focus size={20} style={{ color: 'var(--success)' }} />}
          label="Czas skupienia"
          value={`${Math.round(analytics.focus_time_hours * 10) / 10}h`}
        />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Time distribution pie */}
        <div
          className="rounded-lg border p-4"
          style={{
            backgroundColor: 'var(--surface)',
            borderColor: 'var(--border)',
          }}
        >
          <h3
            className="text-sm font-semibold mb-3"
            style={{ color: 'var(--text)' }}
          >
            Rozkład czasu
          </h3>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={80}
                dataKey="value"
                label={({ name, value }) => `${name}: ${value}h`}
              >
                {pieData.map((_, idx) => (
                  <Cell key={idx} fill={PIE_COLORS[idx % PIE_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  backgroundColor: 'var(--surface)',
                  border: '1px solid var(--border)',
                  color: 'var(--text)',
                  borderRadius: '8px',
                  fontSize: '12px',
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Meetings per day bar */}
        {barData.length > 0 && (
          <div
            className="rounded-lg border p-4"
            style={{
              backgroundColor: 'var(--surface)',
              borderColor: 'var(--border)',
            }}
          >
            <h3
              className="text-sm font-semibold mb-3"
              style={{ color: 'var(--text)' }}
            >
              Spotkania wg dnia
            </h3>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={barData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis
                  dataKey="day"
                  tick={{ fontSize: 12, fill: 'var(--text-secondary)' }}
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fontSize: 12, fill: 'var(--text-secondary)' }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'var(--surface)',
                    border: '1px solid var(--border)',
                    color: 'var(--text)',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                />
                <Bar dataKey="count" fill="var(--accent)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Meeting categories */}
      {analytics.meeting_categories &&
        Object.keys(analytics.meeting_categories).length > 0 && (
          <div
            className="rounded-lg border p-4"
            style={{
              backgroundColor: 'var(--surface)',
              borderColor: 'var(--border)',
            }}
          >
            <h3
              className="text-sm font-semibold mb-3"
              style={{ color: 'var(--text)' }}
            >
              Kategorie spotkań
            </h3>
            <div className="space-y-2">
              {Object.entries(analytics.meeting_categories)
                .sort(([, a], [, b]) => b - a)
                .map(([cat, count]) => {
                  const max = Math.max(
                    ...Object.values(analytics.meeting_categories!),
                  );
                  const pct = max > 0 ? (count / max) * 100 : 0;
                  return (
                    <div key={cat} className="flex items-center gap-2 text-xs">
                      <span
                        className="w-24 truncate"
                        style={{ color: 'var(--text-secondary)' }}
                      >
                        {cat}
                      </span>
                      <div
                        className="flex-1 h-4 rounded overflow-hidden"
                        style={{ backgroundColor: 'var(--surface-hover)' }}
                      >
                        <div
                          className="h-full rounded"
                          style={{
                            width: `${pct}%`,
                            backgroundColor: 'var(--accent)',
                          }}
                        />
                      </div>
                      <span
                        className="w-8 text-right"
                        style={{ color: 'var(--text)' }}
                      >
                        {count}
                      </span>
                    </div>
                  );
                })}
            </div>
          </div>
        )}

      {/* ROI table */}
      {sortedRoi.length > 0 && (
        <div
          className="rounded-lg border overflow-hidden"
          style={{
            backgroundColor: 'var(--surface)',
            borderColor: 'var(--border)',
          }}
        >
          <h3
            className="text-sm font-semibold p-4 pb-2"
            style={{ color: 'var(--text)' }}
          >
            ROI spotkań
          </h3>
          <table className="w-full text-xs">
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                <th
                  className="text-left px-4 py-2 font-medium"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  Spotkanie
                </th>
                <th
                  className="text-center px-4 py-2 font-medium w-20"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  ROI
                </th>
                <th
                  className="text-left px-4 py-2 font-medium"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  Powód
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedRoi.map((m, i) => (
                <tr
                  key={i}
                  style={{ borderBottom: '1px solid var(--border)' }}
                >
                  <td className="px-4 py-2" style={{ color: 'var(--text)' }}>
                    {m.subject}
                  </td>
                  <td className="px-4 py-2 text-center font-bold" style={{ color: roiColor(m.roi_score) }}>
                    {m.roi_score}
                  </td>
                  <td
                    className="px-4 py-2"
                    style={{ color: 'var(--text-secondary)' }}
                  >
                    {m.reason}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
