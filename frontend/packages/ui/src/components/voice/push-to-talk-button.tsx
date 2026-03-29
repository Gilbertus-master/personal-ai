'use client';

import { Mic, Loader2 } from 'lucide-react';
import { cn } from '../../lib/utils';

export interface PushToTalkButtonProps {
  isRecording: boolean;
  isProcessing: boolean;
  disabled?: boolean;
  size?: 'sm' | 'md' | 'lg';
  onRecordStart: () => void;
  onRecordStop: () => void;
}

const sizeMap = {
  sm: 48,
  md: 64,
  lg: 96,
} as const;

const iconSizeMap = {
  sm: 20,
  md: 24,
  lg: 36,
} as const;

export function PushToTalkButton({
  isRecording,
  isProcessing,
  disabled = false,
  size = 'md',
  onRecordStart,
  onRecordStop,
}: PushToTalkButtonProps) {
  const px = sizeMap[size];
  const iconPx = iconSizeMap[size];

  return (
    <div className="relative inline-flex flex-col items-center gap-2">
      {/* Pulse ring animation when recording */}
      {isRecording && (
        <span
          className="absolute rounded-full bg-red-500/30 animate-[pulse-ring_1.5s_ease-out_infinite]"
          style={{ width: px + 24, height: px + 24 }}
        />
      )}

      <button
        type="button"
        disabled={disabled || isProcessing}
        onMouseDown={onRecordStart}
        onMouseUp={onRecordStop}
        onMouseLeave={onRecordStop}
        onTouchStart={onRecordStart}
        onTouchEnd={onRecordStop}
        className={cn(
          'relative z-10 flex items-center justify-center rounded-full border-2 transition-all select-none',
          'focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]',
          disabled && 'opacity-50 pointer-events-none',
          isRecording
            ? 'bg-red-500/20 border-red-500'
            : isProcessing
              ? 'bg-[var(--accent)]/20 border-[var(--accent)]'
              : 'bg-[var(--surface)] border-[var(--border)] hover:border-[var(--accent)]',
        )}
        style={{ width: px, height: px }}
        aria-label={isRecording ? 'Nagrywam — puść aby zatrzymać' : 'Przytrzymaj aby nagrywać'}
      >
        {isProcessing ? (
          <Loader2 size={iconPx} className="animate-spin text-[var(--accent)]" />
        ) : (
          <Mic
            size={iconPx}
            className={cn(
              'transition-colors',
              isRecording ? 'text-red-500' : 'text-[var(--text-secondary)]',
            )}
          />
        )}
      </button>

      {(isRecording || isProcessing) && (
        <span
          className={cn(
            'text-xs font-medium',
            isRecording ? 'text-red-500' : 'text-[var(--accent)]',
          )}
        >
          {isRecording ? 'Nagrywam...' : 'Przetwarzam...'}
        </span>
      )}

      <style jsx global>{`
        @keyframes pulse-ring {
          0% {
            transform: scale(0.8);
            opacity: 0.8;
          }
          100% {
            transform: scale(1.4);
            opacity: 0;
          }
        }
      `}</style>
    </div>
  );
}
