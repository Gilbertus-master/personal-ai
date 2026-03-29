'use client';

import type { ComplianceMatter } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';
import { ComplianceBadge } from './compliance-badge';
import { PhaseTimeline } from './phase-timeline';
import { MatterActions } from './matter-actions';
import { RbacGate } from '../rbac-gate';
import { CheckCircle, Circle, Clock } from 'lucide-react';

export interface MatterDetailProps {
  matter: ComplianceMatter | undefined;
  isLoading?: boolean;
  activeTab: 'overview' | 'analysis' | 'action_plan' | 'communication' | 'report';
  onTabChange: (tab: 'overview' | 'analysis' | 'action_plan' | 'communication' | 'report') => void;
  // Actions
  onResearch: (id: number) => void;
  onAdvance: (id: number) => void;
  onReport: (id: number) => void;
  onCommPlan: (id: number) => void;
  onExecuteComm: (id: number) => void;
  isResearching?: boolean;
  isAdvancing?: boolean;
  isReporting?: boolean;
  isCommPlanning?: boolean;
  isExecutingComm?: boolean;
}

const TABS = [
  { key: 'overview' as const, label: 'Przegląd' },
  { key: 'analysis' as const, label: 'Analiza' },
  { key: 'action_plan' as const, label: 'Plan działań' },
  { key: 'communication' as const, label: 'Komunikacja' },
  { key: 'report' as const, label: 'Raport' },
];

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '\u2014';
  try {
    return new Intl.DateTimeFormat('pl-PL', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(dateStr));
  } catch {
    return '\u2014';
  }
}

function SkeletonDetail() {
  return (
    <div className="space-y-6">
      <div className="h-8 w-2/3 rounded bg-[var(--surface)] animate-pulse" />
      <div className="h-10 w-full rounded bg-[var(--surface)] animate-pulse" />
      <div className="h-40 w-full rounded bg-[var(--surface)] animate-pulse" />
    </div>
  );
}

function MarkdownBlock({ content }: { content: string | undefined }) {
  if (!content) {
    return <p className="text-sm text-[var(--text-secondary)]">Brak danych</p>;
  }
  return (
    <div
      className="prose prose-invert prose-sm max-w-none text-[var(--text)]"
      style={{ whiteSpace: 'pre-wrap' }}
    >
      {content}
    </div>
  );
}

function RiskAnalysisCards({ data }: { data: Record<string, unknown> | undefined }) {
  if (!data || Object.keys(data).length === 0) {
    return <p className="text-sm text-[var(--text-secondary)]">Brak analizy ryzyka</p>;
  }
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {Object.entries(data).map(([key, value]) => (
        <div
          key={key}
          className="rounded-lg border border-[var(--border)] p-3"
          style={{ backgroundColor: 'var(--surface)' }}
        >
          <div className="text-xs font-medium text-[var(--text-secondary)]">{key}</div>
          <div className="mt-1 text-sm text-[var(--text)]">
            {typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}
          </div>
        </div>
      ))}
    </div>
  );
}

