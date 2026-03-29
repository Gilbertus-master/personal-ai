"""
Legal & Compliance Orchestrator — zarządzanie obowiązkami prawnymi,
dokumentami compliance, terminami, szkoleniami, komunikacją i audytem.

Moduł obsługuje 9 obszarów compliance: URE, RODO, AML, KSH, ESG, LABOR, TAX, CONTRACT, INTERNAL_AUDIT.
Każda sprawa (matter) przechodzi 10 faz: initiation → research → analysis → planning →
document_generation → approval → training → communication → verification → monitoring.

Crony: daily 6:15, regulatory scan 6h, weekly Sun 19:00, monthly 1st 8:00, training Mon-Fri 9:00
"""
from __future__ import annotations

import structlog
log = structlog.get_logger(__name__)

import json
import os
from datetime import date
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection
from app.db.cost_tracker import log_anthropic_cost

load_dotenv()

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
ANTHROPIC_FAST = os.getenv("ANTHROPIC_FAST_MODEL", "claude-haiku-4-5")
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=120.0)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def _ensure_tables() -> None:
    """Create all compliance tables if they don't exist."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS compliance_areas (
                    id BIGSERIAL PRIMARY KEY,
                    code TEXT NOT NULL UNIQUE,
                    name_pl TEXT NOT NULL,
                    name_en TEXT,
                    description TEXT,
                    governing_body TEXT,
                    key_regulations JSONB DEFAULT '[]',
                    responsible_person_id INT,
                    risk_level TEXT DEFAULT 'medium' CHECK (risk_level IN ('low','medium','high','critical')),
                    review_frequency_days INT DEFAULT 90,
                    last_reviewed_at TIMESTAMPTZ,
                    status TEXT DEFAULT 'active' CHECK (status IN ('active','inactive','pending_review')),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS compliance_obligations (
                    id BIGSERIAL PRIMARY KEY,
                    area_id BIGINT NOT NULL REFERENCES compliance_areas(id),
                    title TEXT NOT NULL,
                    description TEXT,
                    legal_basis TEXT,
                    obligation_type TEXT NOT NULL CHECK (obligation_type IN (
                        'reporting','licensing','documentation','training','audit',
                        'notification','registration','inspection','filing','other'
                    )),
                    frequency TEXT CHECK (frequency IN (
                        'one_time','daily','weekly','monthly','quarterly',
                        'semi_annual','annual','biennial','on_change','on_demand'
                    )),
                    deadline_rule TEXT,
                    next_deadline DATE,
                    penalty_description TEXT,
                    penalty_max_pln NUMERIC,
                    applies_to TEXT[] DEFAULT '{}',
                    responsible_role TEXT,
                    responsible_person_id INT,
                    required_documents TEXT[],
                    status TEXT DEFAULT 'active' CHECK (status IN (
                        'active','compliant','non_compliant','waived','pending_review','expired'
                    )),
                    compliance_status TEXT DEFAULT 'unknown' CHECK (compliance_status IN (
                        'compliant','partially_compliant','non_compliant','unknown','not_applicable'
                    )),
                    last_fulfilled_at TIMESTAMPTZ,
                    evidence_chunk_ids BIGINT[],
                    risk_score NUMERIC(3,2),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_co_area ON compliance_obligations(area_id);
                CREATE INDEX IF NOT EXISTS idx_co_deadline ON compliance_obligations(next_deadline) WHERE status = 'active';
                CREATE INDEX IF NOT EXISTS idx_co_compliance ON compliance_obligations(compliance_status);

                CREATE TABLE IF NOT EXISTS compliance_matters (
                    id BIGSERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    matter_type TEXT NOT NULL CHECK (matter_type IN (
                        'new_regulation','regulation_change','audit_finding','incident',
                        'license_renewal','contract_review','policy_update','training_need',
                        'complaint','inspection','risk_assessment','other'
                    )),
                    area_id BIGINT REFERENCES compliance_areas(id),
                    priority TEXT DEFAULT 'medium' CHECK (priority IN ('low','medium','high','critical')),
                    description TEXT,
                    legal_analysis TEXT,
                    risk_analysis JSONB,
                    obligations_report TEXT,
                    consequences_report TEXT,
                    action_plan JSONB DEFAULT '[]',
                    communication_plan JSONB DEFAULT '[]',
                    source_regulation TEXT,
                    source_chunk_ids BIGINT[],
                    contract_id BIGINT,
                    initiated_by TEXT DEFAULT 'gilbertus',
                    status TEXT DEFAULT 'open' CHECK (status IN (
                        'open','researching','analyzed','action_plan_ready',
                        'in_progress','review','completed','closed','on_hold'
                    )),
                    phase TEXT DEFAULT 'initiation' CHECK (phase IN (
                        'initiation','research','analysis','planning',
                        'document_generation','approval','training',
                        'communication','verification','monitoring','closed'
                    )),
                    completed_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_cm_status ON compliance_matters(status);
                CREATE INDEX IF NOT EXISTS idx_cm_area ON compliance_matters(area_id);
                CREATE INDEX IF NOT EXISTS idx_cm_phase ON compliance_matters(phase);

                CREATE TABLE IF NOT EXISTS compliance_documents (
                    id BIGSERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    doc_type TEXT NOT NULL CHECK (doc_type IN (
                        'policy','procedure','form','template','register',
                        'report','certificate','license','contract_annex',
                        'training_material','communication','regulation_text',
                        'internal_regulation','risk_assessment','audit_report','other'
                    )),
                    area_id BIGINT REFERENCES compliance_areas(id),
                    matter_id BIGINT REFERENCES compliance_matters(id),
                    obligation_id BIGINT REFERENCES compliance_obligations(id),
                    version INT DEFAULT 1,
                    content_text TEXT,
                    content_html TEXT,
                    file_path TEXT,
                    generated_by TEXT DEFAULT 'ai',
                    approved_by TEXT,
                    approved_at TIMESTAMPTZ,
                    valid_from DATE,
                    valid_until DATE,
                    review_due DATE,
                    requires_signature BOOLEAN DEFAULT FALSE,
                    signature_status TEXT DEFAULT 'not_required' CHECK (signature_status IN (
                        'not_required','pending','partially_signed','signed','expired'
                    )),
                    signers JSONB DEFAULT '[]',
                    status TEXT DEFAULT 'draft' CHECK (status IN (
                        'draft','review','approved','active','superseded','expired','archived'
                    )),
                    tags TEXT[] DEFAULT '{}',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_cdoc_area ON compliance_documents(area_id);
                CREATE INDEX IF NOT EXISTS idx_cdoc_review ON compliance_documents(review_due) WHERE status = 'active';
                CREATE INDEX IF NOT EXISTS idx_cdoc_status ON compliance_documents(status);

                CREATE TABLE IF NOT EXISTS compliance_deadlines (
                    id BIGSERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    deadline_date DATE NOT NULL,
                    deadline_type TEXT NOT NULL CHECK (deadline_type IN (
                        'filing','reporting','license_renewal','audit','training',
                        'review','inspection','payment','document_expiry','contract','custom'
                    )),
                    area_id BIGINT REFERENCES compliance_areas(id),
                    obligation_id BIGINT REFERENCES compliance_obligations(id),
                    matter_id BIGINT REFERENCES compliance_matters(id),
                    document_id BIGINT REFERENCES compliance_documents(id),
                    responsible_person_id INT,
                    reminder_days INT[] DEFAULT '{30,14,7,3,1}',
                    last_reminder_sent DATE,
                    recurrence TEXT DEFAULT 'none' CHECK (recurrence IN (
                        'none','monthly','quarterly','semi_annual','annual'
                    )),
                    status TEXT DEFAULT 'pending' CHECK (status IN (
                        'pending','in_progress','completed','overdue','cancelled'
                    )),
                    completed_at TIMESTAMPTZ,
                    notes TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_cdl_date ON compliance_deadlines(deadline_date) WHERE status IN ('pending','in_progress');
                CREATE INDEX IF NOT EXISTS idx_cdl_status ON compliance_deadlines(status);

                CREATE TABLE IF NOT EXISTS compliance_trainings (
                    id BIGSERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    area_id BIGINT REFERENCES compliance_areas(id),
                    matter_id BIGINT REFERENCES compliance_matters(id),
                    training_type TEXT DEFAULT 'mandatory' CHECK (training_type IN (
                        'mandatory','awareness','certification','refresher','onboarding'
                    )),
                    content_summary TEXT,
                    content_document_id BIGINT REFERENCES compliance_documents(id),
                    target_audience TEXT[],
                    deadline DATE,
                    status TEXT DEFAULT 'planned' CHECK (status IN (
                        'planned','material_ready','scheduled','in_progress','completed','cancelled'
                    )),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS compliance_training_records (
                    id BIGSERIAL PRIMARY KEY,
                    training_id BIGINT NOT NULL REFERENCES compliance_trainings(id),
                    person_id INT NOT NULL,
                    status TEXT DEFAULT 'assigned' CHECK (status IN (
                        'assigned','notified','started','completed','overdue','exempted'
                    )),
                    notified_at TIMESTAMPTZ,
                    completed_at TIMESTAMPTZ,
                    score NUMERIC,
                    delegation_task_id BIGINT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_ctr_training ON compliance_training_records(training_id);
                CREATE INDEX IF NOT EXISTS idx_ctr_person ON compliance_training_records(person_id);

                CREATE TABLE IF NOT EXISTS compliance_raci (
                    id BIGSERIAL PRIMARY KEY,
                    area_id BIGINT REFERENCES compliance_areas(id),
                    matter_id BIGINT REFERENCES compliance_matters(id),
                    obligation_id BIGINT REFERENCES compliance_obligations(id),
                    person_id INT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('responsible','accountable','consulted','informed')),
                    notes TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(area_id, matter_id, obligation_id, person_id, role)
                );

                CREATE TABLE IF NOT EXISTS compliance_risk_assessments (
                    id BIGSERIAL PRIMARY KEY,
                    area_id BIGINT REFERENCES compliance_areas(id),
                    matter_id BIGINT REFERENCES compliance_matters(id),
                    risk_title TEXT NOT NULL,
                    risk_description TEXT,
                    likelihood TEXT CHECK (likelihood IN ('very_low','low','medium','high','very_high')),
                    impact TEXT CHECK (impact IN ('negligible','minor','moderate','major','catastrophic')),
                    risk_score NUMERIC(3,2),
                    current_controls TEXT,
                    residual_risk TEXT,
                    mitigation_plan TEXT,
                    risk_owner_person_id INT,
                    status TEXT DEFAULT 'open' CHECK (status IN ('open','mitigated','accepted','closed')),
                    review_date DATE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS compliance_audit_evidence (
                    id BIGSERIAL PRIMARY KEY,
                    obligation_id BIGINT REFERENCES compliance_obligations(id),
                    matter_id BIGINT REFERENCES compliance_matters(id),
                    evidence_type TEXT CHECK (evidence_type IN (
                        'document','screenshot','email','report','certificate',
                        'training_record','signature','system_log','other'
                    )),
                    title TEXT NOT NULL,
                    description TEXT,
                    document_id BIGINT REFERENCES compliance_documents(id),
                    chunk_id BIGINT,
                    file_path TEXT,
                    verified_at TIMESTAMPTZ,
                    verified_by TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS compliance_communications (
                    id BIGSERIAL PRIMARY KEY,
                    matter_id BIGINT REFERENCES compliance_matters(id),
                    recipient_person_id INT,
                    recipient_name TEXT,
                    recipient_role TEXT CHECK (recipient_role IN ('responsible','accountable','consulted','informed')),
                    channel TEXT NOT NULL CHECK (channel IN ('email','teams','whatsapp')),
                    subject TEXT,
                    content TEXT NOT NULL,
                    purpose TEXT CHECK (purpose IN ('inform','request_action','request_signature','train')),
                    scheduled_date DATE,
                    status TEXT NOT NULL DEFAULT 'planned' CHECK (status IN ('planned','sent','failed','pending_approval','cancelled')),
                    sent_communication_id BIGINT,
                    sent_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_cc_matter ON compliance_communications(matter_id);
                CREATE INDEX IF NOT EXISTS idx_cc_status ON compliance_communications(status);
            """)
        conn.commit()
    log.debug("compliance_tables_ensured")


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

