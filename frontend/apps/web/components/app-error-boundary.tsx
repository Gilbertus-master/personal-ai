'use client';

import { Component, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

/**
 * React Error Boundary — catches rendering errors in child components
 * and reports them to the Gilbertus backend for autofix.
 */
export class AppErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    const API = `http://${window.location.hostname}:8000`;

    fetch(`${API}/errors/report`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: 'sebastian',
        error_type: 'render',
        error_message: error.message?.slice(0, 500),
        error_stack: (error.stack ?? '').slice(0, 1000),
        component: info.componentStack?.slice(0, 500),
        route: window.location.pathname,
        browser: navigator.userAgent.slice(0, 120),
        app_version: '0.2',
      }),
    }).catch(() => {});
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center',
          justifyContent: 'center', height: '100vh', gap: '16px',
          fontFamily: 'monospace', color: '#e0e0e0', background: '#0d0d1a',
        }}>
          <h2 style={{ color: '#f87171' }}>Błąd w module</h2>
          <p style={{ maxWidth: 600, textAlign: 'center', color: '#9ca3af', fontSize: 14 }}>
            {this.state.error?.message}
          </p>
          <p style={{ color: '#6b7280', fontSize: 12 }}>
            Błąd został automatycznie zgłoszony do systemu naprawczego.
          </p>
          <button
            onClick={() => {
              this.setState({ hasError: false, error: null });
              window.location.reload();
            }}
            style={{
              padding: '8px 24px', borderRadius: 8,
              background: '#6366f1', color: '#fff', border: 'none',
              cursor: 'pointer', fontSize: 14,
            }}
          >
            Odśwież stronę
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
