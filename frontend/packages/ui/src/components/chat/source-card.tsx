'use client';

import {
  Mail,
  Users,
  MessageCircle,
  FileText,
  Mic,
  Calendar,
  Bot,
  File,
} from 'lucide-react';

export interface SourceItem {
  document_id: number;
  title: string;
  source_type: string;
  source_name: string;
  created_at: string;
}

interface SourceCardProps {
  source: SourceItem;
}

const sourceIcons: Record<string, React.ElementType> = {
  email: Mail,
  teams: Users,
  whatsapp: MessageCircle,
  whatsapp_live: MessageCircle,
  document: FileText,
  plaud: Mic,
  calendar: Calendar,
  chatgpt: Bot,
  pdf: FileText,
};

function formatDate(dateStr: string): string {
  try {
    const date = new Date(dateStr);
    return date.toLocaleDateString('pl-PL', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    });
  } catch {
    return dateStr;
  }
}

export function SourceCard({ source }: SourceCardProps) {
  const Icon = sourceIcons[source.source_type] ?? File;

  return (
    <div className="flex items-start gap-3 p-3 bg-[var(--surface)] border border-[var(--border)] rounded-lg hover:bg-[var(--surface-hover)] transition-colors">
      <div className="shrink-0 mt-0.5 text-[var(--text-secondary)]">
        <Icon size={18} />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-[var(--text)] truncate">
          {source.title}
        </p>
        <p className="text-xs text-[var(--text-secondary)] truncate">
          {source.source_name}
        </p>
        <p className="text-xs text-[var(--text-secondary)] mt-1">
          {formatDate(source.created_at)}
        </p>
      </div>
    </div>
  );
}
