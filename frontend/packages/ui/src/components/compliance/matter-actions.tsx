'use client';

import { useState } from 'react';
import { Loader2, Search, ArrowRight, FileText, MessageSquare, Send } from 'lucide-react';

export interface MatterActionsProps {
  matterId: number;
  onResearch: (matterId: number) => void;
  onAdvance: (matterId: number) => void;
  onReport: (matterId: number) => void;
  onCommPlan: (matterId: number) => void;
  onExecuteComm: (matterId: number) => void;
  isResearching?: boolean;
  isAdvancing?: boolean;
  isReporting?: boolean;
  isCommPlanning?: boolean;
  isExecutingComm?: boolean;
}

export function MatterActions({
  matterId,
  onResearch,
  onAdvance,
  onReport,
  onCommPlan,
  onExecuteComm,
  isResearching = false,
  isAdvancing = false,
  isReporting = false,
  isCommPlanning = false,
  isExecutingComm = false,
}: MatterActionsProps) {
  const [confirmExec, setConfirmExec] = useState(false);
  const anyLoading = isResearching || isAdvancing || isReporting || isCommPlanning || isExecutingComm;

  const handleExecuteComm = () => {
    if (!confirmExec) {
      setConfirmExec(true);
      return;
    }
    onExecuteComm(matterId);
    setConfirmExec(false);
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      {/* Research */}
      <button
        onClick={() => onResearch(matterId)}
        disabled={anyLoading}
        className="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-50"
        style={{ borderColor: 'var(--border)', color: 'var(--text)' }}
      >
        {isResearching ? (
          <>
            <Loader2 size={14} className="animate-spin" />
            <span>Analizuję...</span>
          </>
        ) : (
          <>
            <Search size={14} />
            <span>Zbadaj</span>
          </>
        )}
      </button>

      {/* Advance */}
      <button
        onClick={() => onAdvance(matterId)}
        disabled={anyLoading}
        className="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-50"
        style={{ borderColor: 'var(--border)', color: 'var(--text)' }}
      >
        {isAdvancing ? (
          <Loader2 size={14} className="animate-spin" />
        ) : (
          <ArrowRight size={14} />
        )}
        <span>Następna faza</span>
      </button>

      {/* Report */}
      <button
        onClick={() => onReport(matterId)}
        disabled={anyLoading}
        className="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-50"
        style={{ borderColor: 'var(--border)', color: 'var(--text)' }}
      >
        {isReporting ? (
          <>
            <Loader2 size={14} className="animate-spin" />
            <span>Generuję...</span>
          </>
        ) : (
          <>
            <FileText size={14} />
            <span>Generuj raport</span>
          </>
        )}
      </button>

      {/* Comm Plan */}
      <button
        onClick={() => onCommPlan(matterId)}
        disabled={anyLoading}
        className="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-50"
        style={{ borderColor: 'var(--border)', color: 'var(--text)' }}
      >
        {isCommPlanning ? (
          <Loader2 size={14} className="animate-spin" />
        ) : (
          <MessageSquare size={14} />
        )}
        <span>Plan komunikacji</span>
      </button>

      {/* Execute Comm */}
      <button
        onClick={handleExecuteComm}
        disabled={anyLoading}
        className="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-50"
        style={{
          borderColor: confirmExec ? 'var(--accent)' : 'var(--border)',
          color: confirmExec ? 'var(--accent)' : 'var(--text)',
        }}
      >
        {isExecutingComm ? (
          <Loader2 size={14} className="animate-spin" />
        ) : (
          <Send size={14} />
        )}
        <span>{confirmExec ? 'Potwierdź wysyłkę' : 'Wyślij komunikację'}</span>
      </button>
    </div>
  );
}
