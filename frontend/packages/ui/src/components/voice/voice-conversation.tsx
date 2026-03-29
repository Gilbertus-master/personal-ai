'use client';

import { useEffect, useRef } from 'react';
import { Mic } from 'lucide-react';
import { VoiceMessage } from './voice-message';

export interface ConversationMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  audioUrl?: string;
  timestamp: string;
}

export interface VoiceConversationProps {
  messages: ConversationMessage[];
  isProcessing: boolean;
  onPlayAudio?: (url: string) => void;
}

export function VoiceConversation({ messages, isProcessing, onPlayAudio }: VoiceConversationProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length, isProcessing]);

  if (messages.length === 0 && !isProcessing) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4 text-[var(--text-muted)]">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-[var(--surface)]">
          <Mic size={28} />
        </div>
        <p className="text-sm">Naciśnij przycisk lub spację aby rozpocząć</p>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col gap-4 overflow-y-auto px-4 py-6">
      {messages.map((msg) => (
        <VoiceMessage
          key={msg.id}
          role={msg.role}
          text={msg.text}
          timestamp={msg.timestamp}
          audioUrl={msg.audioUrl}
          onPlayAudio={onPlayAudio}
        />
      ))}

      {isProcessing && (
        <div className="flex items-center gap-1 pl-11">
          <span className="h-2 w-2 animate-bounce rounded-full bg-[var(--text-muted)] [animation-delay:0ms]" />
          <span className="h-2 w-2 animate-bounce rounded-full bg-[var(--text-muted)] [animation-delay:150ms]" />
          <span className="h-2 w-2 animate-bounce rounded-full bg-[var(--text-muted)] [animation-delay:300ms]" />
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
