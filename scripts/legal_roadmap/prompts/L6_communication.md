Jesteś ekspertem od compliance communication management. Zadanie: L6 — Communication Planner + Reporter + Daily Updates.

REPO: /home/sebastian/personal-ai

## KONTEKST
Moduł Legal & Compliance jest w budowie. Istnieją: legal_compliance.py (orchestrator), obligation_tracker.py, regulatory_scanner.py, risk_assessor.py, document_generator.py, training_manager.py. Tabele DB, API endpointy /compliance/*.

Istniejące systemy:
- app/orchestrator/communication.py: send_and_log(channel, recipient, subject, body, authorization_type), _send_whatsapp_to()
- compliance_raci table: macierz RACI (responsible, accountable, consulted, informed)
- compliance_communications table: plan komunikacji z execution tracking

## CO MUSISZ ZROBIĆ

### 1. Utwórz app/analysis/legal/communication_planner.py

```python
"""
Communication Planner — planowanie i egzekucja komunikacji compliance.

Workflow:
1. Generuj plan komunikacji z RACI matrix i action_plan
2. Waliduj scope via standing_orders
3. Egzekwuj komunikację przez istniejące kanały (email/Teams/WhatsApp)
4. Trackuj delivery i confirmation
"""
from __future__ import annotations

import structlog
log = structlog.get_logger(__name__)

import json
import os
from datetime import date, datetime, timezone
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection
from app.db.cost_tracker import log_anthropic_cost

load_dotenv()

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=120.0)
```

Implementuj:

#### generate_communication_plan()
```python
def generate_communication_plan(matter_id: int) -> dict[str, Any]:
    """Generuje plan komunikacji na bazie RACI matrix, action_plan i area.

    1. Pobierz matter (title, action_plan, area)
    2. Pobierz RACI entries dla matter (compliance_raci JOIN people)
    3. Wywołaj Claude:
       'Na podstawie sprawy compliance i macierzy RACI, wygeneruj plan komunikacji.
        Sprawa: {title}
        Obszar: {area}
        RACI: {raci_entries}
        Action plan: {action_plan}

        Dla każdego interesariusza określ:
        - Kogo poinformować (imię, rola RACI)
        - O czym (treść komunikatu — 2-3 zdania)
        - Jakim kanałem (email dla formalnych, Teams dla operacyjnych, WhatsApp dla pilnych)
        - Kiedy (data lub "natychmiast" / "po zatwierdzeniu" / "po szkoleniu")
        - Cel (inform/request_action/request_signature/train)

        Zwróć JSON array: [{recipient_name, recipient_role, channel, subject, content, when, purpose}]'

    4. INSERT INTO compliance_communications (matter_id, recipient_person_id, channel, subject, content, purpose, scheduled_date, status='planned')
    5. Zaktualizuj matter.communication_plan z JSON
    6. Zwróć: {matter_id, communications_planned: N, details: [...]}
    """
```

#### execute_communication_plan()
```python
def execute_communication_plan(matter_id: int) -> dict[str, Any]:
    """Egzekwuje zaplanowaną komunikację.

    1. Pobierz compliance_communications WHERE matter_id AND status='planned' AND scheduled_date <= TODAY
    2. Dla każdej:
       a. Sprawdź scope via: from app.orchestrator.communication import check_scope, send_and_log
       b. Jeśli scope OK → send_and_log(channel, recipient, subject, body, 'compliance')
       c. Jeśli scope NOT OK → propose_action() dla zatwierdzenia (authority level 2)
       d. UPDATE compliance_communications SET status='sent', sent_communication_id = comm_id
    3. Zwróć: {sent: N, pending_approval: N, failed: N}
    """
```

#### set_raci()
```python
def set_raci(
    area_code: str | None = None,
    matter_id: int | None = None,
    person_id: int = 0,
    role: str = "informed",
    notes: str | None = None,
) -> dict[str, Any]:
    """Dodaje wpis RACI. INSERT ... ON CONFLICT DO UPDATE."""
```

#### get_raci()
```python
def get_raci(matter_id: int | None = None, area_code: str | None = None) -> list[dict[str, Any]]:
    """Pobierz RACI matrix. JOIN z people na imię/nazwisko."""
```

### 2. Utwórz app/analysis/legal/compliance_reporter.py

```python
"""
Compliance Reporter — raporty, dashboard data, daily/weekly updates.

Raporty:
- Daily update: krótki status na WhatsApp (overdue, upcoming, open matters)
- Weekly report: pełny przegląd compliance per area
- Area report: szczegółowy raport dla konkretnego obszaru
"""
from __future__ import annotations

import structlog
log = structlog.get_logger(__name__)

import os
import subprocess
from datetime import date, datetime, timezone
from typing import Any

from app.db.postgres import get_pg_connection
from dotenv import load_dotenv

load_dotenv()

OPENCLAW_BIN = os.getenv("OPENCLAW_BIN", "openclaw")
WA_TARGET = os.getenv("WA_TARGET", "")
```

Implementuj:

#### generate_daily_update()
```python
def generate_daily_update() -> str | None:
    """Generuje dzienny update compliance na WhatsApp.

    Zbierz:
    - Overdue deadlines count
    - Upcoming deadlines (7 dni)
    - Open matters count by priority
    - Stale documents count
    - Pending trainings count
    - Pending signatures count

    Format WhatsApp (max 800 znaków):
    '📋 *Compliance Daily*
    ⚠️ Overdue: {N} terminów
    📅 Nadchodzące (7d): {N}
    📂 Otwarte sprawy: {N} (critical: {N})
    📄 Dokumenty do przeglądu: {N}
    📚 Szkolenia w toku: {N}
    ✍️ Podpisy oczekujące: {N}

    Szczegóły: /compliance/dashboard'

    Zwróć None jeśli nie ma nic do raportowania (0 overdue, 0 upcoming).
    """
```

#### generate_weekly_report()
```python
def generate_weekly_report() -> dict[str, Any]:
    """Tygodniowy raport compliance.

    Per area:
    - Obligations: compliant/partially/non_compliant count
    - Matters: opened/closed this week
    - Deadlines: met/missed this week
    - Documents: generated/approved/expired
    - Trainings: completed/overdue
    - Risks: new/mitigated

    Wyślij na WhatsApp podsumowanie (max 1500 znaków).
    Zwróć pełny raport jako dict.
    """
```

#### generate_area_report()
```python
def generate_area_report(area_code: str) -> dict[str, Any]:
    """Szczegółowy raport dla obszaru compliance.

    Zbierz:
    - Area detail (name, governing_body, risk_level, last_reviewed)
    - All obligations with compliance_status
    - Open matters
    - Active documents
    - Upcoming deadlines
    - Active trainings
    - Risk assessments
    - RACI matrix

    Zwróć jako dict (dla API).
    """
```

### 3. Rozszerz advance_matter_phase() — fazy 8-10

W legal_compliance.py:
```python
# communication → verification:
#   execute_communication_plan(matter_id)
#   Sprawdź czy wszystkie communications sent

# verification → monitoring:
#   Sprawdź: all obligations compliant, all documents signed, all trainings completed
#   Zbierz audit evidence
#   Jeśli OK → status='completed', phase='monitoring'

# monitoring → closed:
#   Ręczne zamknięcie po potwierdzeniu compliance
```

### 4. Dodaj wrappers w legal_compliance.py

```python
# ================================================================
# Communication functions
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
    """Cron daily: deadlines + freshness + daily update."""
    _ensure_tables()
    from app.analysis.legal.obligation_tracker import run_deadline_monitor
    from app.analysis.legal.document_generator import run_document_freshness_check
    from app.analysis.legal.compliance_reporter import generate_daily_update
    deadline_result = run_deadline_monitor()
    freshness_result = run_document_freshness_check()
    update_msg = generate_daily_update()
    if update_msg:
        try:
            import subprocess
            subprocess.run([os.getenv("OPENCLAW_BIN", "openclaw"), "message", "send",
                          "--channel", "whatsapp", "--target", os.getenv("WA_TARGET", ""),
                          "--message", update_msg], capture_output=True, text=True, timeout=30)
        except Exception:
            pass
    return {"deadlines": deadline_result, "freshness": freshness_result, "update_sent": bool(update_msg)}
```

### 5. Zaktualizuj scripts/legal_compliance_daily.sh

Zastąp zawartość:
```bash
#!/bin/bash
set -euo pipefail
cd /home/sebastian/personal-ai
source .venv/bin/activate

echo "[$(date +'%Y-%m-%d %H:%M:%S')] Legal Compliance Daily Check"

python3 -c "
from app.analysis.legal_compliance import run_daily_compliance_check
result = run_daily_compliance_check()
print(f'Daily check: {result}')
"

echo "[$(date +'%Y-%m-%d %H:%M:%S')] Done"
```

### 6. API endpointy

```python
@app.get("/compliance/report/daily")
def compliance_daily_report():
    from app.analysis.legal.compliance_reporter import generate_daily_update
    update = generate_daily_update()
    return {"report": update or "No compliance issues to report"}

@app.get("/compliance/report/area/{code}")
def compliance_area_report(code: str):
    from app.analysis.legal.compliance_reporter import generate_area_report
    return generate_area_report(code.upper())

@app.get("/compliance/raci")
def compliance_raci(matter_id: int | None = None, area_code: str | None = None):
    from app.analysis.legal.communication_planner import get_raci
    return {"raci": get_raci(matter_id=matter_id, area_code=area_code)}

@app.post("/compliance/matters/{matter_id}/communication-plan")
def compliance_comm_plan(matter_id: int):
    from app.analysis.legal_compliance import generate_communication_plan
    return generate_communication_plan(matter_id)

@app.post("/compliance/matters/{matter_id}/execute-communication")
def compliance_exec_comm(matter_id: int):
    from app.analysis.legal_compliance import execute_communication_plan
    return execute_communication_plan(matter_id)
```

## WERYFIKACJA

```bash
python3 -c "
import sys; sys.path.insert(0, '/home/sebastian/personal-ai')
from app.analysis.legal.communication_planner import generate_communication_plan, get_raci
from app.analysis.legal.compliance_reporter import generate_daily_update, generate_weekly_report
print('L6 modules: OK')
"

# Daily update test
python3 -c "
import sys; sys.path.insert(0, '/home/sebastian/personal-ai')
from app.analysis.legal.compliance_reporter import generate_daily_update
update = generate_daily_update()
print('Daily update:', update or 'Nothing to report')
"

# Daily cron test
bash scripts/legal_compliance_daily.sh

python3 /home/sebastian/personal-ai/scripts/non_regression_gate.py
```
