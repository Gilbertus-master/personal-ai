'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useOffline } from '@/lib/providers/offline-provider';
import { useOfflineStore } from '@/lib/stores/offline-store';
import {
  enqueue,
  flush,
  getQueueSize,
  clearQueue,
  type OutboxMessage,
} from '@/lib/offline/message-queue';

interface MessageQueueResult {
  sendOrQueue: (msg: { type: 'chat' | 'voice'; payload: unknown }) => Promise<void>;
  queueSize: number;
  flushQueue: () => Promise<void>;
  isSyncing: boolean;
}

export function useMessageQueue(
  sendFn: (msg: OutboxMessage) => Promise<void>,
): MessageQueueResult {
  const { isOnline } = useOffline();
  const prevOnlineRef = useRef(isOnline);
  const [queueSize, setQueueSize] = useState(0);
  const [isSyncing, setIsSyncing] = useState(false);
  const { incrementQueue, decrementQueue, setSyncStatus } = useOfflineStore();

  const refreshQueueSize = useCallback(async () => {
    const size = await getQueueSize();
    setQueueSize(size);
  }, []);

  // Load queue size on mount
  useEffect(() => {
    void refreshQueueSize();
  }, [refreshQueueSize]);

  const doFlush = useCallback(async () => {
    setIsSyncing(true);
    setSyncStatus('syncing');
    try {
      const result = await flush(sendFn);
      for (let i = 0; i < result.sent; i++) {
        decrementQueue();
      }
      if (result.failed > 0) {
        setSyncStatus('error');
      } else {
        setSyncStatus('idle');
      }
    } catch {
      setSyncStatus('error');
    } finally {
      setIsSyncing(false);
      await refreshQueueSize();
    }
  }, [sendFn, decrementQueue, setSyncStatus, refreshQueueSize]);

  // Auto-flush when transitioning from offline to online
  useEffect(() => {
    if (isOnline && !prevOnlineRef.current) {
      void doFlush();
    }
    prevOnlineRef.current = isOnline;
  }, [isOnline, doFlush]);

  const sendOrQueue = useCallback(
    async (msg: { type: 'chat' | 'voice'; payload: unknown }) => {
      if (isOnline) {
        try {
          const outboxMsg: OutboxMessage = {
            id: crypto.randomUUID(),
            type: msg.type,
            payload: msg.payload,
            createdAt: new Date().toISOString(),
            retries: 0,
          };
          await sendFn(outboxMsg);
          return;
        } catch {
          // Network failed mid-send — fall through to queue
        }
      }

      await enqueue(msg);
      incrementQueue();
      await refreshQueueSize();
    },
    [isOnline, sendFn, incrementQueue, refreshQueueSize],
  );

  const handleFlush = useCallback(async () => {
    await doFlush();
  }, [doFlush]);

  const handleClear = useCallback(async () => {
    await clearQueue();
    await refreshQueueSize();
  }, [refreshQueueSize]);

  return {
    sendOrQueue,
    queueSize,
    flushQueue: handleFlush,
    isSyncing,
  };
}
