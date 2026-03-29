'use client';

import { cn } from '../../lib/utils';

export interface VoiceHealthBadgeProps {
  health: { whisper: string; tts: string } | null;
  isLoading: boolean;
}

type HealthStatus = 'online' | 'partial' | 'offline';

function getStatus(health: { whisper: string; tts: string } | null): HealthStatus {
  if (!health) return 'offline';
  const whisperOk = health.whisper === 'ok';
  const ttsOk = health.tts.includes('ok');
  if (whisperOk && ttsOk) return 'online';
  if (whisperOk || ttsOk) return 'partial';
  return 'offline';
}

const STATUS_CONFIG: Record<HealthStatus, { dot: string; label: string }> = {
  online: { dot: 'bg-green-500', label: 'Online' },
  partial: { dot: 'bg-yellow-500', label: 'Częściowo' },
  offline: { dot: 'bg-red-500', label: 'Offline' },
};

export function VoiceHealthBadge({ health, isLoading }: VoiceHealthBadgeProps) {
  if (isLoading) {
    return (
      <div className="flex items-center gap-2 rounded-full border border-[var(--border)] px-3 py-1">
        <div className="h-2.5 w-2.5 animate-spin rounded-full border-2 border-[var(--text-muted)] border-t-transparent" />
        <span className="text-xs text-[var(--text-muted)]">Sprawdzanie...</span>
      </div>
    );
  }

  const status = getStatus(health);
  const config = STATUS_CONFIG[status];

  return (
    <div
      className="group relative flex items-center gap-2 rounded-full border border-[var(--border)] px-3 py-1"
      title={health ? `Whisper: ${health.whisper}, TTS: ${health.tts}` : 'Brak danych'}
    >
      <span className={cn('h-2.5 w-2.5 rounded-full', config.dot)} />
      <span className="text-xs text-[var(--text-secondary)]">{config.label}</span>

      {/* Tooltip on hover */}
      {health && (
        <div className="pointer-events-none absolute right-0 top-full z-30 mt-2 hidden w-48 rounded-lg border border-[var(--border)] bg-[var(--bg)] p-3 shadow-lg group-hover:block">
          <div className="space-y-1.5 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-[var(--text-muted)]">Whisper</span>
              <span className={health.whisper === 'ok' ? 'text-green-500' : 'text-red-500'}>
                {health.whisper}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[var(--text-muted)]">TTS</span>
              <span className={health.tts.includes('ok') ? 'text-green-500' : 'text-red-500'}>
                {health.tts}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
