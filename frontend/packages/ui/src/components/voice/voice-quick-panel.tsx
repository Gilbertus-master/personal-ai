'use client';

import { useEffect, useRef, useCallback } from 'react';
import { X, Maximize2, Volume2, Type } from 'lucide-react';
import { cn } from '../../lib/utils';
import { PushToTalkButton } from './push-to-talk-button';

export interface VoiceQuickPanelProps {
  isOpen: boolean;
  onClose: () => void;
  isRecording: boolean;
  isProcessing: boolean;
  isPlaying: boolean;
  transcript: string | null;
  response: string | null;
  onRecordStart: () => void;
  onRecordStop: () => void;
  onStopPlayback: () => void;
  onOpenFullPage: () => void;
  responseMode?: 'voice' | 'text';
  onResponseModeChange?: (m: 'voice' | 'text') => void;
}

export function VoiceQuickPanel({
  isOpen,
  onClose,
  isRecording,
  isProcessing,
  isPlaying,
  transcript,
  response,
  onRecordStart,
  onRecordStop,
  onStopPlayback,
  onOpenFullPage,
  responseMode = 'voice',
  onResponseModeChange,
}: VoiceQuickPanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  // Close on Escape
  useEffect(() => {
    if (!isOpen) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [isOpen, onClose]);

  // Close on click outside
  const handleBackdropClick = useCallback(
    (e: React.MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        onClose();
      }
    },
    [onClose],
  );

  if (!isOpen) return null;

  return (
    // Invisible backdrop for click-outside detection
    <div className="fixed inset-0 z-50" onClick={handleBackdropClick}>
      <div
        ref={panelRef}
        className={cn(
          'fixed bottom-20 right-6 z-50 w-80 max-h-96 flex flex-col',
          'rounded-xl border border-[var(--border)] bg-[var(--bg)] shadow-xl',
          'animate-in slide-in-from-bottom-4 fade-in duration-200',
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
          <h3 className="text-sm font-semibold text-[var(--text)]">
            Asystent głosowy
          </h3>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={onOpenFullPage}
              className="rounded-md p-1 text-[var(--text-secondary)] hover:bg-[var(--surface)] hover:text-[var(--text)] transition-colors"
              aria-label="Otwórz pełny widok"
              title="Otwórz pełny widok"
            >
              <Maximize2 size={16} />
            </button>
            <button
              type="button"
              onClick={onClose}
              className="rounded-md p-1 text-[var(--text-secondary)] hover:bg-[var(--surface)] hover:text-[var(--text)] transition-colors"
              aria-label="Zamknij"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Body — transcript & response */}
        <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
          {!transcript && !response && (
            <p className="text-sm text-[var(--text-secondary)] text-center py-4">
Kliknij mikrofon i zadaj pytanie
            </p>
          )}

          {transcript && (
            <div className="space-y-1">
              <span className="text-xs font-medium text-[var(--text-secondary)]">Ty</span>
              <p className="text-sm text-[var(--text)] bg-[var(--surface)] rounded-lg px-3 py-2">
                {transcript}
              </p>
            </div>
          )}

          {response && (
            <div className="space-y-1">
              <span className="text-xs font-medium text-[var(--accent)]">Gilbertus</span>
              <p className="text-sm text-[var(--text)] bg-[var(--accent)]/10 rounded-lg px-3 py-2">
                {response}
              </p>
            </div>
          )}

          {isPlaying && (
            <button
              type="button"
              onClick={onStopPlayback}
              className="text-xs text-[var(--accent)] hover:underline"
            >
              Zatrzymaj odtwarzanie
            </button>
          )}
        </div>

        {/* Footer — PTT button */}
        <div className="flex justify-center border-t border-[var(--border)] px-4 py-3">
          <PushToTalkButton
            size="md"
            isRecording={isRecording}
            isProcessing={isProcessing}
            onRecordStart={onRecordStart}
            onRecordStop={onRecordStop}
          />
        </div>
      </div>
    </div>
  );
}
