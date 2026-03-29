'use client';

import { useState } from 'react';
import { CheckCircle, Loader2 } from 'lucide-react';
import type { ComplianceTraining, TrainingRecord, TrainingRecordStatus } from '@gilbertus/api-client';
import { cn } from '../../lib/utils';
import { ComplianceBadge } from './compliance-badge';

export interface TrainingStatusGridProps {
  training: ComplianceTraining | undefined;
  records: TrainingRecord[];
  isLoading?: boolean;
  canComplete?: boolean;
  onComplete?: (personId: number, score?: number) => void;
  isCompleting?: boolean;
}

const RECORD_STATUS_COLORS: Record<TrainingRecordStatus, string> = {
  assigned: 'bg-gray-500/10 text-gray-400',
  notified: 'bg-blue-500/15 text-blue-400',
  started: 'bg-yellow-500/15 text-yellow-400',
  completed: 'bg-green-500/15 text-green-400',
  overdue: 'bg-red-500/15 text-red-400',
  exempted: 'bg-gray-500/10 text-gray-400',
};

const RECORD_STATUS_LABELS: Record<TrainingRecordStatus, string> = {
  assigned: 'Przypisane',
  notified: 'Powiadomiony',
  started: 'Rozpoczęte',
  completed: 'Ukończone',
  overdue: 'Zaległe',
  exempted: 'Zwolniony',
};

const ROW_TINT: Record<string, string> = {
  completed: 'bg-green-500/5',
  overdue: 'bg-red-500/5',
  started: 'bg-yellow-500/5',
};

const TRAINING_TYPE_COLORS: Record<string, string> = {
  mandatory: 'bg-red-500/15 text-red-400',
  awareness: 'bg-blue-500/15 text-blue-400',
  certification: 'bg-purple-500/15 text-purple-400',
  refresher: 'bg-yellow-500/15 text-yellow-400',
  onboarding: 'bg-green-500/15 text-green-400',
};

const TRAINING_TYPE_LABELS: Record<string, string> = {
  mandatory: 'Obowiązkowe',
  awareness: 'Świadomość',
  certification: 'Certyfikacja',
  refresher: 'Odświeżenie',
  onboarding: 'Onboarding',
};

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '\u2014';
  try {
    return new Intl.DateTimeFormat('pl-PL', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    }).format(new Date(dateStr));
  } catch {
    return '\u2014';
  }
}

function SkeletonGrid() {
  return (
    <div className="space-y-4">
      <div className="h-24 rounded-lg bg-[var(--surface)] animate-pulse" />
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="h-12 rounded bg-[var(--surface)] animate-pulse" />
      ))}
    </div>
  );
}

function CompleteButton({
  personId,
  onComplete,
  isCompleting,
}: {
  personId: number;
  onComplete: (personId: number, score?: number) => void;
  isCompleting: boolean;
}) {
  const [showConfirm, setShowConfirm] = useState(false);
  const [score, setScore] = useState('');

  if (!showConfirm) {
    return (
      <button
        onClick={() => setShowConfirm(true)}
        className="flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-colors"
        style={{ backgroundColor: 'var(--surface)', color: 'var(--text-secondary)' }}
      >
        <CheckCircle size={12} />
        Ukończ
      </button>
    );
  }

  return (
    <div className="flex items-center gap-1.5">
      <input
        type="number"
        value={score}
        onChange={(e) => setScore(e.target.value)}
        placeholder="Wynik"
        min={0}
        max={100}
        className="w-16 rounded-md border px-2 py-1 text-xs"
        style={{
          backgroundColor: 'var(--surface)',
          borderColor: 'var(--border)',
          color: 'var(--text)',
        }}
      />
      <button
        onClick={() => {
          onComplete(personId, score ? Number(score) : undefined);
          setShowConfirm(false);
        }}
        disabled={isCompleting}
        className="flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-colors disabled:opacity-50"
        style={{ backgroundColor: 'var(--accent)', color: '#fff' }}
      >
        {isCompleting ? <Loader2 size={12} className="animate-spin" /> : <CheckCircle size={12} />}
        OK
      </button>
      <button
        onClick={() => setShowConfirm(false)}
        className="rounded-md px-2 py-1 text-xs"
        style={{ color: 'var(--text-secondary)' }}
      >
        Anuluj
      </button>
    </div>
  );
}

