/**
 * Omnius Plugin Development UI — vanilla React (createElement, no JSX).
 * Loaded by index.html as a separate script.
 */

/* global React, API_BASE, getHeaders, currentUser */

const { createElement: h, useState, useEffect, useRef, useCallback, Fragment } = React;

// ── Status badge colors ───────────────────────────────────────────────────

const STATUS_COLORS = {
  pending:    { bg: '#eab30822', color: '#eab308', border: '#eab30844' },
  approved:   { bg: '#22c55e22', color: '#22c55e', border: '#22c55e44' },
  rejected:   { bg: '#ef444422', color: '#ef4444', border: '#ef444444' },
  developing: { bg: '#3b82f622', color: '#3b82f6', border: '#3b82f644' },
  reviewing:  { bg: '#a855f722', color: '#a855f7', border: '#a855f744' },
  deployed:   { bg: '#22c55e44', color: '#22c55e', border: '#22c55e88' },
};

const STATUS_LABELS = {
  pending: 'Oczekuje',
  approved: 'Zatwierdzony',
  rejected: 'Odrzucony',
  developing: 'W budowie',
  reviewing: 'Recenzja',
  deployed: 'Wdrozony',
};

// ── Helper: fetch with auth ───────────────────────────────────────────────

async function pluginFetch(path, options = {}) {
  const resp = await fetch(`${API_BASE}/api/v1/plugin-dev${path}`, {
    headers: getHeaders(),
    ...options,
  });
  return resp.json();
}

