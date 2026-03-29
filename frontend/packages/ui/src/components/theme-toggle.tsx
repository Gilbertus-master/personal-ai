'use client';

import { useTheme } from 'next-themes';
import { Sun, Moon, Monitor } from 'lucide-react';

const CYCLE = ['dark', 'light', 'system'] as const;

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();

  const next = () => {
    const idx = CYCLE.indexOf(theme as (typeof CYCLE)[number]);
    setTheme(CYCLE[(idx + 1) % CYCLE.length]);
  };

  const Icon = theme === 'light' ? Sun : theme === 'system' ? Monitor : Moon;

  return (
    <button
      onClick={next}
      className="inline-flex items-center justify-center rounded-md p-2 text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
      aria-label="Toggle theme"
    >
      <Icon className="h-5 w-5" />
    </button>
  );
}
