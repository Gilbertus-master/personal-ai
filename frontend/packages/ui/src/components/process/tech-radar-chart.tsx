'use client';

import { useState, useCallback } from 'react';
import type { TechSolution } from '@gilbertus/api-client';

export interface TechRadarChartProps {
  solutions: TechSolution[];
  onSolutionClick?: (id: number) => void;
}

type Quadrant = 'adopt' | 'trial' | 'assess' | 'hold';

interface PlacedSolution {
  solution: TechSolution;
  quadrant: Quadrant;
  x: number;
  y: number;
  radius: number;
}

const QUADRANT_LABELS: Record<Quadrant, string> = {
  adopt: 'Adoptuj',
  trial: 'Testuj',
  assess: 'Oceniaj',
  hold: 'Wstrzymaj',
};

const QUADRANT_FILLS: Record<Quadrant, string> = {
  adopt: 'rgba(34,197,94,0.06)',
  trial: 'rgba(59,130,246,0.06)',
  assess: 'rgba(251,191,36,0.06)',
  hold: 'rgba(239,68,68,0.06)',
};

const TYPE_COLORS: Record<TechSolution['solution_type'], string> = {
  build: '#3b82f6',
  buy: '#22c55e',
  extend: '#a855f7',
};

function getQuadrant(status: TechSolution['status']): Quadrant {
  switch (status) {
    case 'deployed': return 'adopt';
    case 'approved':
    case 'in_development': return 'trial';
    case 'proposed': return 'assess';
    case 'rejected': return 'hold';
  }
}

function seededRandom(seed: number): number {
  const x = Math.sin(seed) * 10000;
  return x - Math.floor(x);
}

function placeSolutions(solutions: TechSolution[]): PlacedSolution[] {
  const maxRoi = Math.max(...solutions.map((s) => s.roi_ratio), 1);
  const SIZE = 400;
  const HALF = SIZE / 2;
  const MARGIN = 40;

  return solutions.map((s, i) => {
    const quadrant = getQuadrant(s.status);
    const radius = 4 + (s.roi_ratio / maxRoi) * 8;

    // Determine quadrant bounds
    const rand1 = seededRandom(s.id * 13 + i * 7);
    const rand2 = seededRandom(s.id * 31 + i * 11);
    let x: number;
    let y: number;

    switch (quadrant) {
      case 'adopt': // top-right
        x = HALF + MARGIN + rand1 * (HALF - MARGIN * 2);
        y = MARGIN + rand2 * (HALF - MARGIN * 2);
        break;
      case 'trial': // top-left
        x = MARGIN + rand1 * (HALF - MARGIN * 2);
        y = MARGIN + rand2 * (HALF - MARGIN * 2);
        break;
      case 'assess': // bottom-left
        x = MARGIN + rand1 * (HALF - MARGIN * 2);
        y = HALF + MARGIN + rand2 * (HALF - MARGIN * 2);
        break;
      case 'hold': // bottom-right
        x = HALF + MARGIN + rand1 * (HALF - MARGIN * 2);
        y = HALF + MARGIN + rand2 * (HALF - MARGIN * 2);
        break;
    }

    return { solution: s, quadrant, x, y, radius };
  });
}

function formatPLN(amount: number): string {
  return new Intl.NumberFormat('pl-PL', { style: 'currency', currency: 'PLN', maximumFractionDigits: 0 }).format(amount);
}

export function TechRadarChart({ solutions, onSolutionClick }: TechRadarChartProps) {
  const [hoveredId, setHoveredId] = useState<number | null>(null);
  const placed = placeSolutions(solutions);

  const handleClick = useCallback(
    (id: number) => {
      onSolutionClick?.(id);
    },
    [onSolutionClick],
  );

  const hovered = placed.find((p) => p.solution.id === hoveredId);

  return (
    <div className="relative">
      <svg viewBox="0 0 400 400" className="h-auto w-full max-w-[400px]" role="img" aria-label="Tech Radar">
        {/* Quadrant backgrounds */}
        <rect x="200" y="0" width="200" height="200" fill={QUADRANT_FILLS.adopt} />
        <rect x="0" y="0" width="200" height="200" fill={QUADRANT_FILLS.trial} />
        <rect x="0" y="200" width="200" height="200" fill={QUADRANT_FILLS.assess} />
        <rect x="200" y="200" width="200" height="200" fill={QUADRANT_FILLS.hold} />

        {/* Grid lines */}
        <line x1="200" y1="0" x2="200" y2="400" stroke="var(--border)" strokeWidth="1" />
        <line x1="0" y1="200" x2="400" y2="200" stroke="var(--border)" strokeWidth="1" />

        {/* Quadrant labels */}
        <text x="300" y="24" textAnchor="middle" fill="var(--text-secondary)" fontSize="11" fontWeight="600">
          {QUADRANT_LABELS.adopt}
        </text>
        <text x="100" y="24" textAnchor="middle" fill="var(--text-secondary)" fontSize="11" fontWeight="600">
          {QUADRANT_LABELS.trial}
        </text>
        <text x="100" y="390" textAnchor="middle" fill="var(--text-secondary)" fontSize="11" fontWeight="600">
          {QUADRANT_LABELS.assess}
        </text>
        <text x="300" y="390" textAnchor="middle" fill="var(--text-secondary)" fontSize="11" fontWeight="600">
          {QUADRANT_LABELS.hold}
        </text>

        {/* Solution dots */}
        {placed.map((p) => (
          <circle
            key={p.solution.id}
            cx={p.x}
            cy={p.y}
            r={hoveredId === p.solution.id ? p.radius + 2 : p.radius}
            fill={TYPE_COLORS[p.solution.solution_type]}
            opacity={hoveredId === null || hoveredId === p.solution.id ? 0.85 : 0.35}
            className="cursor-pointer transition-opacity"
            onMouseEnter={() => setHoveredId(p.solution.id)}
            onMouseLeave={() => setHoveredId(null)}
            onClick={() => handleClick(p.solution.id)}
          />
        ))}
      </svg>

      {/* Tooltip */}
      {hovered && (
        <div className="pointer-events-none absolute left-1/2 top-0 z-10 -translate-x-1/2 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-2.5 shadow-lg">
          <p className="text-xs font-medium text-[var(--text)]">{hovered.solution.name}</p>
          <p className="mt-0.5 text-[10px] text-[var(--text-secondary)]">
            ROI: {hovered.solution.roi_ratio.toFixed(1)}x
          </p>
          <p className="text-[10px] text-[var(--text-secondary)]">
            Oszczędności: {formatPLN(hovered.solution.estimated_annual_savings_pln)}
          </p>
        </div>
      )}

      {/* Legend */}
      <div className="mt-3 flex flex-wrap items-center gap-4 text-[10px] text-[var(--text-secondary)]">
        {(Object.entries(TYPE_COLORS) as [TechSolution['solution_type'], string][]).map(([type, color]) => (
          <span key={type} className="flex items-center gap-1">
            <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
            {type === 'build' ? 'Budowa' : type === 'buy' ? 'Zakup' : 'Rozszerzenie'}
          </span>
        ))}
      </div>
    </div>
  );
}
