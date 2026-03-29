'use client';

import { useState, useEffect, useCallback } from 'react';
import { X, Loader2, FileText } from 'lucide-react';
import { DropZone } from './drop-zone';

export interface UploadModalProps {
  open: boolean;
  onClose: () => void;
  onUpload: (file: File, classification?: string) => void;
  isUploading?: boolean;
  progress?: number;
}

const CLASSIFICATIONS = [
  { value: 'public', label: 'Publiczny' },
  { value: 'internal', label: 'Wewnętrzny' },
  { value: 'confidential', label: 'Poufny' },
] as const;

const ACCEPTED_TYPES = '.pdf,.docx,.xlsx,.txt,.png,.jpg,.jpeg';

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function UploadModal({
  open,
  onClose,
  onUpload,
  isUploading = false,
  progress,
}: UploadModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [classification, setClassification] = useState('internal');

  useEffect(() => {
    if (open) {
      setFile(null);
      setClassification('internal');
    }
  }, [open]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    },
    [onClose],
  );

  useEffect(() => {
    if (open) {
      document.addEventListener('keydown', handleKeyDown);
      return () => document.removeEventListener('keydown', handleKeyDown);
    }
  }, [open, handleKeyDown]);

  if (!open) return null;

  const handleUpload = () => {
    if (!file) return;
    onUpload(file, classification);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      style={{ backgroundColor: 'rgba(0, 0, 0, 0.6)' }}
    >
      <div
        className="relative w-full max-w-lg rounded-lg p-6 shadow-xl"
        style={{ backgroundColor: 'var(--bg)', border: '1px solid var(--border)' }}
      >
        {/* Header */}
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold" style={{ color: 'var(--text)' }}>
            Wgraj dokument
          </h2>
          <button
            onClick={onClose}
            className="rounded-md p-1 transition-colors"
            style={{ color: 'var(--text-secondary)' }}
          >
            <X size={18} />
          </button>
        </div>

        <div className="space-y-4">
          {/* Drop zone */}
          {!file && (
            <DropZone
              onFileSelect={setFile}
              accept={ACCEPTED_TYPES}
              disabled={isUploading}
            />
          )}

          {/* File preview */}
          {file && (
            <div
              className="flex items-center gap-3 rounded-md border p-3"
              style={{ borderColor: 'var(--border)', backgroundColor: 'var(--surface)' }}
            >
              <FileText size={20} style={{ color: 'var(--text-secondary)' }} />
              <div className="flex-1 min-w-0">
                <p className="truncate text-sm font-medium" style={{ color: 'var(--text)' }}>
                  {file.name}
                </p>
                <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                  {formatFileSize(file.size)}
                </p>
              </div>
              {!isUploading && (
                <button
                  onClick={() => setFile(null)}
                  className="rounded-md p-1 transition-colors"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  <X size={14} />
                </button>
              )}
            </div>
          )}

          {/* Classification */}
          <label className="space-y-1">
            <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              Klasyfikacja
            </span>
            <select
              value={classification}
              onChange={(e) => setClassification(e.target.value)}
              disabled={isUploading}
              className="block w-full rounded-md border px-3 py-1.5 text-sm"
              style={{
                backgroundColor: 'var(--surface)',
                borderColor: 'var(--border)',
                color: 'var(--text)',
              }}
            >
              {CLASSIFICATIONS.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </label>

          {/* Progress bar */}
          {isUploading && progress != null && (
            <div className="space-y-1">
              <div className="h-2 w-full rounded-full" style={{ backgroundColor: 'var(--border)' }}>
                <div
                  className="h-full rounded-full bg-[var(--accent)] transition-all"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <p className="text-xs text-center" style={{ color: 'var(--text-secondary)' }}>
                {progress}%
              </p>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="mt-6 flex justify-end gap-3">
          <button
            onClick={onClose}
            disabled={isUploading}
            className="rounded-md px-4 py-1.5 text-sm transition-colors"
            style={{ color: 'var(--text-secondary)' }}
          >
            Anuluj
          </button>
          <button
            onClick={handleUpload}
            disabled={!file || isUploading}
            className="flex items-center gap-2 rounded-md px-4 py-1.5 text-sm font-medium transition-colors disabled:opacity-50"
            style={{ backgroundColor: 'var(--accent)', color: '#fff' }}
          >
            {isUploading && <Loader2 size={14} className="animate-spin" />}
            Wgraj
          </button>
        </div>
      </div>
    </div>
  );
}
