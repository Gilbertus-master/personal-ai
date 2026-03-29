'use client';

import { cn } from '../../lib/utils';

// ── Types ────────────────────────────────────────────────────────────────────

export type BadgeType =
  | 'priority'
  | 'status'
  | 'phase'
  | 'risk'
  | 'area'
  | 'compliance'
  | 'doc_status'
  | 'signature'
  | 'training'
  | 'matter_type'
  | 'obligation_type'
  | 'deadline';

export interface ComplianceBadgeProps {
  type: BadgeType;
  value: string;
  size?: 'sm' | 'md';
}

// ── Color Maps ───────────────────────────────────────────────────────────────

const PRIORITY_COLORS: Record<string, string> = {
  critical: 'bg-red-500/15 text-red-400',
  high: 'bg-orange-500/15 text-orange-400',
  medium: 'bg-yellow-500/15 text-yellow-400',
  low: 'bg-green-500/15 text-green-400',
};

const COMPLIANCE_COLORS: Record<string, string> = {
  compliant: 'bg-green-500/15 text-green-400',
  partially_compliant: 'bg-yellow-500/15 text-yellow-400',
  non_compliant: 'bg-red-500/15 text-red-400',
  not_applicable: 'bg-gray-500/10 text-gray-400',
  unknown: 'bg-gray-500/10 text-gray-400',
};

const RISK_COLORS: Record<string, string> = {
  green: 'bg-green-500/15 text-green-400',
  yellow: 'bg-yellow-500/15 text-yellow-400',
  orange: 'bg-orange-500/15 text-orange-400',
  red: 'bg-red-500/15 text-red-400',
  critical: 'bg-red-600/20 text-red-300',
  low: 'bg-green-500/15 text-green-400',
  medium: 'bg-yellow-500/15 text-yellow-400',
  high: 'bg-orange-500/15 text-orange-400',
};

const AREA_COLORS: Record<string, string> = {
  URE: 'bg-blue-500/15 text-blue-400',
  RODO: 'bg-purple-500/15 text-purple-400',
  AML: 'bg-red-500/15 text-red-400',
  KSH: 'bg-cyan-500/15 text-cyan-400',
  ESG: 'bg-green-500/15 text-green-400',
  LABOR: 'bg-amber-500/15 text-amber-400',
  TAX: 'bg-indigo-500/15 text-indigo-400',
  CONTRACT: 'bg-teal-500/15 text-teal-400',
  INTERNAL_AUDIT: 'bg-gray-500/15 text-gray-400',
};

const STATUS_COLORS: Record<string, string> = {
  open: 'bg-blue-500/15 text-blue-400',
  researching: 'bg-purple-500/15 text-purple-400',
  analyzed: 'bg-cyan-500/15 text-cyan-400',
  action_plan_ready: 'bg-yellow-500/15 text-yellow-400',
  in_progress: 'bg-orange-500/15 text-orange-400',
  review: 'bg-indigo-500/15 text-indigo-400',
  completed: 'bg-green-500/15 text-green-400',
  closed: 'bg-gray-500/10 text-gray-400',
  on_hold: 'bg-gray-500/10 text-gray-400',
};

const PHASE_COLORS: Record<string, string> = {
  initiation: 'bg-blue-500/15 text-blue-400',
  research: 'bg-blue-400/15 text-blue-300',
  analysis: 'bg-cyan-500/15 text-cyan-400',
  planning: 'bg-yellow-500/15 text-yellow-400',
  document_generation: 'bg-yellow-400/15 text-yellow-300',
  approval: 'bg-orange-500/15 text-orange-400',
  training: 'bg-amber-500/15 text-amber-400',
  communication: 'bg-indigo-500/15 text-indigo-400',
  verification: 'bg-green-400/15 text-green-300',
  monitoring: 'bg-green-500/15 text-green-400',
  closed: 'bg-gray-500/10 text-gray-400',
};

const DOC_STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-500/10 text-gray-400',
  review: 'bg-yellow-500/15 text-yellow-400',
  approved: 'bg-green-500/15 text-green-400',
  active: 'bg-blue-500/15 text-blue-400',
  superseded: 'bg-gray-500/10 text-gray-400',
  expired: 'bg-red-500/15 text-red-400',
  archived: 'bg-gray-500/10 text-gray-400',
};

const SIGNATURE_COLORS: Record<string, string> = {
  not_required: 'bg-gray-500/10 text-gray-400',
  pending: 'bg-yellow-500/15 text-yellow-400',
  partially_signed: 'bg-orange-500/15 text-orange-400',
  signed: 'bg-green-500/15 text-green-400',
  expired: 'bg-red-500/15 text-red-400',
};

const TRAINING_COLORS: Record<string, string> = {
  planned: 'bg-gray-500/10 text-gray-400',
  material_ready: 'bg-blue-500/15 text-blue-400',
  scheduled: 'bg-cyan-500/15 text-cyan-400',
  in_progress: 'bg-yellow-500/15 text-yellow-400',
  completed: 'bg-green-500/15 text-green-400',
  cancelled: 'bg-red-500/15 text-red-400',
};

const DEADLINE_COLORS: Record<string, string> = {
  pending: 'bg-yellow-500/15 text-yellow-400',
  in_progress: 'bg-blue-500/15 text-blue-400',
  completed: 'bg-green-500/15 text-green-400',
  overdue: 'bg-red-500/15 text-red-400',
  cancelled: 'bg-gray-500/10 text-gray-400',
};

