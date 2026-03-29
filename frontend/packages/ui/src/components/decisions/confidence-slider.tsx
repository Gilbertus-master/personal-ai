'use client';

import { useMemo } from 'react';

export interface ConfidenceSliderProps {
  value: number;
  onChange: (v: number) => void;
  disabled?: boolean;
}

const TICKS = [0, 25, 50, 75, 100];

function getColor(val: number): string {
  if (val <= 25) return 'var(--danger)';
  if (val <= 50) return 'var(--warning)';
  return 'var(--success)';
}

export function ConfidenceSlider({ value, onChange, disabled = false }: ConfidenceSliderProps) {
  const color = useMemo(() => getColor(value), [value]);
  const pct = Math.round(value);

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
          Pewność
        </span>
        <span className="text-xs font-medium" style={{ color }}>
          {pct}%
        </span>
      </div>
      <input
        type="range"
        min={0}
        max={100}
        step={1}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        disabled={disabled}
        className="h-2 w-full cursor-pointer appearance-none rounded-full disabled:cursor-default disabled:opacity-50"
        style={{
          background: `linear-gradient(to right, var(--danger) 0%, var(--warning) 40%, var(--success) 70%, var(--success) 100%)`,
          accentColor: color,
        }}
      />
      <div className="flex justify-between">
        {TICKS.map((t) => (
          <span key={t} className="text-[10px]" style={{ color: 'var(--text-secondary)' }}>
            {t}%
          </span>
        ))}
      </div>
    </div>
  );
}
