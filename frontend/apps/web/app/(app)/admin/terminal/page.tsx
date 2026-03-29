'use client';

import { useEffect, useRef, useState } from 'react';
import { useSession } from 'next-auth/react';
import { useTerminal, type TerminalStatus } from '@/lib/hooks/use-terminal';

const API_URL =
  process.env.NEXT_PUBLIC_GILBERTUS_API_URL ?? 'http://127.0.0.1:8000';

function StatusBadge({ status }: { status: TerminalStatus }) {
  const colors: Record<TerminalStatus, string> = {
    connected: 'bg-green-500',
    connecting: 'bg-yellow-500 animate-pulse',
    disconnected: 'bg-gray-500',
    error: 'bg-red-500',
  };

  const labels: Record<TerminalStatus, string> = {
    connected: 'Connected',
    connecting: 'Connecting...',
    disconnected: 'Disconnected',
    error: 'Error',
  };

  return (
    <div className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
      <span className={`inline-block h-2 w-2 rounded-full ${colors[status]}`} />
      {labels[status]}
    </div>
  );
}

export default function TerminalPage() {
  const { data: session } = useSession();
  const termRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<any>(null);
  const fitAddonRef = useRef<any>(null);
  const [ready, setReady] = useState(false);

  // Get API key from session cookie or env
  const apiKey =
    (session?.user as any)?.authType === 'api_key'
      ? (process.env.NEXT_PUBLIC_GILBERTUS_API_KEY ?? '')
      : '';

  const { connect, disconnect, sendData, sendResize, status, onData } =
    useTerminal({
      apiUrl: API_URL,
      apiKey,
    });

  // Load xterm.js dynamically (browser-only)
  useEffect(() => {
    let cancelled = false;

    async function loadXterm() {
      const [xtermMod, fitMod, linksMod] = await Promise.all([
        import('@xterm/xterm'),
        import('@xterm/addon-fit'),
        import('@xterm/addon-web-links'),
      ]);

      if (cancelled || !termRef.current) return;

      const terminal = new xtermMod.Terminal({
        cursorBlink: true,
        fontSize: 14,
        fontFamily: '"JetBrains Mono", "Fira Code", "Cascadia Code", monospace',
        theme: {
          background: '#0d1117',
          foreground: '#c9d1d9',
          cursor: '#58a6ff',
          selectionBackground: '#264f78',
          black: '#0d1117',
          red: '#ff7b72',
          green: '#7ee787',
          yellow: '#d29922',
          blue: '#58a6ff',
          magenta: '#bc8cff',
          cyan: '#39d353',
          white: '#c9d1d9',
          brightBlack: '#484f58',
          brightRed: '#ffa198',
          brightGreen: '#56d364',
          brightYellow: '#e3b341',
          brightBlue: '#79c0ff',
          brightMagenta: '#d2a8ff',
          brightCyan: '#56d364',
          brightWhite: '#f0f6fc',
        },
        allowProposedApi: true,
      });

      const fitAddon = new fitMod.FitAddon();
      const webLinksAddon = new linksMod.WebLinksAddon();

      terminal.loadAddon(fitAddon);
      terminal.loadAddon(webLinksAddon);
      terminal.open(termRef.current);

      fitAddon.fit();

      xtermRef.current = terminal;
      fitAddonRef.current = fitAddon;
      setReady(true);
    }

    loadXterm();

    return () => {
      cancelled = true;
      if (xtermRef.current) {
        xtermRef.current.dispose();
        xtermRef.current = null;
      }
    };
  }, []);

  // Connect terminal data flow once xterm is ready
  useEffect(() => {
    if (!ready || !xtermRef.current) return;

    const terminal = xtermRef.current;

    // Terminal input → WebSocket
    const disposable = terminal.onData((data: string) => {
      sendData(data);
    });

    // WebSocket → Terminal output
    onData((data: ArrayBuffer | string) => {
      if (data instanceof ArrayBuffer) {
        terminal.write(new Uint8Array(data));
      } else {
        terminal.write(data);
      }
    });

    // Connect WebSocket
    connect();

    return () => {
      disposable.dispose();
      disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready]);

  // Handle resize
  useEffect(() => {
    if (!ready || !fitAddonRef.current || !xtermRef.current) return;

    const handleResize = () => {
      const fitAddon = fitAddonRef.current;
      const terminal = xtermRef.current;
      if (!fitAddon || !terminal) return;

      fitAddon.fit();
      sendResize(terminal.cols, terminal.rows);
    };

    // Initial resize
    handleResize();

    window.addEventListener('resize', handleResize);

    const observer = new ResizeObserver(() => {
      handleResize();
    });

    if (termRef.current) {
      observer.observe(termRef.current);
    }

    return () => {
      window.removeEventListener('resize', handleResize);
      observer.disconnect();
    };
  }, [ready, sendResize]);

  // Inject xterm CSS on mount
  useEffect(() => {
    const id = 'xterm-css';
    if (document.getElementById(id)) return;

    const style = document.createElement('style');
    style.id = id;
    // Minimal critical xterm styles; the Terminal constructor handles canvas rendering
    style.textContent = `
      .xterm { position: relative; user-select: none; -ms-user-select: none; -webkit-user-select: none; }
      .xterm.focus, .xterm:focus { outline: none; }
      .xterm .xterm-helpers { position: absolute; top: 0; z-index: 5; }
      .xterm .xterm-helper-textarea {
        padding: 0; border: 0; margin: 0; position: absolute; opacity: 0;
        left: -9999em; top: 0; width: 0; height: 0; z-index: -5;
        white-space: nowrap; overflow: hidden; resize: none;
      }
      .xterm .composition-view { display: none; }
      .xterm .xterm-viewport { overflow-y: scroll; cursor: default; position: absolute; right: 0; left: 0; top: 0; bottom: 0; }
      .xterm .xterm-screen { position: relative; }
      .xterm .xterm-screen canvas { position: absolute; left: 0; top: 0; }
      .xterm .xterm-decoration-container .xterm-decoration { z-index: 6; position: absolute; }
      .xterm .xterm-scroll-area { visibility: hidden; }
      .xterm-char-measure-element { display: inline-block; visibility: hidden; position: absolute; top: 0; left: -9999em; line-height: normal; }
      .xterm.enable-mouse-events { cursor: default; }
      .xterm .xterm-cursor-pointer { cursor: pointer; }
      .xterm.column-select.focus { cursor: crosshair; }
      .xterm .xterm-rows { position: absolute; left: 0; top: 0; }
    `;
    document.head.appendChild(style);
  }, []);

  return (
    <div className="flex h-full flex-col">
      {/* Toolbar */}
      <div className="flex items-center justify-between border-b border-[var(--border)] bg-[var(--surface)] px-4 py-2">
        <h1 className="text-sm font-semibold text-[var(--text)]">Terminal</h1>
        <div className="flex items-center gap-4">
          <StatusBadge status={status} />
          {status === 'disconnected' && (
            <button
              onClick={connect}
              className="rounded-md bg-[var(--accent)] px-3 py-1 text-xs font-medium text-white hover:opacity-90 transition-opacity"
            >
              Reconnect
            </button>
          )}
        </div>
      </div>

      {/* Terminal */}
      <div
        ref={termRef}
        className="flex-1 bg-[#0d1117]"
        style={{ padding: '4px' }}
      />
    </div>
  );
}
