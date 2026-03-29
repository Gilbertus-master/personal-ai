'use client';

import { Mic } from 'lucide-react';
import { VoiceHealthBadge } from './voice-health-badge';

export interface VoiceHeaderProps {
  health: { whisper: string; tts: string } | null;
  isHealthLoading: boolean;
}

export function VoiceHeader({ health, isHealthLoading }: VoiceHeaderProps) {
  return (
    <div className="flex items-center justify-between border-b border-[var(--border)] px-6 py-4">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--accent)]/10 text-[var(--accent)]">
          <Mic size={20} />
        </div>
        <div>
          <h1 className="text-lg font-semibold text-[var(--text)]">Interfejs głosowy</h1>
          <p className="text-xs text-[var(--text-muted)]">
            Rozmawiaj z Gilbertusem za pomocą głosu
          </p>
        </div>
      </div>

      <VoiceHealthBadge health={health} isLoading={isHealthLoading} />
    </div>
  );
}
