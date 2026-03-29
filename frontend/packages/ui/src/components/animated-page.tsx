'use client';

import type { ReactNode } from 'react';

interface AnimatedPageProps {
  children: ReactNode;
  className?: string;
}

export function AnimatedPage({ children, className }: AnimatedPageProps) {
  return <div className={`animate-fade-in ${className ?? ''}`}>{children}</div>;
}
