'use client';

import { useState } from 'react';
import { Clock, User, AlertTriangle, FileText, Play } from 'lucide-react';
import { cn } from '../../lib/utils';
import { MarkdownRenderer } from '../chat/markdown-renderer';
import type { CorrelationType, CorrelationRequest, CorrelationResult } from '@gilbertus/api-client';

interface CorrelationExplorerProps {
  correlationType: CorrelationType;
  onTypeChange: (type: CorrelationType) => void;
  params: Record<string, string>;
  onParamChange: (key: string, value: string) => void;
  onReset: () => void;
  onRun: (request: CorrelationRequest) => void;
  result?: CorrelationResult | null;
  isRunning?: boolean;
}

const TYPES: Array<{
  value: CorrelationType;
  label: string;
  description: string;
  Icon: typeof Clock;
}> = [
  { value: 'temporal', label: 'Korelacja czasowa', description: 'Znajdź powiązania między typami zdarzeń w czasie', Icon: Clock },
  { value: 'person', label: 'Profil osoby', description: 'Analiza wzorców zachowań osoby', Icon: User },
  { value: 'anomaly', label: 'Anomalie', description: 'Wykryj nietypowe wzorce', Icon: AlertTriangle },
  { value: 'report', label: 'Raport', description: 'Pełny raport korelacji', Icon: FileText },
];

function WindowToggle({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex rounded-lg border border-[var(--border)] overflow-hidden">
      {(['week', 'month'] as const).map((w) => (
        <button
          key={w}
          onClick={() => onChange(w)}
          className={cn(
            'px-4 py-2 text-sm font-medium transition-colors',
            value === w
              ? 'bg-[var(--accent)] text-white'
              : 'bg-[var(--surface)] text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]',
          )}
        >
          {w === 'week' ? 'Tydzień' : 'Miesiąc'}
        </button>
      ))}
    </div>
  );
}

function canRun(type: CorrelationType, params: Record<string, string>): boolean {
  if (type === 'temporal') return !!(params.event_type_a && params.event_type_b);
  if (type === 'person') return !!params.person;
  return true;
}

function buildRequest(type: CorrelationType, params: Record<string, string>): CorrelationRequest {
  return {
    correlation_type: type,
    event_type_a: params.event_type_a || null,
    event_type_b: params.event_type_b || null,
    person: params.person || null,
    window: (params.window as 'week' | 'month') || 'week',
  };
}

export function CorrelationExplorer({
  correlationType,
  onTypeChange,
  params,
  onParamChange,
  onReset,
  onRun,
  result,
  isRunning,
}: CorrelationExplorerProps) {
  return (
    <div className="space-y-6">
      {/* Step 1: Type selector */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {TYPES.map((t) => (
          <button
            key={t.value}
            onClick={() => {
              onTypeChange(t.value);
              onReset();
            }}
            className={cn(
              'flex flex-col items-start gap-2 rounded-lg border p-4 text-left transition-colors',
              correlationType === t.value
                ? 'border-[var(--accent)] bg-[var(--accent)]/5'
                : 'border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-hover)]',
            )}
          >
            <t.Icon
              className={cn(
                'h-5 w-5',
                correlationType === t.value ? 'text-[var(--accent)]' : 'text-[var(--text-muted)]',
              )}
            />
            <span className="text-sm font-medium text-[var(--text)]">{t.label}</span>
            <span className="text-xs text-[var(--text-secondary)]">{t.description}</span>
          </button>
        ))}
      </div>

      {/* Step 2: Dynamic params */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 space-y-4">
        {correlationType === 'temporal' && (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-[var(--text-secondary)]">Typ zdarzeń A</label>
                <input
                  type="text"
                  value={params.event_type_a || ''}
                  onChange={(e) => onParamChange('event_type_a', e.target.value)}
                  placeholder="np. meeting, decision"
                  className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-muted)] focus:border-[var(--accent)] focus:outline-none"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-[var(--text-secondary)]">Typ zdarzeń B</label>
                <input
                  type="text"
                  value={params.event_type_b || ''}
                  onChange={(e) => onParamChange('event_type_b', e.target.value)}
                  placeholder="np. conflict, escalation"
                  className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-muted)] focus:border-[var(--accent)] focus:outline-none"
                />
              </div>
            </div>
            <WindowToggle
              value={params.window || 'week'}
              onChange={(v) => onParamChange('window', v)}
            />
          </>
        )}

        {correlationType === 'person' && (
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-[var(--text-secondary)]">Osoba</label>
            <input
              type="text"
              value={params.person || ''}
              onChange={(e) => onParamChange('person', e.target.value)}
              placeholder="Imię i nazwisko"
              className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-muted)] focus:border-[var(--accent)] focus:outline-none"
            />
          </div>
        )}

        {(correlationType === 'anomaly' || correlationType === 'report') && (
          <WindowToggle
            value={params.window || 'week'}
            onChange={(v) => onParamChange('window', v)}
          />
        )}
      </div>

      {/* Step 3: Run button */}
      <button
        onClick={() => onRun(buildRequest(correlationType, params))}
        disabled={!canRun(correlationType, params) || isRunning}
        className={cn(
          'flex items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-medium transition-colors',
          'bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)]',
          'disabled:opacity-50 disabled:cursor-not-allowed',
        )}
      >
        <Play className={cn('h-4 w-4', isRunning && 'animate-pulse')} />
        {isRunning ? 'Analizuję...' : 'Analizuj'}
      </button>

      {/* Step 4: Result display */}
      {result && (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 space-y-3">
          <h3 className="text-sm font-medium text-[var(--text)]">Wynik analizy</h3>
          <div className="text-sm text-[var(--text)]">
            {typeof result.data === 'string' ? (
              <MarkdownRenderer content={result.data} />
            ) : (
              <pre className="whitespace-pre-wrap text-xs bg-[var(--bg)] rounded-md p-3 overflow-x-auto">
                {JSON.stringify(result.data, null, 2)}
              </pre>
            )}
          </div>
          {result.latency_ms != null && (
            <p className="text-xs text-[var(--text-muted)]">
              Czas: {result.latency_ms.toFixed(0)} ms
            </p>
          )}
        </div>
      )}
    </div>
  );
}