AREAS = [
    ("URE", "Prawo energetyczne (URE)", "Energy Law (URE)",
     "Koncesje, raporty, obowiązki wobec URE i TGE",
     "URE", '[{"name":"Prawo energetyczne","ref":"Dz.U.2024.266"},{"name":"Rozporządzenie ws. koncesji","ref":"Dz.U.2023.1234"}]',
     "high"),
    ("RODO", "Ochrona danych osobowych (RODO/GDPR)", "Data Protection (GDPR)",
     "Przetwarzanie danych osobowych, rejestry, DPIA, IOD",
     "UODO", '[{"name":"RODO","ref":"EU 2016/679"},{"name":"Ustawa o ochronie danych osobowych","ref":"Dz.U.2019.1781"}]',
     "high"),
    ("AML", "Przeciwdziałanie praniu pieniędzy (AML)", "Anti-Money Laundering",
     "KYC, transakcje podejrzane, raportowanie do GIIF",
     "GIIF", '[{"name":"Ustawa AML","ref":"Dz.U.2023.1124"}]',
     "high"),
    ("KSH", "Kodeks Spółek Handlowych", "Commercial Companies Code",
     "Organy spółki, uchwały, protokoły, KRS, sprawozdania",
     "KRS", '[{"name":"KSH","ref":"Dz.U.2024.18"}]',
     "medium"),
    ("ESG", "Raportowanie ESG/CSRD", "ESG/CSRD Reporting",
     "Raportowanie zrównoważonego rozwoju wg ESRS, od 2025",
     "KNF", '[{"name":"Dyrektywa CSRD","ref":"EU 2022/2464"},{"name":"ESRS","ref":"EU 2023/2772"}]',
     "high"),
    ("LABOR", "Prawo pracy", "Labor Law",
     "Kodeks pracy, BHP, regulamin pracy, ZFŚS",
     "PIP", '[{"name":"Kodeks pracy","ref":"Dz.U.2023.1465"}]',
     "medium"),
    ("TAX", "Prawo podatkowe", "Tax Law",
     "CIT, VAT, PIT, ceny transferowe, JPK, raportowanie",
     "KAS", '[{"name":"Ordynacja podatkowa","ref":"Dz.U.2023.2383"},{"name":"Ustawa CIT","ref":"Dz.U.2023.2805"}]',
     "medium"),
    ("CONTRACT", "Zarządzanie umowami", "Contract Management",
     "Przegląd umów, terminy, odnowienia, klauzule compliance",
     None, '[]',
     "medium"),
    ("INTERNAL_AUDIT", "Audyt wewnętrzny", "Internal Audit",
     "Kontrole wewnętrzne, procedury, polityki, continuous improvement",
     None, '[]',
     "low"),
]


def _seed_compliance_areas() -> None:
    """Seed the 9 compliance areas (idempotent)."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            for code, name_pl, name_en, desc, body, regs, risk in AREAS:
                cur.execute("""
                    INSERT INTO compliance_areas
                        (code, name_pl, name_en, description, governing_body, key_regulations, risk_level)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
                    ON CONFLICT (code) DO NOTHING
                """, (code, name_pl, name_en, desc, body, regs, risk))
        conn.commit()
    log.debug("compliance_areas_seeded", count=len(AREAS))


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def create_matter(
    title: str,
    matter_type: str,
    area_code: str | None = None,
    description: str | None = None,
    priority: str = "medium",
    contract_id: int | None = None,
    source_regulation: str | None = None,
) -> dict[str, Any]:
    """Create a new compliance matter. Returns dict with id, title, status, phase."""
    _ensure_tables()
    _seed_compliance_areas()

    area_id = None
    if area_code:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM compliance_areas WHERE code = %s", (area_code.upper(),))
                row = cur.fetchone()
                if row:
                    area_id = row[0]

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO compliance_matters
                    (title, matter_type, area_id, priority, description,
                     contract_id, source_regulation)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, title, status, phase, created_at
            """, (title, matter_type, area_id, priority, description,
                  contract_id, source_regulation))
            row = cur.fetchone()
        conn.commit()

    log.info("compliance_matter_created", matter_id=row[0], title=title, area=area_code)
    return {
        "id": row[0],
        "title": row[1],
        "status": row[2],
        "phase": row[3],
        "created_at": str(row[4]),
    }


