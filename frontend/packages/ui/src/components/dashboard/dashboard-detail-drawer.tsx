'use client';

import { useState, useEffect, useMemo } from 'react';
import {
  X,
  FileText,
  Calendar,
  Users,
  Target,
  DollarSign,
  AlertTriangle,
  AlertCircle,
  Info,
  Loader2,
  ChevronRight,
  Mail,
  MessageSquare,
  Phone,
  Mic,
  File,
  Clock,
  Filter,
} from 'lucide-react';
import type {
  StatusResponse,
  TimelineResponse,
  TimelineEvent,
  CommitmentsListResponse,
  CommitmentItem,
  BudgetResponse,
  AlertsResponse,
  AlertItem as AlertItemType,
} from '@gilbertus/api-client';
import {
  fetchStatus,
  fetchTimeline,
  fetchCommitments,
  fetchBudget,
  fetchAlerts,
} from '@gilbertus/api-client';
import { cn } from '../../lib/utils';
import { ActionableItem } from '../shared/actionable-item';
import type { TileKey } from './kpi-grid';

interface DashboardDetailDrawerProps {
  tile: TileKey | null;
  onClose: () => void;
  onOpenAlert?: (alert: AlertItemType) => void;
}

const TILE_CONFIG: Record<TileKey, { title: string; icon: typeof FileText }> = {
  documents: { title: 'Dokumenty w archiwum', icon: FileText },
  events: { title: 'Ostatnie eventy', icon: Calendar },
  entities: { title: 'Encje w systemie', icon: Users },
  commitments: { title: 'Otwarte zobowiązania', icon: Target },
  budget: { title: 'Koszty i budżet LLM', icon: DollarSign },
  alerts: { title: 'Aktywne alerty', icon: AlertTriangle },
};

const SOURCE_BADGE: Record<string, { label: string; color: string }> = {
  email: { label: 'Email', color: 'bg-blue-500/15 text-blue-400' },
  teams: { label: 'Teams', color: 'bg-purple-500/15 text-purple-400' },
  whatsapp: { label: 'WhatsApp', color: 'bg-green-500/15 text-green-400' },
  plaud: { label: 'Plaud', color: 'bg-orange-500/15 text-orange-400' },
  pdf: { label: 'PDF', color: 'bg-gray-500/15 text-gray-400' },
  chatgpt: { label: 'ChatGPT', color: 'bg-teal-500/15 text-teal-400' },
  document: { label: 'Dokument', color: 'bg-gray-500/15 text-gray-400' },
};

const EVENT_TYPE_BADGE: Record<string, string> = {
  decision: 'bg-blue-500/15 text-blue-400',
  commitment: 'bg-amber-500/15 text-amber-400',
  conflict: 'bg-red-500/15 text-red-400',
  meeting: 'bg-purple-500/15 text-purple-400',
  task: 'bg-green-500/15 text-green-400',
  risk: 'bg-orange-500/15 text-orange-400',
  opportunity: 'bg-emerald-500/15 text-emerald-400',
  escalation: 'bg-red-500/15 text-red-400',
};

const SEVERITY_CONFIG: Record<string, { label: string; color: string; bg: string; icon: typeof AlertTriangle }> = {
  high: { label: 'Wysoki', color: 'text-red-400', bg: 'bg-red-500/10', icon: AlertCircle },
  medium: { label: 'Średni', color: 'text-amber-400', bg: 'bg-amber-500/10', icon: AlertTriangle },
  low: { label: 'Niski', color: 'text-blue-400', bg: 'bg-blue-500/10', icon: Info },
};

const ALERT_TYPE_LABEL: Record<string, string> = {
  decision_no_followup: 'Brak follow-up',
  conflict_spike: 'Konflikt',
  missing_communication: 'Brak komunikacji',
  health_clustering: 'Zdrowie',
  data_guardian: 'Data Guardian',
  ingestion_stale: 'Ingestion',
  compliance: 'Compliance',
  extraction_watchdog: 'Extraction',
};