const COLOR_MAP: Record<BadgeType, Record<string, string>> = {
  priority: PRIORITY_COLORS,
  status: STATUS_COLORS,
  phase: PHASE_COLORS,
  risk: RISK_COLORS,
  area: AREA_COLORS,
  compliance: COMPLIANCE_COLORS,
  doc_status: DOC_STATUS_COLORS,
  signature: SIGNATURE_COLORS,
  training: TRAINING_COLORS,
  matter_type: PRIORITY_COLORS, // fallback — matter types use neutral styling
  obligation_type: PRIORITY_COLORS, // fallback
  deadline: DEADLINE_COLORS,
};

// ── Label Maps (Polish) ─────────────────────────────────────────────────────

const PRIORITY_LABELS: Record<string, string> = {
  critical: 'Krytyczny',
  high: 'Wysoki',
  medium: 'Średni',
  low: 'Niski',
};

const COMPLIANCE_LABELS: Record<string, string> = {
  compliant: 'Zgodny',
  partially_compliant: 'Częściowo zgodny',
  non_compliant: 'Niezgodny',
  not_applicable: 'Nie dotyczy',
  unknown: 'Nieznany',
};

const STATUS_LABELS: Record<string, string> = {
  open: 'Otwarty',
  researching: 'Badanie',
  analyzed: 'Przeanalizowany',
  action_plan_ready: 'Plan działania',
  in_progress: 'W toku',
  review: 'Przegląd',
  completed: 'Zakończony',
  closed: 'Zamknięty',
  on_hold: 'Wstrzymany',
};

const PHASE_LABELS: Record<string, string> = {
  initiation: 'Inicjacja',
  research: 'Badanie',
  analysis: 'Analiza',
  planning: 'Planowanie',
  document_generation: 'Dokumenty',
  approval: 'Zatwierdzenie',
  training: 'Szkolenie',
  communication: 'Komunikacja',
  verification: 'Weryfikacja',
  monitoring: 'Monitoring',
  closed: 'Zamknięta',
};

const AREA_LABELS: Record<string, string> = {
  URE: 'URE',
  RODO: 'RODO',
  AML: 'AML',
  KSH: 'KSH',
  ESG: 'ESG',
  LABOR: 'Prawo pracy',
  TAX: 'Podatki',
  CONTRACT: 'Umowy',
  INTERNAL_AUDIT: 'Audyt',
};

const DOC_STATUS_LABELS: Record<string, string> = {
  draft: 'Szkic',
  review: 'Przegląd',
  approved: 'Zatwierdzony',
  active: 'Aktywny',
  superseded: 'Zastąpiony',
  expired: 'Wygasły',
  archived: 'Zarchiwizowany',
};

const SIGNATURE_LABELS: Record<string, string> = {
  not_required: 'Nie wymaga',
  pending: 'Oczekuje',
  partially_signed: 'Częściowo',
  signed: 'Podpisany',
  expired: 'Wygasły',
};

const TRAINING_LABELS: Record<string, string> = {
  planned: 'Planowane',
  material_ready: 'Materiały gotowe',
  scheduled: 'Zaplanowane',
  in_progress: 'W toku',
  completed: 'Ukończone',
  cancelled: 'Anulowane',
};

const MATTER_TYPE_LABELS: Record<string, string> = {
  new_regulation: 'Nowa regulacja',
  regulation_change: 'Zmiana regulacji',
  audit_finding: 'Wynik audytu',
  incident: 'Incydent',
  license_renewal: 'Odnowienie licencji',
  contract_review: 'Przegląd umowy',
  policy_update: 'Aktualizacja polityki',
  training_need: 'Potrzeba szkolenia',
  complaint: 'Skarga',
  inspection: 'Kontrola',
  risk_assessment: 'Ocena ryzyka',
  other: 'Inne',
};

const OBLIGATION_TYPE_LABELS: Record<string, string> = {
  reporting: 'Raportowanie',
  licensing: 'Licencjonowanie',
  documentation: 'Dokumentacja',
  training: 'Szkolenie',
  audit: 'Audyt',
  notification: 'Powiadomienie',
  registration: 'Rejestracja',
  inspection: 'Kontrola',
  filing: 'Zgłoszenie',
  other: 'Inne',
};

const DEADLINE_LABELS: Record<string, string> = {
  pending: 'Oczekuje',
  in_progress: 'W toku',
  completed: 'Zakończony',
  overdue: 'Zaległy',
  cancelled: 'Anulowany',
};

const RISK_LABELS: Record<string, string> = {
  green: 'Niski',
  yellow: 'Średni',
  orange: 'Podwyższony',
  red: 'Wysoki',
  critical: 'Krytyczny',
  low: 'Niski',
  medium: 'Średni',
  high: 'Wysoki',
};

const LABEL_MAP: Record<BadgeType, Record<string, string>> = {
  priority: PRIORITY_LABELS,
  status: STATUS_LABELS,
  phase: PHASE_LABELS,
  risk: RISK_LABELS,
  area: AREA_LABELS,
  compliance: COMPLIANCE_LABELS,
  doc_status: DOC_STATUS_LABELS,
  signature: SIGNATURE_LABELS,
  training: TRAINING_LABELS,
  matter_type: MATTER_TYPE_LABELS,
  obligation_type: OBLIGATION_TYPE_LABELS,
  deadline: DEADLINE_LABELS,
};

// ── Component ────────────────────────────────────────────────────────────────

export function ComplianceBadge({ type, value, size = 'sm' }: ComplianceBadgeProps) {
  const colors = COLOR_MAP[type]?.[value] ?? 'bg-gray-500/10 text-gray-400';
  const label = LABEL_MAP[type]?.[value] ?? value;

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full font-medium',
        size === 'sm' && 'px-2 py-0.5 text-xs',
        size === 'md' && 'px-2.5 py-1 text-sm',
        colors,
      )}
    >
      {label}
    </span>
  );
}