def list_matters(
    status: str | None = None,
    area_code: str | None = None,
    priority: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """List compliance matters with optional filters."""
    _ensure_tables()
    _seed_compliance_areas()

    conditions = []
    params: list[Any] = []

    if status:
        conditions.append("cm.status = %s")
        params.append(status)
    if area_code:
        conditions.append("ca.code = %s")
        params.append(area_code.upper())
    if priority:
        conditions.append("cm.priority = %s")
        params.append(priority)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    params.append(limit)

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT cm.id, cm.title, cm.matter_type, ca.code as area_code,
                       cm.priority, cm.status, cm.phase, cm.created_at
                FROM compliance_matters cm
                LEFT JOIN compliance_areas ca ON ca.id = cm.area_id
                {where}
                ORDER BY cm.created_at DESC
                LIMIT %s
            """, params)
            rows = cur.fetchall()

    return [
        {
            "id": r[0], "title": r[1], "matter_type": r[2], "area_code": r[3],
            "priority": r[4], "status": r[5], "phase": r[6],
            "created_at": str(r[7]),
        }
        for r in rows
    ]


def get_matter_detail(matter_id: int) -> dict[str, Any]:
    """Full detail for a compliance matter with related documents, deadlines, risks."""
    _ensure_tables()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT cm.id, cm.title, cm.matter_type, ca.code as area_code, ca.name_pl as area_name,
                       cm.priority, cm.description, cm.legal_analysis,
                       cm.risk_analysis, cm.obligations_report, cm.consequences_report,
                       cm.action_plan, cm.communication_plan, cm.source_regulation,
                       cm.status, cm.phase, cm.completed_at, cm.created_at, cm.updated_at
                FROM compliance_matters cm
                LEFT JOIN compliance_areas ca ON ca.id = cm.area_id
                WHERE cm.id = %s
            """, (matter_id,))
            row = cur.fetchone()
            if not row:
                return {"error": "matter_not_found", "matter_id": matter_id}

            matter = {
                "id": row[0], "title": row[1], "matter_type": row[2],
                "area_code": row[3], "area_name": row[4],
                "priority": row[5], "description": row[6],
                "legal_analysis": row[7], "risk_analysis": row[8],
                "obligations_report": row[9], "consequences_report": row[10],
                "action_plan": row[11], "communication_plan": row[12],
                "source_regulation": row[13], "status": row[14],
                "phase": row[15],
                "completed_at": str(row[16]) if row[16] else None,
                "created_at": str(row[17]), "updated_at": str(row[18]),
            }

            # Related documents
            cur.execute("""
                SELECT id, title, doc_type, status, version, created_at
                FROM compliance_documents WHERE matter_id = %s
                ORDER BY created_at DESC
            """, (matter_id,))
            matter["documents"] = [
                {"id": r[0], "title": r[1], "doc_type": r[2], "status": r[3],
                 "version": r[4], "created_at": str(r[5])}
                for r in cur.fetchall()
            ]

            # Related deadlines
            cur.execute("""
                SELECT id, title, deadline_date, deadline_type, status
                FROM compliance_deadlines WHERE matter_id = %s
                ORDER BY deadline_date ASC
            """, (matter_id,))
            matter["deadlines"] = [
                {"id": r[0], "title": r[1], "deadline_date": str(r[2]),
                 "deadline_type": r[3], "status": r[4]}
                for r in cur.fetchall()
            ]

            # Related risks
            cur.execute("""
                SELECT id, risk_title, likelihood, impact, risk_score, status
                FROM compliance_risk_assessments WHERE matter_id = %s
                ORDER BY risk_score DESC NULLS LAST
            """, (matter_id,))
            matter["risks"] = [
                {"id": r[0], "risk_title": r[1], "likelihood": r[2], "impact": r[3],
                 "risk_score": float(r[4]) if r[4] else None, "status": r[5]}
                for r in cur.fetchall()
            ]

    return matter


def get_compliance_dashboard() -> dict[str, Any]:
    """Dashboard: areas summary, open matters, upcoming deadlines, overdue, doc freshness, risk heatmap."""
    _ensure_tables()
    _seed_compliance_areas()

    dashboard: dict[str, Any] = {}

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Areas summary
            cur.execute("""
                SELECT ca.code, ca.name_pl, ca.risk_level, ca.status,
                       COUNT(DISTINCT co.id) FILTER (WHERE co.status = 'active') as obligations_count,
                       COUNT(DISTINCT cm.id) FILTER (WHERE cm.status NOT IN ('completed','closed')) as open_matters
                FROM compliance_areas ca
                LEFT JOIN compliance_obligations co ON co.area_id = ca.id
                LEFT JOIN compliance_matters cm ON cm.area_id = ca.id
                GROUP BY ca.id, ca.code, ca.name_pl, ca.risk_level, ca.status
                ORDER BY ca.code
            """)
            dashboard["areas"] = [
                {"code": r[0], "name_pl": r[1], "risk_level": r[2], "status": r[3],
                 "obligations_count": r[4], "open_matters": r[5]}
                for r in cur.fetchall()
            ]

            # Open matters by status
            cur.execute("""
                SELECT status, COUNT(*) FROM compliance_matters
                WHERE status NOT IN ('completed','closed')
                GROUP BY status ORDER BY COUNT(*) DESC
            """)
            dashboard["open_matters"] = {r[0]: r[1] for r in cur.fetchall()}

            # Upcoming deadlines (next 30 days)
            cur.execute("""
                SELECT cd.id, cd.title, cd.deadline_date, cd.deadline_type, ca.code as area_code, cd.status
                FROM compliance_deadlines cd
                LEFT JOIN compliance_areas ca ON ca.id = cd.area_id
                WHERE cd.deadline_date <= CURRENT_DATE + 30
                  AND cd.status IN ('pending','in_progress')
                ORDER BY cd.deadline_date ASC
                LIMIT 20
            """)
            dashboard["upcoming_deadlines"] = [
                {"id": r[0], "title": r[1], "deadline_date": str(r[2]),
                 "deadline_type": r[3], "area_code": r[4], "status": r[5]}
                for r in cur.fetchall()
            ]

            # Overdue count
            cur.execute("""
                SELECT COUNT(*) FROM compliance_deadlines
                WHERE deadline_date < CURRENT_DATE AND status IN ('pending','in_progress')
            """)
            dashboard["overdue_deadlines_count"] = cur.fetchone()[0]

            # Document freshness
            cur.execute("""
                SELECT status, COUNT(*) FROM compliance_documents
                GROUP BY status ORDER BY COUNT(*) DESC
            """)
            dashboard["documents_by_status"] = {r[0]: r[1] for r in cur.fetchall()}

            # Documents needing review
            cur.execute("""
                SELECT COUNT(*) FROM compliance_documents
                WHERE review_due <= CURRENT_DATE AND status = 'active'
            """)
            dashboard["documents_overdue_review"] = cur.fetchone()[0]

            # Risk heatmap
            cur.execute("""
                SELECT likelihood, impact, COUNT(*)
                FROM compliance_risk_assessments
                WHERE status = 'open'
                GROUP BY likelihood, impact
            """)
            dashboard["risk_heatmap"] = [
                {"likelihood": r[0], "impact": r[1], "count": r[2]}
                for r in cur.fetchall()
            ]

            # Total counts
            cur.execute("""
                SELECT
                    (SELECT COUNT(*) FROM compliance_matters) as total_matters,
                    (SELECT COUNT(*) FROM compliance_obligations) as total_obligations,
                    (SELECT COUNT(*) FROM compliance_documents) as total_documents,
                    (SELECT COUNT(*) FROM compliance_trainings) as total_trainings,
                    (SELECT COUNT(*) FROM compliance_risk_assessments WHERE status = 'open') as open_risks
            """)
            row = cur.fetchone()
            dashboard["totals"] = {
                "matters": row[0], "obligations": row[1], "documents": row[2],
                "trainings": row[3], "open_risks": row[4],
            }

    return dashboard