type CommitmentFilter = 'all' | 'overdue' | 'this_week' | 'no_deadline';
type AlertFilter = 'all' | 'high' | 'data_guardian' | 'compliance';

function LoadingSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-12 animate-pulse rounded-lg bg-[var(--surface-hover)]" />
      ))}
    </div>
  );
}

// ─── DOCUMENTS VIEW ───

function DocumentsView({ status }: { status: StatusResponse | null }) {
  if (!status) return <LoadingSkeleton />;

  const sources = status.sources ?? [];

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-lg bg-[var(--surface)] border border-[var(--border)] p-3 text-center">
          <p className="text-xl font-bold text-[var(--text)]">{status.db.documents}</p>
          <p className="text-xs text-[var(--text-secondary)]">Dokumenty</p>
        </div>
        <div className="rounded-lg bg-[var(--surface)] border border-[var(--border)] p-3 text-center">
          <p className="text-xl font-bold text-[var(--text)]">{status.db.chunks}</p>
          <p className="text-xs text-[var(--text-secondary)]">Chunki</p>
        </div>
        <div className="rounded-lg bg-[var(--surface)] border border-[var(--border)] p-3 text-center">
          <p className="text-xl font-bold text-[var(--text)]">{status.embeddings.done}/{status.embeddings.total}</p>
          <p className="text-xs text-[var(--text-secondary)]">Embeddingi</p>
        </div>
      </div>

      {/* Sources table */}
      <div>
        <h3 className="mb-2 text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">
          Źródła
        </h3>
        <div className="overflow-hidden rounded-lg border border-[var(--border)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] bg-[var(--surface)]">
                <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--text-secondary)]">Typ źródła</th>
                <th className="px-4 py-2.5 text-right text-xs font-medium text-[var(--text-secondary)]">Dokumenty</th>
                <th className="px-4 py-2.5 text-right text-xs font-medium text-[var(--text-secondary)]">Ostatni import</th>
              </tr>
            </thead>
            <tbody>
              {sources.map((s) => {
                const badge = SOURCE_BADGE[s.source_type] ?? { label: s.source_type, color: 'bg-gray-500/15 text-gray-400' };
                return (
                  <tr key={s.source_type} className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--surface-hover)]">
                    <td className="px-4 py-2.5">
                      <span className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium', badge.color)}>
                        {badge.label}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-right text-[var(--text)]">{s.document_count}</td>
                    <td className="px-4 py-2.5 text-right text-xs text-[var(--text-secondary)]">
                      {s.newest_date ? new Date(s.newest_date).toLocaleDateString('pl-PL') : '—'}
                    </td>
                  </tr>
                );
              })}
              {sources.length === 0 && (
                <tr>
                  <td colSpan={3} className="px-4 py-8 text-center text-sm text-[var(--text-secondary)]">
                    Brak danych o źródłach
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pending embeddings */}
      {status.embeddings.pending > 0 && (
        <div className="flex items-center gap-2 rounded-lg bg-amber-500/10 border border-amber-500/20 px-4 py-2.5 text-sm text-amber-400">
          <Clock className="h-4 w-4" />
          {status.embeddings.pending} chunków oczekuje na embedding
        </div>
      )}
    </div>
  );
}

// ─── EVENTS VIEW ───

