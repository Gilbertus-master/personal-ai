import { useCallback, useEffect, useRef, useState } from 'react';

export type TerminalStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

interface UseTerminalOptions {
  apiUrl: string;
  apiKey: string;
  cmd?: string;
  reconnectDelay?: number;
  maxReconnects?: number;
}

interface UseTerminalReturn {
  connect: () => void;
  disconnect: () => void;
  sendData: (data: string) => void;
  sendResize: (cols: number, rows: number) => void;
  status: TerminalStatus;
  onData: (callback: (data: ArrayBuffer | string) => void) => void;
}

export function useTerminal({
  apiUrl,
  apiKey,
  cmd = 'bash',
  reconnectDelay = 3000,
  maxReconnects = 5,
}: UseTerminalOptions): UseTerminalReturn {
  const wsRef = useRef<WebSocket | null>(null);
  const dataCallbackRef = useRef<((data: ArrayBuffer | string) => void) | null>(null);
  const reconnectCountRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const intentionalCloseRef = useRef(false);
  const [status, setStatus] = useState<TerminalStatus>('disconnected');

  const cleanup = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.onopen = null;
      wsRef.current.onclose = null;
      wsRef.current.onmessage = null;
      wsRef.current.onerror = null;
      if (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING) {
        wsRef.current.close();
      }
      wsRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    cleanup();
    intentionalCloseRef.current = false;
    setStatus('connecting');

    const wsUrl = apiUrl
      .replace(/^http/, 'ws')
      .replace(/\/$/, '');

    const url = `${wsUrl}/terminal/ws?api_key=${encodeURIComponent(apiKey)}&cmd=${encodeURIComponent(cmd)}`;

    const ws = new WebSocket(url);
    ws.binaryType = 'arraybuffer';
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus('connected');
      reconnectCountRef.current = 0;
    };

    ws.onmessage = (event) => {
      if (dataCallbackRef.current) {
        dataCallbackRef.current(event.data);
      }
    };

    ws.onerror = () => {
      setStatus('error');
    };

    ws.onclose = (event) => {
      wsRef.current = null;

      if (intentionalCloseRef.current) {
        setStatus('disconnected');
        return;
      }

      if (event.code === 4003) {
        setStatus('error');
        return;
      }

      if (reconnectCountRef.current < maxReconnects) {
        setStatus('connecting');
        reconnectCountRef.current += 1;
        reconnectTimerRef.current = setTimeout(() => {
          connect();
        }, reconnectDelay);
      } else {
        setStatus('disconnected');
      }
    };
  }, [apiUrl, apiKey, cmd, cleanup, maxReconnects, reconnectDelay]);

  const disconnect = useCallback(() => {
    intentionalCloseRef.current = true;
    cleanup();
    setStatus('disconnected');
  }, [cleanup]);

  const sendData = useCallback((data: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(data);
    }
  }, []);

  const sendResize = useCallback((cols: number, rows: number) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'resize', cols, rows }));
    }
  }, []);

  const onData = useCallback((callback: (data: ArrayBuffer | string) => void) => {
    dataCallbackRef.current = callback;
  }, []);

  useEffect(() => {
    return () => {
      intentionalCloseRef.current = true;
      cleanup();
    };
  }, [cleanup]);

  return { connect, disconnect, sendData, sendResize, status, onData };
}