async function pluginPost(path, body) {
  return pluginFetch(path, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

// ── StatusBadge ───────────────────────────────────────────────────────────

function StatusBadge({ status }) {
  const c = STATUS_COLORS[status] || STATUS_COLORS.pending;
  return h('span', {
    style: {
      padding: '2px 10px',
      borderRadius: '4px',
      fontSize: '11px',
      fontWeight: 600,
      textTransform: 'uppercase',
      background: c.bg,
      color: c.color,
      border: `1px solid ${c.border}`,
    },
  }, STATUS_LABELS[status] || status);
}

// ── ProposalForm ──────────────────────────────────────────────────────────

function ProposalForm({ onSubmitted }) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [expectedValue, setExpectedValue] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);

  const handleSubmit = useCallback(async () => {
    if (!title.trim() || !description.trim()) return;
    setSubmitting(true);
    setResult(null);
    try {
      const res = await pluginPost('/propose', {
        title: title.trim(),
        description: description.trim(),
        expected_value: expectedValue.trim(),
      });
      setResult(res);
      if (res.status === 'approved' || res.status === 'pending') {
        setTitle('');
        setDescription('');
        setExpectedValue('');
        if (onSubmitted) onSubmitted();
      }
    } catch (e) {
      setResult({ status: 'error', error: e.message });
    }
    setSubmitting(false);
  }, [title, description, expectedValue, onSubmitted]);

  const inputStyle = {
    width: '100%',
    padding: '8px 12px',
    background: 'var(--bg)',
    border: '1px solid var(--border)',
    borderRadius: '6px',
    color: 'var(--text)',
    fontSize: '14px',
    fontFamily: 'inherit',
    marginBottom: '12px',
  };

  const textareaStyle = { ...inputStyle, minHeight: '80px', resize: 'vertical' };

  return h('div', { style: { marginBottom: '24px' } },
    h('h3', { style: { marginBottom: '16px', fontSize: '16px' } }, 'Nowa propozycja wtyczki'),

    h('label', { style: { fontSize: '13px', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' } }, 'Tytul'),
    h('input', { type: 'text', value: title, onChange: e => setTitle(e.target.value), style: inputStyle, placeholder: 'Nazwa wtyczki...' }),

    h('label', { style: { fontSize: '13px', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' } }, 'Opis'),
    h('textarea', { value: description, onChange: e => setDescription(e.target.value), style: textareaStyle, placeholder: 'Co ta wtyczka robi...' }),

    h('label', { style: { fontSize: '13px', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' } }, 'Oczekiwana wartosc'),
    h('textarea', { value: expectedValue, onChange: e => setExpectedValue(e.target.value), style: textareaStyle, placeholder: 'Jaka wartosc biznesowa przyniesie...' }),

    h('button', {
      className: 'btn btn-primary',
      onClick: handleSubmit,
      disabled: submitting || !title.trim() || !description.trim(),
      style: { opacity: submitting ? 0.5 : 1 },
    }, submitting ? 'Wysylanie...' : 'Wyslij propozycje'),

    result && h('div', {
      style: {
        marginTop: '16px',
        padding: '12px 16px',
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: '8px',
        fontSize: '13px',
      },
    },
      h('div', { style: { display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' } },
        h('strong', null, 'Status: '),
        h(StatusBadge, { status: result.status }),
        result.value_score != null && h('span', { style: { color: 'var(--text-muted)' } }, ` (ocena: ${result.value_score})`),
      ),
      result.governance_result && h('div', { style: { marginTop: '8px' } },
        result.governance_result.feasibility && h('div', null,
          h('strong', null, 'Wykonalnosc: '),
          result.governance_result.feasibility.reasoning,
        ),
        result.governance_result.value && h('div', { style: { marginTop: '4px' } },
          h('strong', null, 'Wartosc: '),
          result.governance_result.value.reasoning,
        ),
        result.governance_result.duplicate_check && result.governance_result.duplicate_check.is_duplicate && h('div', { style: { marginTop: '4px', color: 'var(--error)' } },
          h('strong', null, 'Duplikat: '),
          result.governance_result.duplicate_check.reasoning,
        ),
      ),
      result.error && h('div', { style: { color: 'var(--error)', marginTop: '4px' } }, result.error),
    ),
  );
}

// ── ProposalDetail ────────────────────────────────────────────────────────

function ProposalDetail({ proposal }) {
  if (!proposal) return null;

  const gov = proposal.governance_result;
  const review = proposal.review_result;

  return h('div', {
    style: {
      padding: '16px',
      background: 'var(--bg)',
      border: '1px solid var(--border)',
      borderRadius: '8px',
      marginTop: '8px',
      fontSize: '13px',
      lineHeight: 1.6,
    },
  },
    h('div', null, h('strong', null, 'Opis: '), proposal.description),
    proposal.expected_value && h('div', { style: { marginTop: '4px' } }, h('strong', null, 'Oczekiwana wartosc: '), proposal.expected_value),
    proposal.value_score != null && h('div', { style: { marginTop: '4px' } }, h('strong', null, 'Ocena: '), proposal.value_score),

    gov && h('div', { style: { marginTop: '12px' } },
      h('strong', null, 'Governance:'),
      gov.feasibility && h('div', { style: { marginLeft: '8px', marginTop: '4px' } },
        `Wykonalnosc: ${gov.feasibility.possible ? 'TAK' : 'NIE'} (${gov.feasibility.score}) — ${gov.feasibility.reasoning}`),
      gov.value && h('div', { style: { marginLeft: '8px' } },
        `Wartosc: ${gov.value.approved ? 'TAK' : 'NIE'} (${gov.value.value_score}) — ${gov.value.reasoning}`),
      gov.cost_estimate && h('div', { style: { marginLeft: '8px' } },
        `Koszt: ${gov.cost_estimate.development_time_hours}h dev, ${gov.cost_estimate.complexity} zlozonosc`),
      gov.duplicate_check && gov.duplicate_check.is_duplicate && h('div', { style: { marginLeft: '8px', color: 'var(--error)' } },
        `DUPLIKAT: ${gov.duplicate_check.similar_plugin} — ${gov.duplicate_check.reasoning}`),
    ),

    review && h('div', { style: { marginTop: '12px' } },
      h('strong', null, 'Recenzja kodu:'),
      h('div', { style: { marginLeft: '8px', marginTop: '4px' } },
        `Wynik: ${review.passed ? 'POZYTYWNY' : 'NEGATYWNY'} | Bezpieczenstwo: ${review.security_score} | Jakosc: ${review.quality_score} | Testy: ${review.tests_passed}/${review.tests_total}`),
      review.findings && review.findings.length > 0 && h('div', { style: { marginLeft: '8px', marginTop: '4px' } },
        review.findings.map((f, i) =>
          h('div', { key: i, style: { color: f.severity === 'critical' || f.severity === 'high' ? 'var(--error)' : 'var(--text-muted)' } },
            `[${f.severity}] ${f.title}: ${f.description}`)
        ),
      ),
    ),
  );
}

// ── DevChat (sandbox terminal) ────────────────────────────────────────────

function DevChat({ sessionId, proposalId, onReviewSubmitted }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [connected, setConnected] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const wsRef = useRef(null);
  const outputRef = useRef(null);

  useEffect(() => {
    if (!sessionId) return;

    const session = JSON.parse(localStorage.getItem('omnius_session') || '{}');
    const apiKey = session.devEmail || '';
    const wsUrl = `${API_BASE.replace('http', 'ws')}/api/v1/plugin-dev/ws/${sessionId}?api_key=${encodeURIComponent(apiKey)}`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      setMessages(prev => [...prev, { type: 'system', text: 'Polaczono z sandboxem.' }]);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'output') {
          setMessages(prev => [...prev, { type: 'output', text: data.data }]);
        } else if (data.type === 'done') {
          setMessages(prev => [...prev, { type: 'system', text: '--- Komenda zakonczona ---' }]);
        } else if (data.error) {
          setMessages(prev => [...prev, { type: 'error', text: data.error }]);
        }
      } catch (e) {
        setMessages(prev => [...prev, { type: 'output', text: event.data }]);
      }
    };

    ws.onerror = () => {
      setMessages(prev => [...prev, { type: 'error', text: 'Blad polaczenia WebSocket' }]);
    };

    ws.onclose = () => {
      setConnected(false);
      setMessages(prev => [...prev, { type: 'system', text: 'Rozlaczono.' }]);
    };

    return () => {
      ws.close();
    };
  }, [sessionId]);

  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [messages]);

  const sendCommand = useCallback(() => {
    if (!input.trim() || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(JSON.stringify({ command: input.trim() }));
    setMessages(prev => [...prev, { type: 'command', text: `$ ${input.trim()}` }]);
    setInput('');
  }, [input]);

  const handleSubmitReview = useCallback(async () => {
    setSubmitting(true);
    try {
      const res = await pluginPost(`/proposals/${proposalId}/submit`, {});
      setMessages(prev => [...prev, {
        type: res.review_result?.passed ? 'system' : 'error',
        text: res.review_result?.passed
          ? 'Recenzja POZYTYWNA — wtyczka wyslana do zatwierdzenia.'
          : `Recenzja NEGATYWNA — popraw bledy i sprobuj ponownie. Znaleziono ${(res.review_result?.findings || []).length} problemow.`,
      }]);
      if (onReviewSubmitted) onReviewSubmitted(res);
    } catch (e) {
      setMessages(prev => [...prev, { type: 'error', text: `Blad: ${e.message}` }]);
    }
    setSubmitting(false);
  }, [proposalId, onReviewSubmitted]);

  const msgColor = { system: 'var(--text-muted)', output: 'var(--text)', command: 'var(--accent)', error: 'var(--error)' };

  return h('div', { style: { marginTop: '16px' } },
    h('h3', { style: { fontSize: '15px', marginBottom: '8px' } }, 'Sandbox Development'),

    // Terminal output
    h('div', {
      ref: outputRef,
      style: {
        background: '#0a0a0f',
        border: '1px solid var(--border)',
        borderRadius: '8px',
        padding: '12px',
        height: '300px',
        overflowY: 'auto',
        fontFamily: 'monospace',
        fontSize: '12px',
        lineHeight: 1.5,
      },
    }, messages.map((m, i) =>
      h('div', { key: i, style: { color: msgColor[m.type] || 'var(--text)', whiteSpace: 'pre-wrap' } }, m.text)
    )),

    // Input
    h('div', { style: { display: 'flex', gap: '8px', marginTop: '8px' } },
      h('input', {
        type: 'text',
        value: input,
        onChange: e => setInput(e.target.value),
        onKeyDown: e => { if (e.key === 'Enter') sendCommand(); },
        placeholder: connected ? 'Wpisz komende...' : 'Laczenie...',
        disabled: !connected,
        style: {
          flex: 1,
          padding: '8px 12px',
          background: 'var(--bg)',
          border: '1px solid var(--border)',
          borderRadius: '6px',
          color: 'var(--text)',
          fontSize: '13px',
          fontFamily: 'monospace',
        },
      }),
      h('button', {
        className: 'btn btn-primary',
        onClick: sendCommand,
        disabled: !connected || !input.trim(),
        style: { padding: '8px 16px', fontSize: '13px' },
      }, 'Wyslij'),
    ),

    // Submit for review
    h('div', { style: { marginTop: '12px' } },
      h('button', {
        className: 'btn',
        onClick: handleSubmitReview,
        disabled: submitting,
        style: {
          background: '#a855f7',
          color: 'white',
          padding: '8px 20px',
          fontSize: '13px',
          opacity: submitting ? 0.5 : 1,
        },
      }, submitting ? 'Wysylanie do recenzji...' : 'Wyslij do recenzji'),
    ),
  );
}

// ── Main PluginDevTab ─────────────────────────────────────────────────────

function PluginDevTab() {
  const [proposals, setProposals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [expandedId, setExpandedId] = useState(null);
  const [expandedData, setExpandedData] = useState(null);

  const loadProposals = useCallback(async () => {
    setLoading(true);
    try {
      const data = await pluginFetch('/proposals');
      setProposals(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error('Failed to load proposals:', e);
      setProposals([]);
    }
    setLoading(false);
  }, []);

  useEffect(() => { loadProposals(); }, [loadProposals]);

  const handleExpand = useCallback(async (id) => {
    if (expandedId === id) {
      setExpandedId(null);
      setExpandedData(null);
      return;
    }
    setExpandedId(id);
    try {
      const data = await pluginFetch(`/proposals/${id}`);
      setExpandedData(data);
    } catch (e) {
      setExpandedData(null);
    }
  }, [expandedId]);

  const handleStartDev = useCallback(async (proposalId) => {
    try {
      await pluginPost(`/proposals/${proposalId}/start-dev`, {});
      loadProposals();
      // Reload detail
      const data = await pluginFetch(`/proposals/${proposalId}`);
      setExpandedData(data);
    } catch (e) {
      alert('Blad: ' + e.message);
    }
  }, [loadProposals]);

  const tableStyle = {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: '13px',
  };

  const thStyle = {
    textAlign: 'left',
    padding: '8px 12px',
    borderBottom: '1px solid var(--border)',
    color: 'var(--text-muted)',
    fontSize: '12px',
    fontWeight: 600,
    textTransform: 'uppercase',
  };

  const tdStyle = {
    padding: '10px 12px',
    borderBottom: '1px solid var(--border)',
  };

  return h('div', { style: { padding: '24px', maxWidth: '1000px', margin: '0 auto' } },
    // Header
    h('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' } },
      h('h2', { style: { fontSize: '20px' } }, 'Wtyczki'),
      h('button', {
        className: 'btn btn-primary',
        onClick: () => setShowForm(!showForm),
        style: { padding: '8px 20px', fontSize: '13px' },
      }, showForm ? 'Anuluj' : 'Nowa propozycja'),
    ),

    // Form
    showForm && h(ProposalForm, { onSubmitted: () => { loadProposals(); setShowForm(false); } }),

    // Table
    loading
      ? h('div', { style: { color: 'var(--text-muted)', textAlign: 'center', padding: '40px' } }, 'Ladowanie...')
      : proposals.length === 0
        ? h('div', { style: { color: 'var(--text-muted)', textAlign: 'center', padding: '40px' } }, 'Brak propozycji wtyczek.')
        : h('table', { style: tableStyle },
            h('thead', null,
              h('tr', null,
                h('th', { style: thStyle }, 'Tytul'),
                h('th', { style: thStyle }, 'Status'),
                h('th', { style: thStyle }, 'Ocena'),
                h('th', { style: thStyle }, 'Autor'),
                h('th', { style: thStyle }, 'Data'),
              ),
            ),
            h('tbody', null,
              proposals.map(p =>
                h(Fragment, { key: p.id },
                  h('tr', {
                    onClick: () => handleExpand(p.id),
                    style: { cursor: 'pointer', background: expandedId === p.id ? 'var(--surface)' : 'transparent' },
                  },
                    h('td', { style: tdStyle }, p.title),
                    h('td', { style: tdStyle }, h(StatusBadge, { status: p.status })),
                    h('td', { style: tdStyle }, p.value_score != null ? p.value_score.toFixed(2) : '—'),
                    h('td', { style: tdStyle }, p.proposed_by || '—'),
                    h('td', { style: { ...tdStyle, color: 'var(--text-muted)' } }, p.created_at?.split('T')[0] || p.created_at?.split(' ')[0] || '—'),
                  ),
                  expandedId === p.id && expandedData && h('tr', null,
                    h('td', { colSpan: 5, style: { padding: '0 12px 16px' } },
                      h(ProposalDetail, { proposal: expandedData }),
                      // Start dev button
                      expandedData.status === 'approved' && h('div', { style: { marginTop: '12px' } },
                        h('button', {
                          className: 'btn btn-primary',
                          onClick: (e) => { e.stopPropagation(); handleStartDev(expandedData.id); },
                          style: { padding: '8px 20px', fontSize: '13px' },
                        }, 'Rozpocznij development'),
                      ),
                      // Dev chat
                      expandedData.status === 'developing' && expandedData.sandbox_session_id &&
                        h(DevChat, {
                          sessionId: expandedData.sandbox_session_id,
                          proposalId: expandedData.id,
                          onReviewSubmitted: () => { loadProposals(); pluginFetch(`/proposals/${expandedData.id}`).then(setExpandedData); },
                        }),
                    ),
                  ),
                ),
              ),
            ),
          ),
  );
}

// Export for use in index.html
window.PluginDevTab = PluginDevTab;