def list_areas() -> list[dict[str, Any]]:
    """List all compliance areas with status."""
    _ensure_tables()
    _seed_compliance_areas()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT ca.id, ca.code, ca.name_pl, ca.name_en, ca.description,
                       ca.governing_body, ca.key_regulations, ca.risk_level,
                       ca.review_frequency_days, ca.last_reviewed_at, ca.status,
                       COUNT(DISTINCT co.id) FILTER (WHERE co.status = 'active') as obligations_count,
                       COUNT(DISTINCT cm.id) FILTER (WHERE cm.status NOT IN ('completed','closed')) as open_matters
                FROM compliance_areas ca
                LEFT JOIN compliance_obligations co ON co.area_id = ca.id
                LEFT JOIN compliance_matters cm ON cm.area_id = ca.id
                GROUP BY ca.id
                ORDER BY ca.code
            """)
            return [
                {
                    "id": r[0], "code": r[1], "name_pl": r[2], "name_en": r[3],
                    "description": r[4], "governing_body": r[5],
                    "key_regulations": r[6], "risk_level": r[7],
                    "review_frequency_days": r[8],
                    "last_reviewed_at": str(r[9]) if r[9] else None,
                    "status": r[10], "obligations_count": r[11], "open_matters": r[12],
                }
                for r in cur.fetchall()
            ]


def get_area_detail(area_code: str) -> dict[str, Any]:
    """Detail for a compliance area with obligations, matters, documents."""
    _ensure_tables()
    _seed_compliance_areas()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, code, name_pl, name_en, description, governing_body,
                       key_regulations, risk_level, review_frequency_days,
                       last_reviewed_at, status, created_at
                FROM compliance_areas WHERE code = %s
            """, (area_code,))
            row = cur.fetchone()
            if not row:
                return {"error": "area_not_found", "code": area_code}

            area = {
                "id": row[0], "code": row[1], "name_pl": row[2], "name_en": row[3],
                "description": row[4], "governing_body": row[5],
                "key_regulations": row[6], "risk_level": row[7],
                "review_frequency_days": row[8],
                "last_reviewed_at": str(row[9]) if row[9] else None,
                "status": row[10], "created_at": str(row[11]),
            }
            area_id = row[0]

            # Obligations
            cur.execute("""
                SELECT id, title, obligation_type, frequency, next_deadline,
                       compliance_status, status, risk_score
                FROM compliance_obligations WHERE area_id = %s
                ORDER BY next_deadline ASC NULLS LAST
            """, (area_id,))
            area["obligations"] = [
                {"id": r[0], "title": r[1], "obligation_type": r[2], "frequency": r[3],
                 "next_deadline": str(r[4]) if r[4] else None,
                 "compliance_status": r[5], "status": r[6],
                 "risk_score": float(r[7]) if r[7] else None}
                for r in cur.fetchall()
            ]

            # Matters
            cur.execute("""
                SELECT id, title, matter_type, priority, status, phase, created_at
                FROM compliance_matters WHERE area_id = %s
                ORDER BY created_at DESC LIMIT 20
            """, (area_id,))
            area["matters"] = [
                {"id": r[0], "title": r[1], "matter_type": r[2], "priority": r[3],
                 "status": r[4], "phase": r[5], "created_at": str(r[6])}
                for r in cur.fetchall()
            ]

            # Documents
            cur.execute("""
                SELECT id, title, doc_type, status, version, valid_until, review_due
                FROM compliance_documents WHERE area_id = %s
                ORDER BY created_at DESC LIMIT 20
            """, (area_id,))
            area["documents"] = [
                {"id": r[0], "title": r[1], "doc_type": r[2], "status": r[3],
                 "version": r[4], "valid_until": str(r[5]) if r[5] else None,
                 "review_due": str(r[6]) if r[6] else None}
                for r in cur.fetchall()
            ]

    return area


# ================================================================
# Obligation & Deadline functions (delegated to obligation_tracker)
# ================================================================

def run_deadline_monitor() -> dict[str, Any]:
    """Cron entry: sprawdź terminy i wyślij przypomnienia."""
    _ensure_tables()
    from app.analysis.legal.obligation_tracker import run_deadline_monitor as _run
    return _run()


def create_obligation(**kwargs) -> dict[str, Any]:
    """Utwórz nowy obowiązek prawny."""
    _ensure_tables()
    _seed_compliance_areas()
    from app.analysis.legal.obligation_tracker import create_obligation as _create
    return _create(**kwargs)


def list_obligations(**kwargs) -> list[dict[str, Any]]:
    _ensure_tables()
    from app.analysis.legal.obligation_tracker import list_obligations as _list
    return _list(**kwargs)


def get_overdue_obligations() -> list[dict[str, Any]]:
    _ensure_tables()
    from app.analysis.legal.obligation_tracker import get_overdue_obligations as _get
    return _get()


def fulfill_obligation(obligation_id: int, evidence_description: str | None = None) -> dict[str, Any]:
    _ensure_tables()
    from app.analysis.legal.obligation_tracker import fulfill_obligation as _fulfill
    return _fulfill(obligation_id, evidence_description)


# ================================================================
# AI Research & Analysis (L3)
# ================================================================

def research_regulation(matter_id: int, query: str | None = None) -> dict[str, Any]:
    """AI-powered research regulacji dla sprawy.

    1. Pobierz matter (title, description, area, source_regulation)
    2. Wyszukaj w Qdrant semantycznie via search_chunks
    3. Zbierz kontekst z chunks
    4. Wywołaj Claude Sonnet z promptem prawnym
    5. Zapisz wynik do matter.legal_analysis
    6. Zaktualizuj matter.phase = 'research', status = 'researching'

    Zwraca: {matter_id, legal_analysis, chunks_used: N, model_used}
    """
    _ensure_tables()

    # 1. Fetch matter
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT cm.id, cm.title, cm.description, cm.source_regulation,
                       ca.code as area_code, ca.name_pl as area_name
                FROM compliance_matters cm
                LEFT JOIN compliance_areas ca ON ca.id = cm.area_id
                WHERE cm.id = %s
            """, (matter_id,))
            row = cur.fetchone()
            if not row:
                return {"error": "matter_not_found", "matter_id": matter_id}

    m_id, title, description, source_regulation, area_code, area_name = row

    # 2. Semantic search in Qdrant
    search_query = query or f"{title} {description or ''} {source_regulation or ''}"
    chunks_used = 0
    context = ""

    try:
        from app.retrieval.retriever import search_chunks
        matches = search_chunks(search_query, top_k=15)
        if matches:
            context_parts = []
            for m in matches:
                src = m.get("source_type", "")
                created = m.get("created_at", "")
                text = m.get("text", "")[:500]
                context_parts.append(f"[{src} {created}] {text}")
            context = "\n\n".join(context_parts)
            chunks_used = len(matches)
    except Exception as e:
        log.warning("research_search_fallback", error=str(e))
        context = "(Brak wyników wyszukiwania semantycznego)"

    # 3-4. AI analysis
    question = query or "Jakie są obowiązki prawne wynikające z tej regulacji?"

    _SYSTEM_RESEARCH = (
        "Jesteś prawnikiem specjalizującym się w polskim prawie energetycznym. "
        "Analizujesz źródła i odpowiadasz na pytania prawne.\n\n"
        "Odpowiedz w strukturze:\n"
        "1. STRESZCZENIE REGULACJI\n"
        "2. OBOWIĄZKI (lista konkretnych obowiązków z podstawą prawną)\n"
        "3. TERMINY (jakie terminy obowiązują)\n"
        "4. KONSEKWENCJE NIEDOPEŁNIENIA (kary, sankcje)\n"
        "5. WYMAGANE DOKUMENTY (jakie dokumenty trzeba przygotować)\n"
        "6. REKOMENDACJE (co należy zrobić)\n\n"
        "Bądź konkretny, podawaj artykuły ustaw. Pisz po polsku."
    )

    prompt = (
        f"SPRAWA: {title}\n"
        f"OPIS: {description or 'brak'}\n"
        f"OBSZAR: {area_name or area_code or 'ogólny'}\n"
        f"REGULACJA ŹRÓDŁOWA: {source_regulation or 'brak'}\n"
        f"PYTANIE: {question}\n\n"
        f"ŹRÓDŁA:\n{context or '(brak źródeł)'}"
    )

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=8000,
            system=[
                {"type": "text", "text": _SYSTEM_RESEARCH, "cache_control": {"type": "ephemeral"}},
            ],
            messages=[{"role": "user", "content": prompt}],
        )
        log_anthropic_cost(ANTHROPIC_MODEL, "legal_research", response.usage)
        if response.stop_reason == "max_tokens":
            log.warning("legal_research_truncated", matter_id=matter_id, stop_reason=response.stop_reason)
        log.info("cache_stats",
                 cache_creation=getattr(response.usage, "cache_creation_input_tokens", 0),
                 cache_read=getattr(response.usage, "cache_read_input_tokens", 0))
        legal_analysis = response.content[0].text.strip()
    except Exception as e:
        log.error("legal_research_ai_error", error=str(e), matter_id=matter_id)
        return {"error": "ai_error", "detail": str(e), "matter_id": matter_id}

    # 5-6. Save results
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE compliance_matters
                SET legal_analysis = %s,
                    phase = 'research',
                    status = 'researching',
                    updated_at = NOW()
                WHERE id = %s
            """, (legal_analysis, matter_id))
        conn.commit()

    log.info("legal_research_completed",
             matter_id=matter_id, chunks_used=chunks_used,
             analysis_length=len(legal_analysis))

    return {
        "matter_id": matter_id,
        "legal_analysis": legal_analysis,
        "chunks_used": chunks_used,
        "model_used": ANTHROPIC_MODEL,
    }


