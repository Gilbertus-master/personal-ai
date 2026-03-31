'use client';

import { useState, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { RbacGate, AlertDetailDrawer, showToast } from '@gilbertus/ui';
import { resolveAlert, deleteAlertSuppression, completeAlertFixTask } from '@gilbertus/api-client';
import type { AlertItem } from '@gilbertus/api-client';
import { useAlerts, useAlertSuppressions, useAlertFixTasks } from '@/lib/hooks/use-dashboard';
import { useDashboardStore } from '@/lib/stores/dashboard-store';
import {
  AlertTriangle,
  Wrench,
  Ban,
  Trash2,
  CheckCircle2,
  Clock,
  XCircle,
  Filter,
} from 'lucide-react';
import { cn } from '@gilbertus/ui';

type Tab = 'alerts' | 'fix-tasks' | 'suppressions';

const SEVERITY_DOT: Record<string, string> = {
  high: 'bg-red-500',
  medium: 'bg-amber-500',
  low: 'bg-blue-500',
};

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: typeof Clock }> = {
  pending: { label: 'Oczekujace', color: 'text-amber-400', icon: Clock },
  in_progress: { label: 'W trakcie', color: 'text-blue-400', icon: Clock },
  done: { label: 'Wykonane', color: 'text-green-400', icon: CheckCircle2 },
  failed: { label: 'Nieudane', color: 'text-red-400', icon: XCircle },
};

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-';
  return new Date(dateStr).toLocaleString('pl-PL', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function AdminAlertsPage() {
  const [tab, setTab] = useState<Tab>('alerts');
  const [severityFilter, setSeverityFilter] = useState<string>('');
  const [typeFilter, setTypeFilter] = useState<string>('');
  const [drawerAlert, setDrawerAlert] = useState<AlertItem | null>(null);
  const [isResolving, setIsResolving] = useState(false);

  const queryClient = useQueryClient();
  const { dismissAlert } = useDashboardStore();

  const alertsQuery = useAlerts({ activeOnly: true, severity: severityFilter || undefined });
  const suppressionsQuery = useAlertSuppressions();
  const fixTasksQuery = useAlertFixTasks();

  const alerts = alertsQuery.data?.alerts ?? [];
  const suppressions = suppressionsQuery.data?.suppressions ?? [];
  const fixTasks = fixTasksQuery.data?.tasks ?? [];

  const filteredAlerts = typeFilter
    ? alerts.filter((a) => a.alert_type === typeFilter)
    : alerts;

  const pendingTasks = fixTasks.filter((t) => t.status === 'pending' || t.status === 'in_progress');

  // Unique alert types for filter
  const alertTypes = [...new Set(alerts.map((a) => a.alert_type))];

  const handleResolve = useCallback(
    async (alertId: number, action: 'fix' | 'suppress', comment: string, fixInstruction?: string) => {
      setIsResolving(true);
      try {
        await resolveAlert(alertId, { action, comment, fix_instruction: fixInstruction });
        showToast(action === 'fix' ? 'Zadanie naprawy utworzone' : 'Alert suppresowany', 'success');
        setDrawerAlert(null);
        dismissAlert(alertId);
        queryClient.invalidateQueries({ queryKey: ['alerts'] });
      } catch {
        showToast('Blad podczas rozwiazywania alertu', 'error');
      } finally {
        setIsResolving(false);
      }
    },
    [dismissAlert, queryClient],
  );

  const handleDeleteSuppression = useCallback(
    async (id: number) => {
      try {
        await deleteAlertSuppression(id);
        showToast('Suppresja usunieta', 'success');
        queryClient.invalidateQueries({ queryKey: ['alerts'] });
      } catch {
        showToast('Blad usuwania suppresji', 'error');
      }
    },
    [queryClient],
  );

  const handleCompleteTask = useCallback(
    async (taskId: number) => {
      try {
        await completeAlertFixTask(taskId, 'Oznaczono jako wykonane przez UI');
        showToast('Task oznaczony jako wykonany', 'success');
        queryClient.invalidateQueries({ queryKey: ['alerts', 'fix-tasks'] });
      } catch {
        showToast('Blad zakonczenia tasku', 'error');
      }
    },
    [queryClient],
  );

  return (
    <RbacGate roles={['owner', 'gilbertus_admin', 'ceo', 'operator']} fallback={<p className="text-[var(--text-secondary)]">Brak dostepu</p>}>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-xl font-semibold text-[var(--text)]">Zarzadzanie alertami</h1>
          <div className="mt-2 flex gap-4 text-sm">
            <span className="text-[var(--text-secondary)]">
              <span className="font-medium text-red-400">{alerts.length}</span> aktywnych
            </span>
            <span className="text-[var(--text-secondary)]">
              <span className="font-medium text-amber-400">{suppressions.length}</span> suppresji
            </span>
            <span className="text-[var(--text-secondary)]">
              <span className="font-medium text-blue-400">{pendingTasks.length}</span> taskow pending
            </span>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 border-b border-[var(--border)]">
          {([
            { key: 'alerts' as Tab, label: 'Alerty', icon: AlertTriangle, count: alerts.length },
            { key: 'fix-tasks' as Tab, label: 'Fix Tasks', icon: Wrench, count: fixTasks.length },
            { key: 'suppressions' as Tab, label: 'Suppresje', icon: Ban, count: suppressions.length },
          ]).map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={cn(
                'flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors',
                tab === t.key
                  ? 'border-[var(--accent)] text-[var(--accent)]'
                  : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text)]',
              )}
            >
              <t.icon className="h-4 w-4" />
              {t.label}
              {t.count > 0 && (
                <span className="rounded-full bg-[var(--surface-hover)] px-1.5 py-0.5 text-[10px]">
                  {t.count}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Alerts tab */}
        {tab === 'alerts' && (
          <div className="space-y-3">
            {/* Filters */}
            <div className="flex gap-3">
              <div className="flex items-center gap-2">
                <Filter className="h-4 w-4 text-[var(--text-secondary)]" />
                <select
                  value={severityFilter}
                  onChange={(e) => setSeverityFilter(e.target.value)}
                  className="rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-sm text-[var(--text)]"
                >
                  <option value="">Wszystkie severity</option>
                  <option value="high">Wysoki</option>
                  <option value="medium">Sredni</option>
                  <option value="low">Niski</option>
                </select>
              </div>
              <select
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
                className="rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-sm text-[var(--text)]"
              >
                <option value="">Wszystkie typy</option>
                {alertTypes.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>

            {/* Alert list */}
            {alertsQuery.isLoading ? (
              <div className="py-8 text-center text-sm text-[var(--text-secondary)]">Ladowanie...</div>
            ) : filteredAlerts.length === 0 ? (
              <div className="flex flex-col items-center gap-2 py-12 text-center">
                <CheckCircle2 className="h-10 w-10 text-green-400 opacity-60" />
                <p className="text-sm text-[var(--text-secondary)]">Brak aktywnych alertow</p>
              </div>
            ) : (
              <div className="rounded-lg border border-[var(--border)] divide-y divide-[var(--border)]">
                {filteredAlerts.map((alert) => {
                  const dot = SEVERITY_DOT[alert.severity] ?? 'bg-gray-400';
                  return (
                    <div
                      key={alert.alert_id}
                      onClick={() => setDrawerAlert(alert)}
                      className="flex items-center gap-4 px-4 py-3 cursor-pointer transition-colors hover:bg-[var(--surface-hover)]"
                    >
                      <span className={cn('h-2.5 w-2.5 shrink-0 rounded-full', dot)} />
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-[var(--text)] truncate">
                          {alert.title}
                        </p>
                        <p className="text-xs text-[var(--text-secondary)] truncate">
                          {alert.description}
                        </p>
                      </div>
                      <span className="shrink-0 rounded-full bg-[var(--surface-hover)] px-2 py-0.5 text-[10px] text-[var(--text-secondary)]">
                        {alert.alert_type}
                      </span>
                      <span className="shrink-0 text-xs text-[var(--text-secondary)]">
                        {formatDate(alert.created_at)}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Fix Tasks tab */}
        {tab === 'fix-tasks' && (
          <div className="space-y-3">
            {fixTasksQuery.isLoading ? (
              <div className="py-8 text-center text-sm text-[var(--text-secondary)]">Ladowanie...</div>
            ) : fixTasks.length === 0 ? (
              <div className="flex flex-col items-center gap-2 py-12 text-center">
                <Wrench className="h-10 w-10 text-[var(--text-secondary)] opacity-40" />
                <p className="text-sm text-[var(--text-secondary)]">Brak zadan naprawy</p>
              </div>
            ) : (
              <div className="rounded-lg border border-[var(--border)] divide-y divide-[var(--border)]">
                {fixTasks.map((task) => {
                  const statusCfg = STATUS_CONFIG[task.status] ?? STATUS_CONFIG.pending;
                  const StatusIcon = statusCfg.icon;
                  return (
                    <div key={task.id} className="px-4 py-3 space-y-1">
                      <div className="flex items-center gap-3">
                        <StatusIcon className={cn('h-4 w-4 shrink-0', statusCfg.color)} />
                        <p className="text-sm font-medium text-[var(--text)] flex-1 truncate">
                          {task.title}
                        </p>
                        <span className={cn('text-xs font-medium', statusCfg.color)}>
                          {statusCfg.label}
                        </span>
                        {(task.status === 'pending' || task.status === 'in_progress') && (
                          <button
                            onClick={() => handleCompleteTask(task.id)}
                            className="rounded-md px-2 py-1 text-xs font-medium text-green-400 hover:bg-green-500/10 transition-colors"
                          >
                            Oznacz jako done
                          </button>
                        )}
                      </div>
                      <p className="text-xs text-[var(--text-secondary)] pl-7 line-clamp-2">
                        {task.instruction}
                      </p>
                      {task.comment && (
                        <p className="text-xs text-[var(--text-secondary)] pl-7 italic">
                          Komentarz: {task.comment}
                        </p>
                      )}
                      {task.result && (
                        <p className="text-xs text-green-400 pl-7">
                          Wynik: {task.result}
                        </p>
                      )}
                      <p className="text-[10px] text-[var(--text-secondary)] pl-7">
                        {formatDate(task.created_at)}
                      </p>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Suppressions tab */}
        {tab === 'suppressions' && (
          <div className="space-y-3">
            {suppressionsQuery.isLoading ? (
              <div className="py-8 text-center text-sm text-[var(--text-secondary)]">Ladowanie...</div>
            ) : suppressions.length === 0 ? (
              <div className="flex flex-col items-center gap-2 py-12 text-center">
                <Ban className="h-10 w-10 text-[var(--text-secondary)] opacity-40" />
                <p className="text-sm text-[var(--text-secondary)]">Brak regul suppresji</p>
              </div>
            ) : (
              <div className="rounded-lg border border-[var(--border)] divide-y divide-[var(--border)]">
                {suppressions.map((sup) => (
                  <div key={sup.id} className="flex items-center gap-4 px-4 py-3">
                    <Ban className="h-4 w-4 shrink-0 text-red-400" />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-[var(--text)]">
                        {sup.alert_type}
                        {sup.source_type && (
                          <span className="ml-2 text-xs text-[var(--text-secondary)]">
                            (source: {sup.source_type})
                          </span>
                        )}
                      </p>
                      {sup.reason && (
                        <p className="text-xs text-[var(--text-secondary)]">{sup.reason}</p>
                      )}
                    </div>
                    <span className="shrink-0 text-xs text-[var(--text-secondary)]">
                      {formatDate(sup.created_at)}
                    </span>
                    <button
                      onClick={() => handleDeleteSuppression(sup.id)}
                      className="shrink-0 rounded-md p-1.5 text-red-400 hover:bg-red-500/10 transition-colors"
                      title="Usun suppresje"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Alert Detail Drawer */}
      <AlertDetailDrawer
        alert={drawerAlert}
        onClose={() => setDrawerAlert(null)}
        onResolve={handleResolve}
        isResolving={isResolving}
      />
    </RbacGate>
  );
}
