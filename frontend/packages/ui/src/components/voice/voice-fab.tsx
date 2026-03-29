'use client';

import { Mic, Loader2 } from 'lucide-react';
import { usePathname } from 'next/navigation';
import { cn } from '../../lib/utils';

export interface VoiceFabProps {
  roleLevel: number;
  isRecording: boolean;
  isProcessing: boolean;
  onClick: () => void;
}

export function VoiceFab({
  roleLevel,
  isRecording,
  isProcessing,
  onClick,
}: VoiceFabProps) {
  const pathname = usePathname();

  // Hide for non-board roles or on the full voice page
  if (roleLevel < 50 || pathname === '/voice') return null;

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full shadow-lg transition-all hover:scale-105',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2',
        isRecording
          ? 'bg-red-500'
          : 'bg-[var(--accent)]',
      )}
      aria-label="Asystent głosowy"
    >
      {/* Pulsing ring when recording */}
      {isRecording && (
        <span className="absolute inset-0 rounded-full bg-red-500/40 animate-ping" />
      )}

      {isProcessing ? (
        <Loader2 size={24} className="animate-spin text-white" />
      ) : (
        <Mic size={24} className="text-white" />
      )}
    </button>
  );
}