def generate_compliance_report(matter_id: int) -> dict[str, Any]:
    """Generuje pełny raport compliance na bazie legal_analysis.

    1. Pobierz matter z legal_analysis
    2. Wywołaj Claude Sonnet do generacji raportu
    3. Zapisz: matter.obligations_report = raport
    4. Wywołaj assess_risk_for_matter(matter_id) z risk_assessor
    5. Zaktualizuj matter.phase = 'analysis', status = 'analyzed'

    Zwraca: {matter_id, report_length, risks_identified, phase}
    """
    _ensure_tables()

    # 1. Fetch matter
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT cm.id, cm.title, cm.description, cm.legal_analysis,
                       ca.code as area_code, ca.name_pl as area_name
                FROM compliance_matters cm
                LEFT JOIN compliance_areas ca ON ca.id = cm.area_id
                WHERE cm.id = %s
            """, (matter_id,))
            row = cur.fetchone()
            if not row:
                return {"error": "matter_not_found", "matter_id": matter_id}

    m_id, title, description, legal_analysis, area_code, area_name = row

    if not legal_analysis:
        return {
            "error": "no_legal_analysis",
            "matter_id": matter_id,
            "hint": "Run research_regulation() first",
        }

    # 2. Generate report
    _SYSTEM_REPORT = (
        "Generujesz kompletne raporty compliance w formacie markdown, po polsku.\n"
        "Struktura raportu:\n"
        "## I. PODSUMOWANIE WYKONAWCZE\n"
        "## II. OBOWIĄZKI PRAWNE\n"
        "(tabela: obowiązek | podstawa prawna | termin | kara)\n"
        "## III. ANALIZA RYZYK\n"
        "(likelihood × impact)\n"
        "## IV. WYMAGANE DOKUMENTY\n"
        "(lista z opisem)\n"
        "## V. PLAN DZIAŁAŃ\n"
        "(kto | co | kiedy | priorytet)\n"
        "## VI. PLAN KOMUNIKACJI\n"
        "(kogo poinformować | o czym | kanał | kiedy)\n"
        "## VII. SZKOLENIA\n"
        "(kto musi przejść jakie szkolenie)\n"
        "## VIII. REKOMENDACJE\n\n"
        "Format: markdown, po polsku, konkretnie z datami i odpowiedzialnymi. "
        "Jako spółkę przyjmij REH (Respect Energy Holding) — spółka energetyczna, trading."
    )

    prompt = (
        f"# RAPORT COMPLIANCE: {title}\n\n"
        f"SPRAWA: {title}\n"
        f"OPIS: {description or 'brak'}\n"
        f"OBSZAR: {area_name or area_code or 'ogólny'}\n\n"
        f"ANALIZA PRAWNA:\n{legal_analysis[:6000]}"
    )

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=10000,
            system=[
                {"type": "text", "text": _SYSTEM_REPORT, "cache_control": {"type": "ephemeral"}},
            ],
            messages=[{"role": "user", "content": prompt}],
        )
        log_anthropic_cost(ANTHROPIC_MODEL, "compliance_report", response.usage)
        if response.stop_reason == "max_tokens":
            log.warning("compliance_report_truncated", matter_id=matter_id, stop_reason=response.stop_reason)
        log.info("cache_stats",
                 cache_creation=getattr(response.usage, "cache_creation_input_tokens", 0),
                 cache_read=getattr(response.usage, "cache_read_input_tokens", 0))
        report = response.content[0].text.strip()
    except Exception as e:
        log.error("compliance_report_ai_error", error=str(e), matter_id=matter_id)
        return {"error": "ai_error", "detail": str(e), "matter_id": matter_id}

    # 3. Save report
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE compliance_matters
                SET obligations_report = %s,
                    phase = 'analysis',
                    status = 'analyzed',
                    updated_at = NOW()
                WHERE id = %s
            """, (report, matter_id))
        conn.commit()

    # 4. Risk assessment
    risks_identified = 0
    try:
        from app.analysis.legal.risk_assessor import assess_risk_for_matter
        risks = assess_risk_for_matter(matter_id)
        risks_identified = len([r for r in risks if not r.get("error")])
    except Exception as e:
        log.error("compliance_report_risk_error", error=str(e), matter_id=matter_id)

    log.info("compliance_report_generated",
             matter_id=matter_id, report_length=len(report),
             risks_identified=risks_identified)

    return {
        "matter_id": matter_id,
        "report_length": len(report),
        "risks_identified": risks_identified,
        "phase": "analysis",
    }