function ActionPlanList({ items }: { items: Record<string, unknown>[] | undefined }) {
  if (!items || items.length === 0) {
    return <p className="text-sm text-[var(--text-secondary)]">Brak planu działań</p>;
  }
  return (
    <div className="space-y-2">
      {items.map((item, i) => {
        const title = String(item.title ?? item.name ?? `Punkt ${i + 1}`);
        const desc = String(item.description ?? '');
        const status = String(item.status ?? 'pending');
        const isComplete = status === 'completed' || status === 'done';

        return (
          <div
            key={i}
            className="flex items-start gap-3 rounded-lg border border-[var(--border)] p-3"
            style={{ backgroundColor: 'var(--surface)' }}
          >
            {isComplete ? (
              <CheckCircle className="mt-0.5 h-4 w-4 shrink-0 text-green-400" />
            ) : (
              <Circle className="mt-0.5 h-4 w-4 shrink-0 text-[var(--text-secondary)]" />
            )}
            <div className="min-w-0">
              <div className={cn('text-sm font-medium', isComplete ? 'text-green-400 line-through' : 'text-[var(--text)]')}>
                {title}
              </div>
              {desc && <div className="mt-0.5 text-xs text-[var(--text-secondary)]">{desc}</div>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function CommunicationTable({ items }: { items: Record<string, unknown>[] | undefined }) {
  if (!items || items.length === 0) {
    return <p className="text-sm text-[var(--text-secondary)]">Brak planu komunikacji</p>;
  }
  return (
    <div className="border border-[var(--border)] rounded-lg overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--border)] bg-[var(--surface)]">
            <th className="px-4 py-2 text-left text-xs font-medium text-[var(--text-secondary)]">Odbiorca</th>
            <th className="px-4 py-2 text-left text-xs font-medium text-[var(--text-secondary)]">Kanał</th>
            <th className="px-4 py-2 text-left text-xs font-medium text-[var(--text-secondary)]">Termin</th>
            <th className="px-4 py-2 text-left text-xs font-medium text-[var(--text-secondary)]">Status</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, i) => (
            <tr key={i} className="border-b border-[var(--border)]">
              <td className="px-4 py-2 text-[var(--text)]">
                {String(item.recipient ?? item.name ?? '\u2014')}
              </td>
              <td className="px-4 py-2 text-[var(--text-secondary)]">
                {String(item.channel ?? item.method ?? '\u2014')}
              </td>
              <td className="px-4 py-2 text-[var(--text-secondary)]">
                {String(item.timeline ?? item.deadline ?? '\u2014')}
              </td>
              <td className="px-4 py-2 text-[var(--text-secondary)]">
                {String(item.status ?? '\u2014')}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function MatterDetail({
  matter,
  isLoading,
  activeTab,
  onTabChange,
  onResearch,
  onAdvance,
  onReport,
  onCommPlan,
  onExecuteComm,
  isResearching,
  isAdvancing,
  isReporting,
  isCommPlanning,
  isExecutingComm,
}: MatterDetailProps) {
  if (isLoading || !matter) return <SkeletonDetail />;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="space-y-3">
        <h1 className="text-2xl font-bold text-[var(--text)]">{matter.title}</h1>
        <div className="flex flex-wrap items-center gap-2">
          <ComplianceBadge type="matter_type" value={matter.matter_type} size="md" />
          <ComplianceBadge type="area" value={matter.area_code} size="md" />
          <ComplianceBadge type="priority" value={matter.priority} size="md" />
          <ComplianceBadge type="status" value={matter.status} size="md" />
        </div>
        <div className="flex items-center gap-4 text-xs text-[var(--text-secondary)]">
          <span className="flex items-center gap-1">
            <Clock size={12} />
            Utworzono: {formatDate(matter.created_at)}
          </span>
          <span>Aktualizacja: {formatDate(matter.updated_at)}</span>
          {matter.completed_at && <span>Zakończono: {formatDate(matter.completed_at)}</span>}
        </div>
      </div>

      {/* Phase Timeline */}
      <div
        className="rounded-lg border border-[var(--border)] p-4"
        style={{ backgroundColor: 'var(--surface)' }}
      >
        <PhaseTimeline currentPhase={matter.phase} />
      </div>

      {/* Actions (board+ only) */}
      <RbacGate roles={['ceo', 'board', 'gilbertus_admin']}>
        <MatterActions
          matterId={matter.id}
          onResearch={onResearch}
          onAdvance={onAdvance}
          onReport={onReport}
          onCommPlan={onCommPlan}
          onExecuteComm={onExecuteComm}
          isResearching={isResearching}
          isAdvancing={isAdvancing}
          isReporting={isReporting}
          isCommPlanning={isCommPlanning}
          isExecutingComm={isExecutingComm}
        />
      </RbacGate>

      {/* Tab Bar */}
      <div className="flex gap-0 border-b border-[var(--border)]">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => onTabChange(tab.key)}
            className={cn(
              'px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px',
              activeTab === tab.key
                ? 'border-[var(--accent)] text-[var(--text)]'
                : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text)]',
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div>
        {activeTab === 'overview' && (
          <div className="space-y-4">
            {matter.description && (
              <div>
                <h3 className="mb-2 text-sm font-medium text-[var(--text-secondary)]">Opis</h3>
                <p className="text-sm text-[var(--text)]" style={{ whiteSpace: 'pre-wrap' }}>
                  {matter.description}
                </p>
              </div>
            )}
            {matter.source_regulation && (
              <div>
                <h3 className="mb-2 text-sm font-medium text-[var(--text-secondary)]">
                  Regulacja źródłowa
                </h3>
                <p className="text-sm text-[var(--text)]">{matter.source_regulation}</p>
              </div>
            )}
            {!matter.description && !matter.source_regulation && (
              <p className="text-sm text-[var(--text-secondary)]">Brak szczegółów</p>
            )}
          </div>
        )}

        {activeTab === 'analysis' && (
          <div className="space-y-6">
            <div>
              <h3 className="mb-2 text-sm font-medium text-[var(--text-secondary)]">
                Analiza prawna
              </h3>
              <MarkdownBlock content={matter.legal_analysis} />
            </div>
            <div>
              <h3 className="mb-2 text-sm font-medium text-[var(--text-secondary)]">
                Analiza ryzyka
              </h3>
              <RiskAnalysisCards data={matter.risk_analysis} />
            </div>
          </div>
        )}

        {activeTab === 'action_plan' && (
          <ActionPlanList items={matter.action_plan} />
        )}

        {activeTab === 'communication' && (
          <CommunicationTable items={matter.communication_plan} />
        )}

        {activeTab === 'report' && (
          <div className="space-y-6">
            <div>
              <h3 className="mb-2 text-sm font-medium text-[var(--text-secondary)]">
                Raport obowiązków
              </h3>
              <MarkdownBlock content={matter.obligations_report} />
            </div>
            <div>
              <h3 className="mb-2 text-sm font-medium text-[var(--text-secondary)]">
                Raport konsekwencji
              </h3>
              <MarkdownBlock content={matter.consequences_report} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
