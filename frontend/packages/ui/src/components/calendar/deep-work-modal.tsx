'use client';

import { useState, useMemo } from 'react';
import { X, Loader2, Shield } from 'lucide-react';
import type { DeepWorkRequest } from '@gilbertus/api-client';

export interface DeepWorkModalProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: DeepWorkRequest) => void;
  isLoading?: boolean;
}

function getTomorrow(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return d.toISOString().slice(0, 10);
}

const START_OPTIONS = Array.from({ length: 6 }, (_, i) => 7 + i); // 7-12
const END_OPTIONS = Array.from({ length: 11 }, (_, i) => 8 + i); // 8-18

export function DeepWorkModal({
  open,
  onClose,
  onSubmit,
  isLoading = false,
}: DeepWorkModalProps) {
  const [date, setDate] = useState(getTomorrow);
  const [startHour, setStartHour] = useState(9);
  const [endHour, setEndHour] = useState(11);

  const duration = useMemo(
    () => Math.max(0, endHour - startHour),
    [startHour, endHour],
  );

  const validEndOptions = useMemo(
    () => END_OPTIONS.filter((h) => h > startHour),
    [startHour],
  );

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (endHour <= startHour) return;
    onSubmit({ date, start_hour: startHour, end_hour: endHour });
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0"
        style={{ backgroundColor: 'rgba(0,0,0,0.6)' }}
        onClick={onClose}
      />

      {/* Modal */}
      <div
        className="relative rounded-xl border p-6 w-full max-w-md shadow-xl"
        style={{
          backgroundColor: 'var(--bg)',
          borderColor: 'var(--border)',
          color: 'var(--text)',
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Shield size={18} style={{ color: 'var(--accent)' }} />
            <h2 className="text-base font-semibold">Blokada Deep Work</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded hover:brightness-110"
            style={{ color: 'var(--text-secondary)' }}
          >
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Date */}
          <div>
            <label
              className="block text-xs font-medium mb-1"
              style={{ color: 'var(--text-secondary)' }}
            >
              Data
            </label>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="w-full rounded-lg border px-3 py-2 text-sm outline-none focus:ring-2"
              style={{
                backgroundColor: 'var(--surface)',
                borderColor: 'var(--border)',
                color: 'var(--text)',
                // @ts-expect-error CSS custom property for ring color
                '--tw-ring-color': 'var(--accent)',
              }}
            />
          </div>

          {/* Time selectors */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label
                className="block text-xs font-medium mb-1"
                style={{ color: 'var(--text-secondary)' }}
              >
                Od
              </label>
              <select
                value={startHour}
                onChange={(e) => {
                  const v = Number(e.target.value);
                  setStartHour(v);
                  if (endHour <= v) setEndHour(v + 1);
                }}
                className="w-full rounded-lg border px-3 py-2 text-sm outline-none"
                style={{
                  backgroundColor: 'var(--surface)',
                  borderColor: 'var(--border)',
                  color: 'var(--text)',
                }}
              >
                {START_OPTIONS.map((h) => (
                  <option key={h} value={h}>
                    {String(h).padStart(2, '0')}:00
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label
                className="block text-xs font-medium mb-1"
                style={{ color: 'var(--text-secondary)' }}
              >
                Do
              </label>
              <select
                value={endHour}
                onChange={(e) => setEndHour(Number(e.target.value))}
                className="w-full rounded-lg border px-3 py-2 text-sm outline-none"
                style={{
                  backgroundColor: 'var(--surface)',
                  borderColor: 'var(--border)',
                  color: 'var(--text)',
                }}
              >
                {validEndOptions.map((h) => (
                  <option key={h} value={h}>
                    {String(h).padStart(2, '0')}:00
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Duration display */}
          <div
            className="text-center text-sm py-2 rounded-lg"
            style={{
              backgroundColor: 'var(--surface-hover)',
              color: 'var(--accent)',
            }}
          >
            Czas trwania: <strong>{duration}h</strong>
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={isLoading || duration <= 0}
            className="w-full rounded-lg px-4 py-2.5 text-sm font-medium transition-colors disabled:opacity-50"
            style={{
              backgroundColor: 'var(--accent)',
              color: '#fff',
            }}
          >
            {isLoading ? (
              <Loader2 size={16} className="animate-spin mx-auto" />
            ) : (
              'Zablokuj czas'
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
