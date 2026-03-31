'use client';

import { useEffect, useState } from 'react';

export default function TestDataPage() {
  const [results, setResults] = useState<Record<string, string>>({});

  useEffect(() => {
    const apiBase = `http://${window.location.hostname}:8000`;
    const endpoints = ['/status', '/brief/today', '/alerts', '/admin/roles'];

    endpoints.forEach(async (ep) => {
      try {
        const res = await fetch(`${apiBase}${ep}`);
        const data = await res.json();
        setResults(prev => ({ ...prev, [ep]: `${res.status} OK — keys: ${Object.keys(data).join(', ')}` }));
      } catch (e: any) {
        setResults(prev => ({ ...prev, [ep]: `ERROR: ${e.message}` }));
      }
    });
  }, []);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-[var(--text)]">Test Data Loading</h1>
      <p className="text-sm text-[var(--text-secondary)]">
        API Base: http://{typeof window !== 'undefined' ? window.location.hostname : '?'}:8000
      </p>
      {Object.entries(results).map(([ep, result]) => (
        <div key={ep} className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3">
          <span className="font-mono text-sm font-bold text-[var(--text)]">{ep}</span>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">{result}</p>
        </div>
      ))}
      {Object.keys(results).length === 0 && (
        <p className="text-[var(--text-secondary)]">Ładowanie...</p>
      )}
    </div>
  );
}