def advance_matter_phase(matter_id: int, force_phase: str | None = None) -> dict[str, Any]:
    """Przesuwa sprawę do następnej fazy.

    Fazy 1-3:
    - initiation → research: wywołaj research_regulation()
    - research → analysis: wywołaj generate_compliance_report()
    - analysis → planning: (placeholder, L4+ doimplementuje)

    Sprawdza prerequisites i wywołuje odpowiednie funkcje.
    Zwraca: {matter_id, old_phase, new_phase, status}
    """
    _ensure_tables()

    # Fetch current phase
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, phase, status, description, source_regulation,
                       legal_analysis, obligations_report
                FROM compliance_matters WHERE id = %s
            """, (matter_id,))
            row = cur.fetchone()
            if not row:
                return {"error": "matter_not_found", "matter_id": matter_id}

    m_id, current_phase, current_status, description, source_reg, legal_analysis, report = row

    PHASE_ORDER = [
        "initiation", "research", "analysis", "planning",
        "document_generation", "approval", "training",
        "communication", "verification", "monitoring", "closed",
    ]

    target_phase = force_phase
    if not target_phase:
        try:
            idx = PHASE_ORDER.index(current_phase)
            if idx + 1 >= len(PHASE_ORDER):
                return {"error": "already_final_phase", "phase": current_phase}
            target_phase = PHASE_ORDER[idx + 1]
        except ValueError:
            return {"error": "unknown_phase", "phase": current_phase}

    # Prerequisites and actions
    if target_phase == "research":
        if not description and not source_reg:
            return {
                "error": "prerequisite_missing",
                "matter_id": matter_id,
                "hint": "Matter needs description or source_regulation for research",
            }
        result = research_regulation(matter_id)
        if result.get("error"):
            return result
        new_status = "researching"

    elif target_phase == "analysis":
        if not legal_analysis:
            return {
                "error": "prerequisite_missing",
                "matter_id": matter_id,
                "hint": "Run research phase first (legal_analysis is empty)",
            }
        result = generate_compliance_report(matter_id)
        if result.get("error"):
            return result
        new_status = "analyzed"

    elif target_phase == "planning":
        if not report:
            return {
                "error": "prerequisite_missing",
                "matter_id": matter_id,
                "hint": "Run analysis phase first (obligations_report is empty)",
            }
        # Generate action_plan via Claude
        _SYSTEM_PLAN = (
            "Generujesz action_plan jako JSON array na podstawie raportów compliance.\n\n"
            "Wygeneruj JSON array (TYLKO JSON, bez markdown):\n"
            '[{"step": 1, "action": "opis działania", "assignee": "rola/osoba",\n'
            '   "deadline": "YYYY-MM-DD", "document_needed": "policy|procedure|form|none",\n'
            '   "priority": "low|medium|high|critical"}]\n\n'
            "Uwzględnij wszystkie obowiązki z raportu. Deadline'y realistyczne (30-180 dni od dziś)."
        )

        plan_prompt = (
            f"RAPORT COMPLIANCE:\n{report[:3000]}\n\n"
            f"ANALIZA PRAWNA:\n{(legal_analysis or '')[:2000]}\n\n"
            f"Dzisiejsza data: {date.today().isoformat()}"
        )

        resp = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=4000,
            temperature=0.1,
            system=[
                {"type": "text", "text": _SYSTEM_PLAN, "cache_control": {"type": "ephemeral"}},
            ],
            messages=[{"role": "user", "content": plan_prompt}],
        )
        plan_text = resp.content[0].text.strip()
        log_anthropic_cost(ANTHROPIC_MODEL, "legal_action_plan", resp.usage)
        if resp.stop_reason == "max_tokens":
            log.warning("action_plan_truncated", matter_id=matter_id, stop_reason=resp.stop_reason)
        log.info("cache_stats",
                 cache_creation=getattr(resp.usage, "cache_creation_input_tokens", 0),
                 cache_read=getattr(resp.usage, "cache_read_input_tokens", 0))

        # Parse JSON from response
        try:
            # Strip markdown fences if present
            if plan_text.startswith("```"):
                plan_text = plan_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            action_plan = json.loads(plan_text)
        except json.JSONDecodeError:
            log.warning("action_plan_parse_failed", matter_id=matter_id)
            action_plan = []

        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE compliance_matters
                    SET phase = 'planning', status = 'action_plan_ready',
                        action_plan = %s::jsonb, updated_at = NOW()
                    WHERE id = %s
                """, (json.dumps(action_plan), matter_id))
            conn.commit()
        new_status = "action_plan_ready"

    elif target_phase == "document_generation":
        # Fetch action_plan
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT action_plan FROM compliance_matters WHERE id = %s
                """, (matter_id,))
                ap_row = cur.fetchone()
        action_plan = ap_row[0] if ap_row and ap_row[0] else []
        if not action_plan:
            return {
                "error": "prerequisite_missing",
                "matter_id": matter_id,
                "hint": "Run planning phase first (action_plan is empty)",
            }

        # Generate documents for each step that needs one
        from app.analysis.legal.document_generator import generate_document as _gen_doc
        generated = []
        for step in action_plan:
            doc_needed = step.get("document_needed", "none")
            if doc_needed and doc_needed != "none":
                doc_result = _gen_doc(
                    matter_id=matter_id,
                    doc_type=doc_needed,
                    title=step.get("action"),
                )
                generated.append(doc_result)

        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE compliance_matters
                    SET phase = 'document_generation', status = 'in_progress',
                        updated_at = NOW()
                    WHERE id = %s
                """, (matter_id,))
            conn.commit()
        new_status = "in_progress"
        log.info("documents_generated", matter_id=matter_id, count=len(generated))

    elif target_phase == "approval":
        # document_generation → approval: mark as awaiting approval
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE compliance_matters
                    SET phase = 'approval', status = 'review',
                        updated_at = NOW()
                    WHERE id = %s
                """, (matter_id,))
            conn.commit()
        new_status = "review"
        log.info("matter_awaiting_approval", matter_id=matter_id)

    elif target_phase == "training":
        # approval → training: create trainings from action_plan steps that need training
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT action_plan, title FROM compliance_matters WHERE id = %s
                """, (matter_id,))
                row = cur.fetchone()
        action_plan = row[0] if row and row[0] else []
        matter_title = row[1] if row else ""

        # Find steps that mention training/szkolenie
        training_steps = [
            s for s in action_plan
            if any(kw in (s.get("action", "") + s.get("document_needed", "")).lower()
                   for kw in ("training", "szkolenie", "szkoleniow"))
        ]

        created_trainings = []
        if training_steps:
            from app.analysis.legal.training_manager import create_training as _create_training
            # Fetch area_code for matter
            with get_pg_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT a.code FROM compliance_matters m
                        JOIN compliance_areas a ON a.id = m.area_id
                        WHERE m.id = %s
                    """, (matter_id,))
                    arow = cur.fetchone()
            area_code = arow[0] if arow else "INTERNAL_AUDIT"

            for step in training_steps:
                t_result = _create_training(
                    title=step.get("action", f"Szkolenie: {matter_title}"),
                    area_code=area_code,
                    matter_id=matter_id,
                    training_type="mandatory",
                    target_audience=["all_employees"],
                    deadline=step.get("deadline"),
                )
                created_trainings.append(t_result)

        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE compliance_matters
                    SET phase = 'training', status = 'in_progress',
                        updated_at = NOW()
                    WHERE id = %s
                """, (matter_id,))
            conn.commit()
        new_status = "in_progress"
        log.info("matter_training_phase", matter_id=matter_id, trainings_created=len(created_trainings))

    elif target_phase == "communication":
        # training → communication: check if all trainings completed (or none exist)
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) FILTER (WHERE status != 'completed' AND status != 'cancelled') AS pending,
                           COUNT(*) AS total
                    FROM compliance_trainings
                    WHERE matter_id = %s
                """, (matter_id,))
                counts = cur.fetchone()
        pending = counts[0] if counts else 0
        total = counts[1] if counts else 0

        if pending > 0:
            return {
                "error": "prerequisite_missing",
                "matter_id": matter_id,
                "hint": f"Still {pending}/{total} trainings not completed",
            }

        # Execute communication plan
        from app.analysis.legal.communication_planner import execute_communication_plan as _exec_comm
        _exec_comm(matter_id)

        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE compliance_matters
                    SET phase = 'communication', status = 'in_progress',
                        updated_at = NOW()
                    WHERE id = %s
                """, (matter_id,))
            conn.commit()
        new_status = "in_progress"
        log.info("matter_communication_phase", matter_id=matter_id)

    elif target_phase == "verification":
        # communication → verification: check all communications sent
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) FILTER (WHERE status NOT IN ('sent','cancelled')) AS unsent,
                           COUNT(*) AS total
                    FROM compliance_communications
                    WHERE matter_id = %s
                """, (matter_id,))
                counts = cur.fetchone()
        unsent = counts[0] if counts else 0

        if unsent > 0:
            return {
                "error": "prerequisite_missing",
                "matter_id": matter_id,
                "hint": f"Still {unsent} communications not sent",
            }

        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE compliance_matters
                    SET phase = 'verification', status = 'in_progress',
                        updated_at = NOW()
                    WHERE id = %s
                """, (matter_id,))
            conn.commit()
        new_status = "in_progress"
        log.info("matter_verification_phase", matter_id=matter_id)

    elif target_phase == "monitoring":
        # verification → monitoring: check obligations compliant, docs signed, trainings done
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                # Check obligations
                cur.execute("""
                    SELECT COUNT(*) FILTER (WHERE compliance_status NOT IN ('compliant','not_applicable')) AS non_compliant,
                           COUNT(*) AS total
                    FROM compliance_obligations WHERE area_id = (
                        SELECT area_id FROM compliance_matters WHERE id = %s
                    )
                """, (matter_id,))
                obl = cur.fetchone()

                # Check unsigned documents
                cur.execute("""
                    SELECT COUNT(*) FROM compliance_documents
                    WHERE matter_id = %s AND requires_signature = true
                      AND signature_status != 'signed'
                      AND status NOT IN ('superseded','archived')
                """, (matter_id,))
                unsigned = cur.fetchone()[0]

                # Check incomplete trainings
                cur.execute("""
                    SELECT COUNT(*) FROM compliance_trainings
                    WHERE matter_id = %s AND status NOT IN ('completed','cancelled')
                """, (matter_id,))
                incomplete_training = cur.fetchone()[0]

        blockers = []
        if obl and obl[0] > 0:
            blockers.append(f"{obl[0]} obligations not compliant")
        if unsigned > 0:
            blockers.append(f"{unsigned} documents unsigned")
        if incomplete_training > 0:
            blockers.append(f"{incomplete_training} trainings incomplete")

        if blockers:
            return {
                "error": "prerequisite_missing",
                "matter_id": matter_id,
                "hint": "; ".join(blockers),
            }

        # Collect audit evidence summary
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) FROM compliance_audit_evidence WHERE matter_id = %s
                """, (matter_id,))
                evidence_count = cur.fetchone()[0]

                cur.execute("""
                    UPDATE compliance_matters
                    SET phase = 'monitoring', status = 'completed',
                        updated_at = NOW()
                    WHERE id = %s
                """, (matter_id,))
            conn.commit()
        new_status = "completed"
        log.info("matter_monitoring_phase", matter_id=matter_id, evidence=evidence_count)

    elif target_phase == "closed":
        # monitoring → closed: manual close after compliance confirmed
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE compliance_matters
                    SET phase = 'closed', status = 'closed',
                        updated_at = NOW()
                    WHERE id = %s
                """, (matter_id,))
            conn.commit()
        new_status = "closed"
        log.info("matter_closed", matter_id=matter_id)

    else:
        return {
            "error": "unknown_target_phase",
            "target_phase": target_phase,
        }

    log.info("matter_phase_advanced",
             matter_id=matter_id, old_phase=current_phase, new_phase=target_phase)

    return {
        "matter_id": matter_id,
        "old_phase": current_phase,
        "new_phase": target_phase,
        "status": new_status,
    }


# ================================================================
# Document functions (delegated to document_generator)
# ================================================================

def generate_document(matter_id: int, doc_type: str, **kwargs) -> dict[str, Any]:
    _ensure_tables()
    from app.analysis.legal.document_generator import generate_document as _gen
    return _gen(matter_id, doc_type, **kwargs)


