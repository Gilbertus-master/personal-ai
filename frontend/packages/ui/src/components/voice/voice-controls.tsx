'use client';

import { Square } from 'lucide-react';
import { cn } from '../../lib/utils';
import { PushToTalkButton } from './push-to-talk-button';
import { VoiceWaveform } from './voice-waveform';

export interface VoiceControlsProps {
  isRecording: boolean;
  isProcessing: boolean;
  isPlaying: boolean;
  mode: 'http' | 'websocket';
  wsConnected: boolean;
  analyserNode: AnalyserNode | null;
  onRecordStart: () => void;
  onRecordStop: () => void;
  onModeChange: (mode: 'http' | 'websocket') => void;
  onStopPlayback: () => void;
}

export function VoiceControls({
  isRecording,
  isProcessing,
  isPlaying,
  mode,
  wsConnected,
  analyserNode,
  onRecordStart,
  onRecordStop,
  onModeChange,
  onStopPlayback,
}: VoiceControlsProps) {
  return (
    <div className="sticky bottom-0 z-20 border-t border-[var(--border)] bg-[var(--bg)] px-4 py-4">
      <div className="mx-auto flex max-w-3xl items-center justify-between gap-4">
        {/* Left: Mode toggle */}
        <div className="flex items-center gap-2">
          <div className="flex rounded-lg border border-[var(--border)] overflow-hidden">
            <button
              type="button"
              onClick={() => onModeChange('http')}
              className={cn(
                'px-3 py-1.5 text-xs font-medium transition-colors',
                mode === 'http'
                  ? 'bg-[var(--accent)] text-white'
                  : 'bg-[var(--surface)] text-[var(--text-secondary)] hover:text-[var(--text)]',
              )}
            >
              Standardowy
            </button>
            <button
              type="button"
              onClick={() => onModeChange('websocket')}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium transition-colors',
                mode === 'websocket'
                  ? 'bg-[var(--accent)] text-white'
                  : 'bg-[var(--surface)] text-[var(--text-secondary)] hover:text-[var(--text)]',
              )}
            >
              Real-time
              {mode === 'websocket' && (
                <span
                  className={cn(
                    'inline-block h-2 w-2 rounded-full',
                    wsConnected ? 'bg-green-500' : 'bg-red-500',
                  )}
                />
              )}
            </button>
          </div>
        </div>

        {/* Center: Waveform + PTT + Waveform */}
        <div className="flex items-center gap-3">
          <VoiceWaveform
            analyserNode={analyserNode}
            isActive={isRecording}
            width={120}
            height={48}
          />
          <PushToTalkButton
            size="lg"
            isRecording={isRecording}
            isProcessing={isProcessing}
            onRecordStart={onRecordStart}
            onRecordStop={onRecordStop}
          />
          <VoiceWaveform
            analyserNode={analyserNode}
            isActive={isRecording}
            width={120}
            height={48}
          />
        </div>

        {/* Right: Stop playback */}
        <div className="flex items-center" style={{ minWidth: 40 }}>
          {isPlaying && (
            <button
              type="button"
              onClick={onStopPlayback}
              className="flex h-10 w-10 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--surface)] text-[var(--text-secondary)] hover:text-[var(--text)] hover:border-[var(--accent)] transition-colors"
              aria-label="Zatrzymaj odtwarzanie"
            >
              <Square size={18} />
            </button>
          )}
        </div>
      </div>

      {/* Keyboard hint */}
      <p className="mt-2 text-center text-xs text-[var(--text-muted)]">
        Przytrzymaj spację
      </p>
    </div>
  );
}
