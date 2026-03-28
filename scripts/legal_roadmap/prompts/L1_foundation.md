Jesteś ekspertem od architektury systemów compliance. Zadanie: L1 — Foundation: DB Schema + Main Orchestrator + Base API.

REPO: /home/sebastian/personal-ai

## KONTEKST
Budujesz moduł Legal & Compliance Orchestrator dla systemu Gilbertus — prywatnego mentata AI dla właściciela polskich spółek energetycznych (REH, REF). System używa Python, FastAPI, PostgreSQL, Qdrant, Claude API, structlog.

## CO MUSISZ ZROBIĆ

### 1. Utwórz app/analysis/legal/__init__.py
Pusty plik.

### 2. Utwórz app/analysis/legal_compliance.py — główny orchestrator

Wzoruj się na istniejących modułach (np. app/analysis/compliance_manager.py, app/analysis/contract_tracker.py).

IMPORTY (dokładnie te):
```python
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
from datetime import datetime, timezone, date
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection
from app.db.cost_tracker import log_anthropic_cost

load_dotenv()

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
ANTHROPIC_FAST = os.getenv("ANTHROPIC_FAST_MODEL", "claude-haiku-4-5")
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=120.0)
```

### 3. Funkcja _ensure_tables() — utwórz 10 tabel

Wzór z istniejących modułów — CREATE TABLE IF NOT EXISTS z indeksami.

**Tabela 1: compliance_areas** (9 obszarów compliance)
```sql
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
```

**Tabela 2: compliance_obligations** (rejestr obowiązków prawnych)
```sql
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
```

**Tabela 3: compliance_matters** (sprawy/projekty compliance — lifecycle 10 faz)
```sql
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
```

**Tabela 4: compliance_documents** (repozytorium z wersjonowaniem i signature tracking)
```sql
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
```

**Tabela 5: compliance_deadlines** (kalendarz terminów z reminder system)
```sql
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
```

**Tabela 6: compliance_trainings** (szkolenia)
```sql
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
```

**Tabela 7: compliance_training_records** (ewidencja per osoba)
```sql
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
```

**Tabela 8: compliance_raci** (macierz RACI)
```sql
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
```

**Tabela 9: compliance_risk_assessments** (oceny ryzyk 5×5)
```sql
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
```

**Tabela 10: compliance_audit_evidence** (dowody dla audytu)
```sql
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
```

### 4. Funkcja _seed_compliance_areas() — seed 9 obszarów

Wywołaj po _ensure_tables(). Użyj INSERT ... ON CONFLICT (code) DO NOTHING:

```python
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
```

### 5. Funkcje CRUD w legal_compliance.py

Implementuj następujące funkcje:

```python
def create_matter(
    title: str,
    matter_type: str,
    area_code: str | None = None,
    description: str | None = None,
    priority: str = "medium",
    contract_id: int | None = None,
    source_regulation: str | None = None,
) -> dict[str, Any]:
    """Tworzy nową sprawę compliance. Zwraca dict z id, title, status, phase."""

def list_matters(
    status: str | None = None,
    area_code: str | None = None,
    priority: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Lista spraw z filtrami."""

def get_matter_detail(matter_id: int) -> dict[str, Any]:
    """Pełny detail sprawy z powiązanymi danymi (documents, deadlines, risks)."""

def get_compliance_dashboard() -> dict[str, Any]:
    """Dashboard: areas summary, open matters count, upcoming deadlines, overdue count, doc freshness, risk heatmap."""

def list_areas() -> list[dict[str, Any]]:
    """Lista obszarów compliance ze statusem."""

def get_area_detail(area_code: str) -> dict[str, Any]:
    """Detail obszaru z obligations, matters, documents."""
```

### 6. Dodaj 5 bazowych API endpointów w app/api/main.py

Dodaj po sekcji contracts (szukaj `@app.get("/contracts")`). Wzoruj się na istniejącym stylu (get_pg_connection, parametrized SQL, dict comprehension).

```python
# ========================= Compliance =========================

@app.get("/compliance/dashboard")
def compliance_dashboard():
    """Overall compliance status dashboard."""
    from app.analysis.legal_compliance import get_compliance_dashboard
    return get_compliance_dashboard()

@app.get("/compliance/areas")
def compliance_areas():
    """List all compliance areas."""
    from app.analysis.legal_compliance import list_areas
    return {"areas": list_areas()}

@app.get("/compliance/areas/{code}")
def compliance_area_detail(code: str):
    """Detail for specific compliance area."""
    from app.analysis.legal_compliance import get_area_detail
    return get_area_detail(code.upper())

@app.get("/compliance/matters")
def compliance_matters(status: str | None = None, area_code: str | None = None, priority: str | None = None, limit: int = 20):
    """List compliance matters with filters."""
    from app.analysis.legal_compliance import list_matters
    return {"matters": list_matters(status=status, area_code=area_code, priority=priority, limit=limit)}

@app.post("/compliance/matters")
def create_compliance_matter(request: Request, body: dict):
    """Create new compliance matter."""
    from app.analysis.legal_compliance import create_matter
    return create_matter(
        title=body.get("title", ""),
        matter_type=body.get("matter_type", "other"),
        area_code=body.get("area_code"),
        description=body.get("description"),
        priority=body.get("priority", "medium"),
        contract_id=body.get("contract_id"),
        source_regulation=body.get("source_regulation"),
    )

@app.get("/compliance/matters/{matter_id}")
def compliance_matter_detail(matter_id: int):
    """Full detail for compliance matter."""
    from app.analysis.legal_compliance import get_matter_detail
    return get_matter_detail(matter_id)
```

## WERYFIKACJA

```bash
# 1. Sprawdź że tabele się tworzą
python3 -c "
import sys; sys.path.insert(0, '/home/sebastian/personal-ai')
from app.analysis.legal_compliance import _ensure_tables, _seed_compliance_areas
_ensure_tables()
_seed_compliance_areas()
print('Tables + seed: OK')
"

# 2. Sprawdź że areas są w DB
docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -c "SELECT code, name_pl, risk_level FROM compliance_areas ORDER BY code;"

# 3. Sprawdź dashboard
python3 -c "
import sys; sys.path.insert(0, '/home/sebastian/personal-ai')
from app.analysis.legal_compliance import get_compliance_dashboard
import json
print(json.dumps(get_compliance_dashboard(), indent=2, default=str))
"

# 4. Sprawdź create_matter
python3 -c "
import sys; sys.path.insert(0, '/home/sebastian/personal-ai')
from app.analysis.legal_compliance import create_matter
result = create_matter('Test RODO compliance', 'policy_update', 'RODO', 'Test matter', 'medium')
print('Matter created:', result)
"

# 5. Sprawdź API
systemctl --user restart gilbertus-api || true
sleep 3
curl -s http://127.0.0.1:8000/compliance/dashboard | python3 -m json.tool
curl -s http://127.0.0.1:8000/compliance/areas | python3 -m json.tool

# 6. Non-regression
python3 /home/sebastian/personal-ai/scripts/non_regression_gate.py
```

## WAŻNE ZASADY
- Connection pool: ZAWSZE `get_pg_connection()`, nigdy raw psycopg.connect()
- SQL: ZAWSZE parameterized (%s), nigdy f-string
- Logging: structlog, nigdy print()
- Daty: zawsze YYYY-MM-DD, timezone-aware
- Nie dodawaj komentarzy typu "Be conservative" w promptach
- Nie restartuj API automatycznie — tylko przygotuj kod