def list_documents(**kwargs) -> list[dict[str, Any]]:
    _ensure_tables()
    from app.analysis.legal.document_generator import list_documents as _list
    return _list(**kwargs)


def get_stale_documents(days_overdue: int = 0) -> list[dict[str, Any]]:
    _ensure_tables()
    from app.analysis.legal.document_generator import get_stale_documents as _get
    return _get(days_overdue)


def run_document_freshness_check() -> dict[str, Any]:
    _ensure_tables()
    from app.analysis.legal.document_generator import run_document_freshness_check as _run
    return _run()


# ================================================================
# Training functions (delegated to training_manager)
# ================================================================

def create_training(**kwargs) -> dict[str, Any]:
    _ensure_tables()
    from app.analysis.legal.training_manager import create_training as _create
    return _create(**kwargs)


def list_trainings(**kwargs) -> list[dict[str, Any]]:
    _ensure_tables()
    from app.analysis.legal.training_manager import list_trainings as _list
    return _list(**kwargs)


def get_training_status(training_id: int) -> dict[str, Any]:
    _ensure_tables()
    from app.analysis.legal.training_manager import get_training_status as _get
    return _get(training_id)


# ================================================================
# Communication functions (delegated to communication_planner)
# ================================================================

def generate_communication_plan(matter_id: int) -> dict[str, Any]:
    _ensure_tables()
    from app.analysis.legal.communication_planner import generate_communication_plan as _gen
    return _gen(matter_id)


def execute_communication_plan(matter_id: int) -> dict[str, Any]:
    _ensure_tables()
    from app.analysis.legal.communication_planner import execute_communication_plan as _exec
    return _exec(matter_id)


# ================================================================
# Daily/Weekly compliance check entry points (for cron)
# ================================================================

def run_daily_compliance_check() -> dict[str, Any]:
    """Cron daily: pełna kontrola compliance."""
    _ensure_tables()
    from app.analysis.legal.obligation_tracker import run_deadline_monitor
    from app.analysis.legal.document_generator import run_document_freshness_check
    from app.analysis.legal.compliance_reporter import generate_daily_update
    from app.analysis.legal.training_manager import check_training_deadlines

    deadline_result = run_deadline_monitor()
    freshness_result = run_document_freshness_check()
    training_result = check_training_deadlines()
    contract_result = check_contracts_compliance()
    alert_result = create_compliance_alerts()

    update_msg = generate_daily_update()
    if update_msg:
        try:
            import subprocess
            subprocess.run([os.getenv("OPENCLAW_BIN", "openclaw"), "message", "send",
                          "--channel", "whatsapp", "--target", os.getenv("WA_TARGET", ""),
                          "--message", update_msg], capture_output=True, text=True, timeout=30)
        except Exception:
            pass

    return {
        "deadlines": deadline_result,
        "freshness": freshness_result,
        "trainings": training_result,
        "contracts": contract_result,
        "alerts": alert_result,
        "update_sent": bool(update_msg),
    }


# ================================================================
# Cross-reference contracts ↔ compliance (L8)
# ================================================================

def check_contracts_compliance() -> dict[str, Any]:
    """Sprawdź kontrakty pod kątem compliance.

    1. Pobierz aktywne/expiring kontrakty z contracts table
    2. Dla kontraktów z contract_type zawierającym dane/personal/processing/przetwarzanie:
       - Sprawdź czy istnieje compliance_matter z contract_id = contract.id
       - Jeśli nie → create_matter
    3. Dla kontraktów wygasających w ciągu 30 dni:
       - Sprawdź czy istnieje compliance_deadline dla tego kontraktu
       - Jeśli nie → utwórz deadline
    4. Zwróć: {contracts_checked, matters_created, deadlines_created}
    """
    _ensure_tables()
    _seed_compliance_areas()

    DATA_KEYWORDS = ('dane', 'personal', 'processing', 'przetwarzanie')
    contracts_checked = 0
    matters_created = 0
    deadlines_created = 0

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # 1. Fetch active/expiring contracts
            cur.execute("""
                SELECT id, title, contract_type, end_date
                FROM contracts
                WHERE status IN ('active', 'expiring')
                ORDER BY end_date ASC NULLS LAST
            """)
            contracts = cur.fetchall()

            for c_id, c_title, c_type, c_end_date in contracts:
                contracts_checked += 1

                # 2. Data-related contracts → check for compliance matter
                if c_type and any(kw in c_type.lower() for kw in DATA_KEYWORDS):
                    cur.execute("""
                        SELECT id FROM compliance_matters
                        WHERE contract_id = %s AND status NOT IN ('closed', 'completed')
                    """, (c_id,))
                    if not cur.fetchone():
                        cur.execute("""
                            INSERT INTO compliance_matters
                                (title, matter_type, area_id, priority, description, contract_id)
                            VALUES (
                                %s, 'contract_review',
                                (SELECT id FROM compliance_areas WHERE code = 'RODO'),
                                'medium',
                                %s,
                                %s
                            )
                            RETURNING id
                        """, (
                            f"Przegląd compliance kontraktu: {c_title}",
                            f"Automatyczny przegląd compliance kontraktu '{c_title}' (typ: {c_type})",
                            c_id,
                        ))
                        matters_created += 1
                        log.info("contract_compliance_matter_created",
                                 contract_id=c_id, title=c_title)

                # 3. Contracts expiring within 30 days → deadline
                if c_end_date and (c_end_date - date.today()).days <= 30:
                    cur.execute("""
                        SELECT id FROM compliance_deadlines
                        WHERE title LIKE %s
                          AND deadline_date = %s
                          AND status IN ('pending', 'in_progress')
                    """, (f"%kontrakt #{c_id}%", c_end_date))
                    if not cur.fetchone():
                        # Find CONTRACT area id
                        cur.execute("SELECT id FROM compliance_areas WHERE code = 'CONTRACT'")
                        area_row = cur.fetchone()
                        area_id = area_row[0] if area_row else None

                        cur.execute("""
                            INSERT INTO compliance_deadlines
                                (title, deadline_date, deadline_type, area_id, status)
                            VALUES (%s, %s, 'contract', %s, 'pending')
                        """, (
                            f"Wygaśnięcie kontraktu #{c_id}: {c_title}",
                            c_end_date,
                            area_id,
                        ))
                        deadlines_created += 1
                        log.info("contract_deadline_created",
                                 contract_id=c_id, end_date=str(c_end_date))

        conn.commit()

    log.info("contracts_compliance_checked",
             checked=contracts_checked, matters=matters_created, deadlines=deadlines_created)
    return {
        "contracts_checked": contracts_checked,
        "matters_created": matters_created,
        "deadlines_created": deadlines_created,
    }


