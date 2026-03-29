'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { ChevronDown } from 'lucide-react';
import { SourceCard } from './source-card';
import type { SourceItem } from './source-card';

interface SourcePanelProps {
  sources: SourceItem[];
}

export function SourcePanel({ sources }: SourcePanelProps) {
  const [expanded, setExpanded] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);
  const [contentHeight, setContentHeight] = useState(0);

  useEffect(() => {
    if (contentRef.current) {
      setContentHeight(contentRef.current.scrollHeight);
    }
  }, [sources, expanded]);

  const toggle = useCallback(() => setExpanded((prev) => !prev), []);

  if (sources.length === 0) return null;

  return (
    <div className="mt-2">
      <button
        onClick={toggle}
        className="flex items-center gap-1.5 text-sm text-[var(--text-secondary)] hover:text-[var(--text)] transition-colors"
      >
        <ChevronDown
          size={16}
          className={`transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`}
        />
        <span>
          {sources.length} {sources.length === 1 ? 'źródło' : sources.length < 5 ? 'źródła' : 'źródeł'}
        </span>
      </button>
      <div
        className="overflow-hidden transition-[max-height] duration-300 ease-in-out"
        style={{ maxHeight: expanded ? `${contentHeight}px` : '0px' }}
      >
        <div ref={contentRef} className="grid grid-cols-1 md:grid-cols-2 gap-2 pt-2">
          {sources.map((source) => (
            <SourceCard key={source.document_id} source={source} />
          ))}
        </div>
      </div>
    </div>
  );
}