function EventsView({ events }: { events: TimelineEvent[] | null }) {
  if (!events) return <LoadingSkeleton />;

  if (events.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-[var(--text-secondary)]">
        <Calendar className="h-10 w-10 mb-3 opacity-40" />
        <p className="text-sm">Brak eventów</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {events.map((ev) => {
        const badgeColor = EVENT_TYPE_BADGE[ev.event_type] ?? 'bg-gray-500/15 text-gray-400';
        return (
          <ActionableItem
            key={ev.event_id}
            itemId={String(ev.event_id)}
            itemType="event"
            itemTitle={ev.summary}
            itemContent={ev}
          >
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3 hover:bg-[var(--surface-hover)] transition-colors">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={cn('inline-flex rounded-full px-2 py-0.5 text-[10px] font-medium', badgeColor)}>
                      {ev.event_type}
                    </span>
                    {ev.event_time && (
                      <span className="text-[10px] text-[var(--text-secondary)]">
                        {new Date(ev.event_time).toLocaleDateString('pl-PL')}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-[var(--text)] line-clamp-2">{ev.summary}</p>
                  {ev.entities.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {ev.entities.slice(0, 4).map((e) => (
                        <span key={e} className="rounded bg-[var(--surface-hover)] px-1.5 py-0.5 text-[10px] text-[var(--text-secondary)]">
                          {e}
                        </span>
                      ))}
                      {ev.entities.length > 4 && (
                        <span className="text-[10px] text-[var(--text-secondary)]">+{ev.entities.length - 4}</span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </ActionableItem>
        );
      })}
    </div>
  );
}

// ─── ENTITIES VIEW ───

function EntitiesView({ status }: { status: StatusResponse | null }) {
  if (!status) return <LoadingSkeleton />;

  // We use /status data which has entity count. No dedicated entity listing endpoint,
  // so we show the summary from status with a breakdown approach.
  const entityCount = status.db.entities;

  return (
    <div className="space-y-4">
      <div className="rounded-lg bg-[var(--surface)] border border-[var(--border)] p-4 text-center">
        <Users className="h-8 w-8 mx-auto mb-2 text-[var(--accent)] opacity-60" />
        <p className="text-3xl font-bold text-[var(--text)]">{entityCount}</p>
        <p className="text-sm text-[var(--text-secondary)]">Encji wyekstrahowanych z dokumentów</p>
      </div>

      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 space-y-3">
        <h3 className="text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">
          Typy encji
        </h3>
        <div className="grid grid-cols-2 gap-2">
          {[
            { type: 'person', label: 'Osoby', icon: Users, color: 'text-blue-400' },
            { type: 'organization', label: 'Organizacje', icon: FileText, color: 'text-purple-400' },
            { type: 'location', label: 'Lokalizacje', icon: Target, color: 'text-green-400' },
            { type: 'product', label: 'Produkty', icon: File, color: 'text-amber-400' },
          ].map((t) => (
            <div key={t.type} className="flex items-center gap-2 rounded-lg bg-[var(--bg)] border border-[var(--border)] px-3 py-2.5">
              <t.icon className={cn('h-4 w-4', t.color)} />
              <span className="text-sm text-[var(--text)]">{t.label}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-2 rounded-lg bg-[var(--accent)]/10 border border-[var(--accent)]/20 px-4 py-2.5 text-sm text-[var(--accent)]">
        <Info className="h-4 w-4" />
        Szczegóły encji dostępne w zakładce Ludzie
      </div>
    </div>
  );
}

// ─── COMMITMENTS VIEW ───

function CommitmentsView({ commitments }: { commitments: CommitmentItem[] | null }) {
  const [filter, setFilter] = useState<CommitmentFilter>('all');

  const now = new Date();
  const weekFromNow = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);

  const filtered = useMemo(() => {
    if (!commitments) return null;
    switch (filter) {
      case 'overdue':
        return commitments.filter((c) => c.deadline && new Date(c.deadline) < now);
      case 'this_week':
        return commitments.filter(
          (c) => c.deadline && new Date(c.deadline) >= now && new Date(c.deadline) <= weekFromNow,
        );
      case 'no_deadline':
        return commitments.filter((c) => !c.deadline);
      default:
        return commitments;
    }
  }, [commitments, filter]);

  if (!commitments) return <LoadingSkeleton />;

  const overdueCount = commitments.filter((c) => c.deadline && new Date(c.deadline) < now).length;

  function deadlineColor(deadline: string | null): string {
    if (!deadline) return 'text-[var(--text-secondary)]';
    const d = new Date(deadline);
    if (d < now) return 'text-red-400';
    if (d <= weekFromNow) return 'text-amber-400';
    return 'text-emerald-400';
  }

  const filterChips: { key: CommitmentFilter; label: string }[] = [
    { key: 'all', label: `Wszystkie (${commitments.length})` },
    { key: 'overdue', label: `Przeterminowane (${overdueCount})` },
    { key: 'this_week', label: 'Ten tydzień' },
    { key: 'no_deadline', label: 'Bez deadline' },
  ];

  return (
    <div className="space-y-4">
      {/* Filter chips */}
      <div className="flex flex-wrap gap-2">
        {filterChips.map((ch) => (
          <button
            key={ch.key}
            onClick={() => setFilter(ch.key)}
            className={cn(
              'rounded-full px-3 py-1 text-xs font-medium transition-all border',
              filter === ch.key
                ? 'bg-[var(--accent)] text-white border-[var(--accent)]'
                : 'bg-[var(--surface)] text-[var(--text-secondary)] border-[var(--border)] hover:border-[var(--accent)]/40',
            )}
          >
            {ch.label}
          </button>
        ))}
      </div>

      {/* List */}
      {(!filtered || filtered.length === 0) ? (
        <div className="flex flex-col items-center justify-center py-12 text-[var(--text-secondary)]">
          <Target className="h-10 w-10 mb-3 opacity-40" />
          <p className="text-sm">Brak zobowiązań w tej kategorii</p>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((c) => (
            <ActionableItem
              key={c.id}
              itemId={String(c.id)}
              itemType="commitment"
              itemTitle={c.commitment_text}
              itemContent={c}
            >
              <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3 hover:bg-[var(--surface-hover)] transition-colors">
                <p className="text-sm text-[var(--text)] line-clamp-2 mb-1.5">{c.commitment_text}</p>
                <div className="flex items-center gap-3 text-xs">
                  <span className="text-[var(--text-secondary)]">{c.person_name}</span>
                  {c.deadline && (
                    <span className={cn('flex items-center gap-1', deadlineColor(c.deadline))}>
                      <Clock className="h-3 w-3" />
                      {new Date(c.deadline).toLocaleDateString('pl-PL')}
                    </span>
                  )}
                  <span className={cn(
                    'rounded-full px-2 py-0.5 text-[10px] font-medium',
                    c.status === 'open' ? 'bg-amber-500/15 text-amber-400' : 'bg-emerald-500/15 text-emerald-400',
                  )}>
                    {c.status}
                  </span>
                </div>
              </div>
            </ActionableItem>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── BUDGET VIEW ───

function BudgetView({ budget }: { budget: BudgetResponse | null }) {
  if (!budget) return <LoadingSkeleton />;

  return (
    <div className="space-y-4">
      {/* Total today */}
      <div className="rounded-lg bg-[var(--surface)] border border-[var(--border)] p-4 text-center">
        <DollarSign className="h-8 w-8 mx-auto mb-2 text-[var(--accent)] opacity-60" />
        <p className="text-3xl font-bold text-[var(--text)]">${budget.daily_total_usd.toFixed(2)}</p>
        <p className="text-sm text-[var(--text-secondary)]">Koszt dziś</p>
      </div>

      {/* Budget breakdown */}
      <div>
        <h3 className="mb-2 text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">
          Budżety
        </h3>
        <div className="overflow-hidden rounded-lg border border-[var(--border)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] bg-[var(--surface)]">
                <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--text-secondary)]">Zakres</th>
                <th className="px-4 py-2.5 text-right text-xs font-medium text-[var(--text-secondary)]">Wydane</th>
                <th className="px-4 py-2.5 text-right text-xs font-medium text-[var(--text-secondary)]">Limit</th>
                <th className="px-4 py-2.5 text-right text-xs font-medium text-[var(--text-secondary)]">%</th>
                <th className="px-4 py-2.5 text-center text-xs font-medium text-[var(--text-secondary)]">Status</th>
              </tr>
            </thead>
            <tbody>
              {budget.budgets.map((b) => {
                const statusColor =
                  b.status === 'exceeded' ? 'text-red-400 bg-red-500/10' :
                  b.status === 'warning' ? 'text-amber-400 bg-amber-500/10' :
                  'text-emerald-400 bg-emerald-500/10';
                return (
                  <tr key={b.scope} className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--surface-hover)]">
                    <td className="px-4 py-2.5 text-[var(--text)]">{b.scope}</td>
                    <td className="px-4 py-2.5 text-right text-[var(--text)]">${b.spent_usd.toFixed(2)}</td>
                    <td className="px-4 py-2.5 text-right text-[var(--text-secondary)]">${b.limit_usd.toFixed(2)}</td>
                    <td className="px-4 py-2.5 text-right text-[var(--text)]">{b.pct.toFixed(0)}%</td>
                    <td className="px-4 py-2.5 text-center">
                      <span className={cn('inline-flex rounded-full px-2 py-0.5 text-[10px] font-medium', statusColor)}>
                        {b.status}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Today's alerts */}
      {budget.alerts_today.length > 0 && (
        <div>
          <h3 className="mb-2 text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">
            Alerty kosztowe dziś
          </h3>
          <div className="space-y-2">
            {budget.alerts_today.map((a, i) => (
              <div key={i} className="flex items-start gap-2 rounded-lg bg-amber-500/10 border border-amber-500/20 px-3 py-2 text-sm text-amber-400">
                <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
                <div>
                  <p className="font-medium">{a.scope}: {a.type}</p>
                  <p className="text-xs opacity-80">{a.message}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── ALERTS VIEW ───

function AlertsView({ alerts, onOpenAlert }: { alerts: AlertItemType[] | null; onOpenAlert?: (alert: AlertItemType) => void }) {
  const [filter, setFilter] = useState<AlertFilter>('all');

  const filtered = useMemo(() => {
    if (!alerts) return null;
    switch (filter) {
      case 'high':
        return alerts.filter((a) => a.severity === 'high');
      case 'data_guardian':
        return alerts.filter((a) => a.alert_type === 'data_guardian');
      case 'compliance':
        return alerts.filter((a) => a.alert_type === 'compliance');
      default:
        return alerts;
    }
  }, [alerts, filter]);

  if (!alerts) return <LoadingSkeleton />;

  const highCount = alerts.filter((a) => a.severity === 'high').length;

  const filterChips: { key: AlertFilter; label: string }[] = [
    { key: 'all', label: `Wszystkie (${alerts.length})` },
    { key: 'high', label: `Krytyczne (${highCount})` },
    { key: 'data_guardian', label: 'Data Guardian' },
    { key: 'compliance', label: 'Compliance' },
  ];

  return (
    <div className="space-y-4">
      {/* Filter chips */}
      <div className="flex flex-wrap gap-2">
        {filterChips.map((ch) => (
          <button
            key={ch.key}
            onClick={() => setFilter(ch.key)}
            className={cn(
              'rounded-full px-3 py-1 text-xs font-medium transition-all border',
              filter === ch.key
                ? 'bg-[var(--accent)] text-white border-[var(--accent)]'
                : 'bg-[var(--surface)] text-[var(--text-secondary)] border-[var(--border)] hover:border-[var(--accent)]/40',
            )}
          >
            {ch.label}
          </button>
        ))}
      </div>

      {(!filtered || filtered.length === 0) ? (
        <div className="flex flex-col items-center justify-center py-12 text-[var(--text-secondary)]">
          <AlertTriangle className="h-10 w-10 mb-3 opacity-40" />
          <p className="text-sm">Brak alertów w tej kategorii</p>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((alert) => {
            const severity = SEVERITY_CONFIG[alert.severity] ?? SEVERITY_CONFIG.low;
            const SeverityIcon = severity.icon;
            const typeLabel = ALERT_TYPE_LABEL[alert.alert_type] ?? alert.alert_type;

            return (
              <ActionableItem
                key={alert.alert_id}
                itemId={String(alert.alert_id)}
                itemType="alert"
                itemTitle={alert.title}
                itemContent={alert}
              >
                <div
                  className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3 hover:bg-[var(--surface-hover)] transition-colors cursor-pointer"
                  onClick={() => onOpenAlert?.(alert)}
                >
                  <div className="flex items-start gap-3">
                    <SeverityIcon className={cn('h-4 w-4 mt-0.5 shrink-0', severity.color)} />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={cn('inline-flex rounded-full px-2 py-0.5 text-[10px] font-medium', severity.bg, severity.color)}>
                          {severity.label}
                        </span>
                        <span className="rounded-full bg-[var(--surface-hover)] px-2 py-0.5 text-[10px] text-[var(--text-secondary)]">
                          {typeLabel}
                        </span>
                      </div>
                      <p className="text-sm text-[var(--text)] line-clamp-1 font-medium">{alert.title}</p>
                      {alert.description && (
                        <p className="text-xs text-[var(--text-secondary)] line-clamp-2 mt-0.5">{alert.description}</p>
                      )}
                      {alert.created_at && (
                        <p className="text-[10px] text-[var(--text-secondary)] mt-1">
                          {new Date(alert.created_at).toLocaleString('pl-PL')}
                        </p>
                      )}
                    </div>
                    <ChevronRight className="h-4 w-4 text-[var(--text-secondary)] shrink-0 mt-0.5" />
                  </div>
                </div>
              </ActionableItem>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── MAIN DRAWER ───

export function DashboardDetailDrawer({ tile, onClose, onOpenAlert }: DashboardDetailDrawerProps) {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [events, setEvents] = useState<TimelineEvent[] | null>(null);
  const [commitments, setCommitments] = useState<CommitmentItem[] | null>(null);
  const [budget, setBudget] = useState<BudgetResponse | null>(null);
  const [alerts, setAlerts] = useState<AlertItemType[] | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!tile) return;
    setLoading(true);

    async function load() {
      try {
        switch (tile) {
          case 'documents':
          case 'entities': {
            const s = await fetchStatus();
            setStatus(s);
            break;
          }
          case 'events': {
            const t = await fetchTimeline({ limit: 30 });
            setEvents(t.events);
            break;
          }
          case 'commitments': {
            const c = await fetchCommitments({ status: 'open', limit: 30 });
            setCommitments(c.commitments);
            break;
          }
          case 'budget': {
            const b = await fetchBudget();
            setBudget(b);
            break;
          }
          case 'alerts': {
            const a = await fetchAlerts({ active_only: true, limit: 50 });
            setAlerts(a.alerts);
            break;
          }
        }
      } catch (err) {
        console.error('Failed to load tile data', err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [tile]);

  // Close on Escape
  useEffect(() => {
    if (!tile) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [tile, onClose]);

  if (!tile) return null;

  const config = TILE_CONFIG[tile];
  const TileIcon = config.icon;

  function renderContent() {
    if (loading) return <LoadingSkeleton rows={6} />;

    switch (tile) {
      case 'documents':
        return <DocumentsView status={status} />;
      case 'events':
        return <EventsView events={events} />;
      case 'entities':
        return <EntitiesView status={status} />;
      case 'commitments':
        return <CommitmentsView commitments={commitments} />;
      case 'budget':
        return <BudgetView budget={budget} />;
      case 'alerts':
        return <AlertsView alerts={alerts} onOpenAlert={onOpenAlert} />;
      default:
        return null;
    }
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/50 transition-opacity"
        onClick={onClose}
      />

      {/* Drawer */}
      <div className="fixed right-0 top-0 z-50 flex h-full w-full max-w-[600px] flex-col border-l border-[var(--border)] bg-[var(--bg)] shadow-2xl animate-in slide-in-from-right duration-200">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--border)] px-6 py-4">
          <div className="flex items-center gap-3">
            <TileIcon className="h-5 w-5 text-[var(--accent)]" />
            <h2 className="text-base font-semibold text-[var(--text)]">{config.title}</h2>
          </div>
          <button
            onClick={onClose}
            className="rounded-md p-1.5 text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text)]"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {renderContent()}
        </div>
      </div>
    </>
  );
}