def create_compliance_alerts() -> dict[str, Any]:
    """Tworzy alerty compliance w tabeli alerts.

    1. Deadlines overdue → alert severity='high'
    2. Deadlines < 3 dni → alert severity='medium'
    3. Non-compliant obligations → alert severity='high'
    4. Stale documents > 30 dni → alert severity='low'
    5. Overdue trainings → alert severity='medium'

    Dedup: sprawdź czy alert z tym samym title już istnieje i jest active.
    """
    _ensure_tables()
    alerts_created = 0

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            def _insert_alert(severity: str, title: str, description: str, evidence: str | None = None) -> bool:
                """Insert alert if not already active. Returns True if inserted."""
                cur.execute("""
                    SELECT id FROM alerts
                    WHERE title = %s AND is_active = TRUE
                """, (title,))
                if cur.fetchone():
                    return False
                cur.execute("""
                    INSERT INTO alerts (alert_type, severity, title, description, evidence, is_active)
                    VALUES ('compliance', %s, %s, %s, %s, TRUE)
                """, (severity, title, description, evidence))
                return True

            # 1. Overdue deadlines → high
            cur.execute("""
                SELECT cd.id, cd.title, cd.deadline_date, ca.code
                FROM compliance_deadlines cd
                LEFT JOIN compliance_areas ca ON ca.id = cd.area_id
                WHERE cd.deadline_date < CURRENT_DATE
                  AND cd.status IN ('pending', 'in_progress')
            """)
            for dl_id, dl_title, dl_date, area_code in cur.fetchall():
                alert_title = f"[Compliance] Termin przeterminowany: {dl_title}"
                if _insert_alert(
                    'high', alert_title,
                    f"Deadline '{dl_title}' (ID:{dl_id}) upłynął {dl_date}. Obszar: {area_code or 'brak'}.",
                    json.dumps({"deadline_id": dl_id, "deadline_date": str(dl_date), "area": area_code}),
                ):
                    alerts_created += 1

            # 2. Deadlines < 3 days → medium
            cur.execute("""
                SELECT cd.id, cd.title, cd.deadline_date, ca.code
                FROM compliance_deadlines cd
                LEFT JOIN compliance_areas ca ON ca.id = cd.area_id
                WHERE cd.deadline_date BETWEEN CURRENT_DATE AND CURRENT_DATE + 3
                  AND cd.status IN ('pending', 'in_progress')
            """)
            for dl_id, dl_title, dl_date, area_code in cur.fetchall():
                alert_title = f"[Compliance] Zbliżający się termin: {dl_title}"
                if _insert_alert(
                    'medium', alert_title,
                    f"Deadline '{dl_title}' (ID:{dl_id}) upływa {dl_date}. Pozostało < 3 dni.",
                    json.dumps({"deadline_id": dl_id, "deadline_date": str(dl_date), "area": area_code}),
                ):
                    alerts_created += 1

            # 3. Non-compliant obligations → high
            cur.execute("""
                SELECT co.id, co.title, ca.code
                FROM compliance_obligations co
                LEFT JOIN compliance_areas ca ON ca.id = co.area_id
                WHERE co.compliance_status = 'non_compliant'
                  AND co.status = 'active'
            """)
            for ob_id, ob_title, area_code in cur.fetchall():
                alert_title = f"[Compliance] Non-compliant: {ob_title}"
                if _insert_alert(
                    'high', alert_title,
                    f"Obowiązek '{ob_title}' (ID:{ob_id}) jest non-compliant. Obszar: {area_code or 'brak'}.",
                    json.dumps({"obligation_id": ob_id, "area": area_code}),
                ):
                    alerts_created += 1

            # 4. Stale documents > 30 days overdue for review → low
            cur.execute("""
                SELECT cd.id, cd.title, cd.review_due, ca.code
                FROM compliance_documents cd
                LEFT JOIN compliance_areas ca ON ca.id = cd.area_id
                WHERE cd.review_due < CURRENT_DATE - 30
                  AND cd.status = 'active'
            """)
            for doc_id, doc_title, review_due, area_code in cur.fetchall():
                alert_title = f"[Compliance] Stale document: {doc_title}"
                if _insert_alert(
                    'low', alert_title,
                    f"Dokument '{doc_title}' (ID:{doc_id}) wymaga przeglądu od {review_due}.",
                    json.dumps({"document_id": doc_id, "review_due": str(review_due), "area": area_code}),
                ):
                    alerts_created += 1

            # 5. Overdue trainings → medium
            cur.execute("""
                SELECT ct.id, ct.title, ct.deadline, ca.code
                FROM compliance_trainings ct
                LEFT JOIN compliance_areas ca ON ca.id = ct.area_id
                WHERE ct.deadline < CURRENT_DATE
                  AND ct.status NOT IN ('completed', 'cancelled')
            """)
            for tr_id, tr_title, tr_deadline, area_code in cur.fetchall():
                alert_title = f"[Compliance] Przeterminowane szkolenie: {tr_title}"
                if _insert_alert(
                    'medium', alert_title,
                    f"Szkolenie '{tr_title}' (ID:{tr_id}) miało termin {tr_deadline}.",
                    json.dumps({"training_id": tr_id, "deadline": str(tr_deadline), "area": area_code}),
                ):
                    alerts_created += 1

        conn.commit()

    log.info("compliance_alerts_created", count=alerts_created)
    return {"alerts_created": alerts_created}


# ================================================================
# Monthly verification (L8)
# ================================================================

def run_monthly_verification() -> dict[str, Any]:
    """Cron monthly: pełna weryfikacja compliance wszystkich obszarów.

    Per area:
    1. Sprawdź compliance_status każdego obligation
    2. Sprawdź czy dokumenty są aktualne (review_due)
    3. Sprawdź czy szkolenia są ukończone
    4. Jeśli area.last_reviewed_at + review_frequency_days < TODAY → pending_review + matter
    5. Wyślij summary na WhatsApp.
    """
    _ensure_tables()
    _seed_compliance_areas()

    areas_reviewed = 0
    issues_found = 0
    matters_created = 0
    area_reports: list[str] = []

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Fetch all active areas
            cur.execute("""
                SELECT id, code, name_pl, review_frequency_days, last_reviewed_at
                FROM compliance_areas
                WHERE status = 'active'
                ORDER BY code
            """)
            areas = cur.fetchall()

            for area_id, area_code, area_name, freq_days, last_reviewed in areas:
                areas_reviewed += 1
                area_issues = 0

                # 1. Check obligation compliance status
                cur.execute("""
                    SELECT COUNT(*) FILTER (WHERE compliance_status IN ('non_compliant', 'partially_compliant')),
                           COUNT(*) FILTER (WHERE compliance_status = 'unknown'),
                           COUNT(*)
                    FROM compliance_obligations
                    WHERE area_id = %s AND status = 'active'
                """, (area_id,))
                obl_row = cur.fetchone()
                non_compliant = obl_row[0] if obl_row else 0
                unknown = obl_row[1] if obl_row else 0
                total_obl = obl_row[2] if obl_row else 0
                area_issues += non_compliant

                # 2. Check stale documents
                cur.execute("""
                    SELECT COUNT(*) FROM compliance_documents
                    WHERE area_id = %s AND status = 'active'
                      AND review_due IS NOT NULL AND review_due < CURRENT_DATE
                """, (area_id,))
                stale_docs = cur.fetchone()[0]
                area_issues += stale_docs

                # 3. Check overdue trainings
                cur.execute("""
                    SELECT COUNT(*) FROM compliance_trainings
                    WHERE area_id = %s
                      AND deadline < CURRENT_DATE
                      AND status NOT IN ('completed', 'cancelled')
                """, (area_id,))
                overdue_trainings = cur.fetchone()[0]
                area_issues += overdue_trainings

                # 4. Check if area needs review
                needs_review = False
                if freq_days and last_reviewed:
                    from datetime import timedelta
                    if last_reviewed.date() + timedelta(days=freq_days) < date.today():
                        needs_review = True
                elif freq_days and not last_reviewed:
                    needs_review = True

                if needs_review:
                    cur.execute("""
                        UPDATE compliance_areas
                        SET status = 'pending_review', updated_at = NOW()
                        WHERE id = %s
                    """, (area_id,))

                    # Check if review matter already exists
                    cur.execute("""
                        SELECT id FROM compliance_matters
                        WHERE area_id = %s AND matter_type = 'audit_finding'
                          AND status NOT IN ('closed', 'completed')
                          AND title LIKE %s
                    """, (area_id, f"Przegląd obszaru {area_name}%"))
                    if not cur.fetchone():
                        cur.execute("""
                            INSERT INTO compliance_matters
                                (title, matter_type, area_id, priority, description)
                            VALUES (%s, 'audit_finding', %s, 'medium', %s)
                        """, (
                            f"Przegląd obszaru {area_name}",
                            area_id,
                            f"Automatyczny przegląd obszaru {area_name} ({area_code}) — termin review przekroczony.",
                        ))
                        matters_created += 1

                issues_found += area_issues

                # Area report line
                status_icon = "🔴" if area_issues > 0 else ("🟡" if needs_review else "🟢")
                area_reports.append(
                    f"{status_icon} {area_code}: obl={total_obl} (NC:{non_compliant}, ?:{unknown}), "
                    f"stale_docs={stale_docs}, overdue_train={overdue_trainings}"
                    + (" [NEEDS REVIEW]" if needs_review else "")
                )

                # Mark area as reviewed
                cur.execute("""
                    UPDATE compliance_areas
                    SET last_reviewed_at = NOW(), updated_at = NOW()
                    WHERE id = %s AND status != 'pending_review'
                """, (area_id,))

        conn.commit()

    # Send summary to WhatsApp
    summary = (
        f"📋 Monthly Compliance Verification\n"
        f"Areas: {areas_reviewed}, Issues: {issues_found}, New matters: {matters_created}\n\n"
        + "\n".join(area_reports)
    )
    try:
        import subprocess
        subprocess.run([
            os.getenv("OPENCLAW_BIN", "openclaw"), "message", "send",
            "--channel", "whatsapp", "--target", os.getenv("WA_TARGET", ""),
            "--message", summary,
        ], capture_output=True, text=True, timeout=30)
    except Exception:
        pass

    log.info("monthly_verification_completed",
             areas=areas_reviewed, issues=issues_found, matters=matters_created)

    return {
        "areas_reviewed": areas_reviewed,
        "issues_found": issues_found,
        "matters_created": matters_created,
    }
