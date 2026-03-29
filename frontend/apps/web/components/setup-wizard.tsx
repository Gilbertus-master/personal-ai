'use client';

import { useEffect, useState } from 'react';

function isTauriEnv(): boolean {
  return typeof window !== 'undefined' && '__TAURI__' in window;
}

async function tauriInvoke(cmd: string, args?: Record<string, unknown>): Promise<unknown> {
  const { invoke } = await import('@tauri-apps/api/core');
  return invoke(cmd, args);
}

export function SetupWizard() {
  const [visible, setVisible] = useState(false);
  const [apiUrl, setApiUrl] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [status, setStatus] = useState<'idle' | 'testing' | 'error'>('idle');
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    if (!isTauriEnv()) return;

    tauriInvoke('check_first_run')
      .then((result) => {
        const r = result as { first_run: boolean };
        if (r.first_run) {
          setVisible(true);
        }
      })
      .catch(() => {
        // Not in Tauri or command not available
      });
  }, []);

  if (!visible) return null;

  const handleConnect = async () => {
    if (!apiUrl.trim()) {
      setStatus('error');
      setErrorMsg('Podaj adres serwera');
      return;
    }

    setStatus('testing');
    setErrorMsg('');

    try {
      const url = apiUrl.replace(/\/+$/, '');
      const response = await fetch(`${url}/health`, {
        method: 'GET',
        signal: AbortSignal.timeout(10000),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      await tauriInvoke('save_config', { apiUrl: url, apiKey });
      setVisible(false);
    } catch (err) {
      setStatus('error');
      setErrorMsg(
        err instanceof Error
          ? `Nie udalo sie polaczyc: ${err.message}`
          : 'Nie udalo sie polaczyc z serwerem'
      );
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'rgba(0, 0, 0, 0.7)',
        backdropFilter: 'blur(4px)',
      }}
    >
      <div
        style={{
          backgroundColor: 'var(--color-bg-secondary, #1e1e2e)',
          border: '1px solid var(--color-border, #333)',
          borderRadius: '12px',
          padding: '32px',
          width: '100%',
          maxWidth: '420px',
          color: 'var(--color-text, #e0e0e0)',
          fontFamily: 'inherit',
        }}
      >
        <h2 style={{ margin: '0 0 8px', fontSize: '20px', fontWeight: 600 }}>
          Konfiguracja poczatkowa
        </h2>
        <p style={{ margin: '0 0 24px', fontSize: '14px', opacity: 0.7 }}>
          Podaj dane polaczenia z serwerem
        </p>

        <label style={{ display: 'block', marginBottom: '16px' }}>
          <span style={{ display: 'block', marginBottom: '6px', fontSize: '13px', fontWeight: 500 }}>
            Adres serwera
          </span>
          <input
            type="text"
            value={apiUrl}
            onChange={(e) => setApiUrl(e.target.value)}
            placeholder="https://api.example.com"
            style={{
              width: '100%',
              padding: '10px 12px',
              backgroundColor: 'var(--color-bg-primary, #121220)',
              border: '1px solid var(--color-border, #444)',
              borderRadius: '8px',
              color: 'inherit',
              fontSize: '14px',
              outline: 'none',
              boxSizing: 'border-box',
            }}
          />
        </label>

        <label style={{ display: 'block', marginBottom: '24px' }}>
          <span style={{ display: 'block', marginBottom: '6px', fontSize: '13px', fontWeight: 500 }}>
            Klucz API
          </span>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="sk-..."
            style={{
              width: '100%',
              padding: '10px 12px',
              backgroundColor: 'var(--color-bg-primary, #121220)',
              border: '1px solid var(--color-border, #444)',
              borderRadius: '8px',
              color: 'inherit',
              fontSize: '14px',
              outline: 'none',
              boxSizing: 'border-box',
            }}
          />
        </label>

        {status === 'error' && (
          <p style={{ color: '#f87171', fontSize: '13px', margin: '0 0 16px' }}>
            {errorMsg}
          </p>
        )}

        <button
          onClick={handleConnect}
          disabled={status === 'testing'}
          style={{
            width: '100%',
            padding: '10px',
            backgroundColor: status === 'testing' ? '#555' : 'var(--color-primary, #6366f1)',
            color: '#fff',
            border: 'none',
            borderRadius: '8px',
            fontSize: '14px',
            fontWeight: 600,
            cursor: status === 'testing' ? 'not-allowed' : 'pointer',
          }}
        >
          {status === 'testing' ? 'Testowanie polaczenia...' : 'Polacz'}
        </button>
      </div>
    </div>
  );
}
