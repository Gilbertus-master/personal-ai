'use client';

import { useRef, useEffect, useState, useCallback } from 'react';
import { ArrowDown } from 'lucide-react';
import { MessageBubble } from './message-bubble';
import type { MessageBubbleMessage } from './message-bubble';

const SCROLL_THRESHOLD = 100;

export interface MessageListProps {
  messages: MessageBubbleMessage[];
  onRetry: (messageId: string) => void;
}

export function MessageList({ messages, onRetry }: MessageListProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const [newMessageCount, setNewMessageCount] = useState(0);
  const prevMessageCountRef = useRef(messages.length);

  const checkIfAtBottom = useCallback(() => {
    const el = containerRef.current;
    if (!el) return true;
    return el.scrollHeight - el.scrollTop - el.clientHeight <= SCROLL_THRESHOLD;
  }, []);

  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'smooth') => {
    bottomRef.current?.scrollIntoView({ behavior });
    setNewMessageCount(0);
  }, []);

  // Track scroll position
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const handleScroll = () => {
      const atBottom = checkIfAtBottom();
      setIsAtBottom(atBottom);
      if (atBottom) {
        setNewMessageCount(0);
      }
    };

    el.addEventListener('scroll', handleScroll, { passive: true });
    return () => el.removeEventListener('scroll', handleScroll);
  }, [checkIfAtBottom]);

  // Auto-scroll on new messages
  useEffect(() => {
    const prevCount = prevMessageCountRef.current;
    const currentCount = messages.length;
    prevMessageCountRef.current = currentCount;

    if (currentCount <= prevCount) return;

    const added = currentCount - prevCount;

    if (isAtBottom) {
      // User is at bottom — scroll to new messages
      requestAnimationFrame(() => scrollToBottom('smooth'));
    } else {
      // User scrolled up — show badge
      setNewMessageCount((prev) => prev + added);
    }
  }, [messages.length, isAtBottom, scrollToBottom]);

  // Instant scroll on first render
  useEffect(() => {
    scrollToBottom('instant');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="relative flex-1 min-h-0">
      <div
        ref={containerRef}
        className="h-full overflow-y-auto px-4 py-6"
      >
        <div className="mx-auto max-w-3xl space-y-4">
          {messages.map((msg) => (
            <MessageBubble
              key={msg.id}
              message={msg}
              onRetry={() => onRetry(msg.id)}
            />
          ))}
          <div ref={bottomRef} aria-hidden="true" />
        </div>
      </div>

      {/* Scroll-to-bottom FAB */}
      {!isAtBottom && (
        <button
          onClick={() => scrollToBottom('smooth')}
          className="absolute bottom-4 right-4 flex items-center justify-center rounded-full bg-[--bg-secondary] border border-[--border] shadow-lg p-2 hover:bg-[--bg-hover] transition-colors"
          aria-label="Scroll to bottom"
        >
          <ArrowDown className="h-5 w-5 text-[--text-secondary]" />
          {newMessageCount > 0 && (
            <span className="absolute -top-2 -right-2 flex h-5 min-w-5 items-center justify-center rounded-full bg-blue-600 px-1 text-xs font-medium text-white">
              {newMessageCount}
            </span>
          )}
        </button>
      )}
    </div>
  );
}