export function TrainingStatusGrid({
  training,
  records,
  isLoading,
  canComplete = false,
  onComplete,
  isCompleting = false,
}: TrainingStatusGridProps) {
  if (isLoading) return <SkeletonGrid />;
  if (!training) return null;

  const deadlineStr = formatDate(training.deadline);
  const isOverdue = training.deadline ? new Date(training.deadline) < new Date() : false;

  return (
    <div className="space-y-6">
      {/* Training header */}
      <div
        className="rounded-lg p-5"
        style={{ backgroundColor: 'var(--surface)', border: '1px solid var(--border)' }}
      >
        <h2 className="text-xl font-semibold mb-3" style={{ color: 'var(--text)' }}>
          {training.title}
        </h2>
        <div className="flex flex-wrap items-center gap-3">
          <ComplianceBadge type="area" value={training.area_code} size="md" />
          <span
            className={cn(
              'inline-flex items-center rounded-full px-2.5 py-1 text-sm font-medium',
              TRAINING_TYPE_COLORS[training.training_type] ?? 'bg-gray-500/10 text-gray-400',
            )}
          >
            {TRAINING_TYPE_LABELS[training.training_type] ?? training.training_type}
          </span>
          <ComplianceBadge type="training" value={training.status} size="md" />
          {training.deadline && (
            <span
              className={cn(
                'text-sm',
                isOverdue ? 'text-red-400 font-medium' : 'text-[var(--text-secondary)]',
              )}
            >
              Termin: {deadlineStr}
            </span>
          )}
        </div>
        {training.content_summary && (
          <p className="mt-3 text-sm" style={{ color: 'var(--text-secondary)' }}>
            {training.content_summary}
          </p>
        )}
      </div>

      {/* Person grid */}
      <div className="border border-[var(--border)] rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] bg-[var(--surface)]">
              <th className="px-4 py-3 text-left text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider">
                Osoba
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider">
                Status
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider">
                Powiadomiony
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider">
                Ukończony
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider">
                Wynik
              </th>
              {canComplete && (
                <th className="px-4 py-3 text-left text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider">
                  Akcja
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {records.length === 0 ? (
              <tr>
                <td
                  colSpan={canComplete ? 6 : 5}
                  className="px-4 py-8 text-center text-[var(--text-secondary)]"
                >
                  Brak przypisanych osób
                </td>
              </tr>
            ) : (
              records.map((record) => (
                <tr
                  key={record.person_id}
                  className={cn(
                    'border-b border-[var(--border)] transition-colors',
                    ROW_TINT[record.status] ?? '',
                  )}
                >
                  <td className="px-4 py-3 font-medium text-[var(--text)]">
                    {record.person_name}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={cn(
                        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
                        RECORD_STATUS_COLORS[record.status] ?? 'bg-gray-500/10 text-gray-400',
                      )}
                    >
                      {RECORD_STATUS_LABELS[record.status] ?? record.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-[var(--text-secondary)]">
                    {formatDate(record.notified_at)}
                  </td>
                  <td className="px-4 py-3 text-[var(--text-secondary)]">
                    {formatDate(record.completed_at)}
                  </td>
                  <td className="px-4 py-3 text-[var(--text-secondary)]">
                    {record.score != null ? record.score : '\u2014'}
                  </td>
                  {canComplete && (
                    <td className="px-4 py-3">
                      {record.status !== 'completed' && record.status !== 'exempted' && onComplete && (
                        <CompleteButton
                          personId={record.person_id}
                          onComplete={onComplete}
                          isCompleting={isCompleting}
                        />
                      )}
                    </td>
                  )}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
