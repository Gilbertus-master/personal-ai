'use client';

import { useState } from 'react';
import { Star } from 'lucide-react';

export interface StarRatingProps {
  value: number;
  onChange?: (v: number) => void;
  readonly?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

const SIZES: Record<string, number> = { sm: 16, md: 20, lg: 24 };

export function StarRating({ value, onChange, readonly = false, size = 'md' }: StarRatingProps) {
  const [hovered, setHovered] = useState(0);
  const px = SIZES[size];
  const interactive = !readonly && !!onChange;
  const display = interactive && hovered > 0 ? hovered : value;

  return (
    <div
      className="inline-flex gap-0.5"
      onMouseLeave={() => interactive && setHovered(0)}
    >
      {[1, 2, 3, 4, 5].map((star) => {
        const filled = star <= display;
        return (
          <button
            key={star}
            type="button"
            disabled={!interactive}
            onClick={() => interactive && onChange!(star)}
            onMouseEnter={() => interactive && setHovered(star)}
            className="disabled:cursor-default"
            style={{ color: filled ? 'var(--warning)' : 'var(--border)', lineHeight: 0 }}
          >
            <Star size={px} fill={filled ? 'currentColor' : 'none'} strokeWidth={1.5} />
          </button>
        );
      })}
    </div>
  );
}
