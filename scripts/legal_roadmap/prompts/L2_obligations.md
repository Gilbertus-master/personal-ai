Jesteś ekspertem od compliance management. Zadanie: L2 — Obligation Tracker + Deadline Monitor + Cron.

REPO: /home/sebastian/personal-ai

## KONTEKST
Moduł Legal & Compliance Orchestrator jest w trakcie budowy. L1 (foundation) już istnieje:
- app/analysis/legal_compliance.py — main orchestrator z _ensure_tables(), _seed_compliance_areas(), CRUD
- app/analysis/legal/__init__.py — pusty
- 10 tabel DB istnieje (compliance_areas, compliance_obligations, compliance_deadlines, itd.)
- 9 obszarów compliance zaseedowanych (URE, RODO, AML, KSH, ESG, LABOR, TAX, CONTRACT, INTERNAL_AUDIT)
- 5 bazowych API endpointów działa (/compliance/dashboard, /compliance/areas, /compliance/matters)

## CO MUSISZ ZROBIĆ

### 1. Utwórz app/analysis/legal/obligation_tracker.py

```python
"""
Obligation Tracker — monitoring obowiązków prawnych, terminów i przypomnień.

Funkcje:
- CRUD obowiązków (create, update, list, get)
- Automatyczne obliczanie next_deadline na podstawie recurrence
- System przypomnień (30/14/7/3/1 dni przed terminem) via WhatsApp
- Auto-update compliance_status na podstawie fulfillment
- Oznaczanie overdue gdy termin minął
- Tworzenie compliance_deadlines z obligations

Cron: codziennie 6:15 (w ramach legal_compliance_daily.sh)
"""
from __future__ import annotations

import structlog
log = structlog.get_logger(__name__)

import os
import subprocess
from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.db.postgres import get_pg_connection
from dotenv import load_dotenv

load_dotenv()

OPENCLAW_BIN = os.getenv("OPENCLAW_BIN", "openclaw")
WA_TARGET = os.getenv("WA_TARGET", "")
```

Implementuj następujące funkcje:

#### create_obligation()
```python
def create_obligation(
    area_code: str,
    title: str,
    obligation_type: str,
    description: str | None = None,
    legal_basis: str | None = None,
    frequency: str | None = None,
    deadline_rule: str | None = None,
    next_deadline: str | None = None,  # YYYY-MM-DD
    penalty_description: str | None = None,
    penalty_max_pln: float | None = None,
    applies_to: list[str] | None = None,  # ['REH', 'REF']
    responsible_role: str | None = None,
    required_documents: list[str] | None = None,
) -> dict[str, Any]:
    """Tworzy nowy obowiązek prawny. Automatycznie tworzy deadline jeśli next_deadline podany."""
```
- Pobierz area_id z compliance_areas po code
- INSERT INTO compliance_obligations
- Jeśli next_deadline podany → wywołaj _create_deadline_from_obligation()
- Zwróć dict z id, title, area_code, next_deadline, status

#### list_obligations()
```python
def list_obligations(
    area_code: str | None = None,
    compliance_status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Lista obowiązków z filtrami. JOIN z compliance_areas na code."""
```

#### get_overdue_obligations()
```python
def get_overdue_obligations() -> list[dict[str, Any]]:
    """Zwraca obowiązki z next_deadline < TODAY i compliance_status != 'compliant'."""
```

#### fulfill_obligation()
```python
def fulfill_obligation(obligation_id: int, evidence_description: str | None = None) -> dict[str, Any]:
    """Oznacza obowiązek jako spełniony. Aktualizuje last_fulfilled_at, compliance_status='compliant'.
    Jeśli recurrence != 'one_time' → oblicz i ustaw nowy next_deadline.
    Opcjonalnie tworzy compliance_audit_evidence."""
```

#### _calculate_next_deadline()
```python
def _calculate_next_deadline(current_deadline: date, frequency: str) -> date | None:
    """Oblicza następny termin na podstawie frequency.
    monthly → +1 month, quarterly → +3 months, semi_annual → +6, annual → +12, biennial → +24.
    Zwraca None dla one_time, on_change, on_demand."""
```

#### _create_deadline_from_obligation()
```python
def _create_deadline_from_obligation(obligation_id: int, obligation_title: str,
                                       deadline_date: date, area_id: int,
                                       responsible_person_id: int | None = None) -> int:
    """Tworzy wpis w compliance_deadlines. Zwraca deadline_id."""
```

#### check_deadlines_and_remind()
```python
def check_deadlines_and_remind() -> dict[str, Any]:
    """Główna funkcja cron. Sprawdza compliance_deadlines:
    1. Oznacz overdue (deadline_date < TODAY i status='pending')
    2. Dla każdego pending deadline sprawdź reminder_days array
    3. Jeśli TODAY jest w reminder_days od deadline → wyślij WhatsApp
    4. Aktualizuj last_reminder_sent

    Format WhatsApp:
    '⚠️ *Compliance Deadline*\n{title}\nTermin: {deadline_date} ({days} dni)\nObszar: {area_name}\nOdp: {responsible}'

    Zwraca: {checked: N, reminded: N, overdue_marked: N}"""
```

#### _send_reminder_wa()
```python
def _send_reminder_wa(message: str):
    """Wysyła WhatsApp reminder via openclaw. Timeout 30s, capture output."""
```
Wzór:
```python
try:
    subprocess.run(
        [OPENCLAW_BIN, "message", "send", "--channel", "whatsapp",
         "--target", WA_TARGET, "--message", message],
        capture_output=True, text=True, timeout=30,
    )
except Exception as e:
    log.error("wa_reminder_failed", error=str(e))
```

#### run_deadline_monitor()
```python
def run_deadline_monitor() -> dict[str, Any]:
    """Entry point dla cron. Wywołuje check_deadlines_and_remind().
    Dodatkowo: update compliance_status na 'non_compliant' dla overdue obligations."""
```

### 2. Dodaj funkcje wrapper w app/analysis/legal_compliance.py

Na końcu pliku (przed `if __name__`) dodaj:

```python
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
```

### 3. Dodaj API endpointy w app/api/main.py

Dodaj po istniejących endpointach /compliance/*:

```python
@app.get("/compliance/obligations")
def compliance_obligations(area_code: str | None = None, status: str | None = None, limit: int = 50):
    """List compliance obligations."""
    from app.analysis.legal_compliance import list_obligations
    return {"obligations": list_obligations(area_code=area_code, compliance_status=status, limit=limit)}

@app.get("/compliance/obligations/overdue")
def compliance_obligations_overdue():
    """List overdue obligations."""
    from app.analysis.legal_compliance import get_overdue_obligations
    return {"overdue": get_overdue_obligations()}

@app.post("/compliance/obligations")
def create_compliance_obligation(request: Request, body: dict):
    """Create new compliance obligation."""
    from app.analysis.legal_compliance import create_obligation
    return create_obligation(**{k: v for k, v in body.items() if v is not None})

@app.post("/compliance/obligations/{obligation_id}/fulfill")
def fulfill_compliance_obligation(obligation_id: int, body: dict = {}):
    """Mark obligation as fulfilled."""
    from app.analysis.legal_compliance import fulfill_obligation
    return fulfill_obligation(obligation_id, body.get("evidence_description"))

@app.get("/compliance/deadlines")
def compliance_deadlines(days_ahead: int = 30, area_code: str | None = None):
    """Upcoming compliance deadlines."""
    from app.analysis.legal.obligation_tracker import list_obligations
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            sql = """
                SELECT d.id, d.title, d.deadline_date, d.deadline_type, d.status,
                       d.recurrence, a.code as area_code, a.name_pl as area_name
                FROM compliance_deadlines d
                LEFT JOIN compliance_areas a ON a.id = d.area_id
                WHERE d.deadline_date <= CURRENT_DATE + %s
                  AND d.status IN ('pending','in_progress')
            """
            params = [days_ahead]
            if area_code:
                sql += " AND a.code = %s"
                params.append(area_code.upper())
            sql += " ORDER BY d.deadline_date ASC"
            cur.execute(sql, params)
            return {"deadlines": [
                {"id": r[0], "title": r[1], "date": str(r[2]), "type": r[3],
                 "status": r[4], "recurrence": r[5], "area_code": r[6], "area_name": r[7]}
                for r in cur.fetchall()
            ]}

@app.get("/compliance/deadlines/overdue")
def compliance_deadlines_overdue():
    """Overdue compliance deadlines."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT d.id, d.title, d.deadline_date, d.deadline_type,
                       a.code, a.name_pl,
                       CURRENT_DATE - d.deadline_date as days_overdue
                FROM compliance_deadlines d
                LEFT JOIN compliance_areas a ON a.id = d.area_id
                WHERE d.status = 'overdue'
                   OR (d.deadline_date < CURRENT_DATE AND d.status = 'pending')
                ORDER BY d.deadline_date ASC
            """)
            return {"overdue": [
                {"id": r[0], "title": r[1], "date": str(r[2]), "type": r[3],
                 "area_code": r[4], "area_name": r[5], "days_overdue": r[6]}
                for r in cur.fetchall()
            ]}
```

### 4. Utwórz scripts/legal_compliance_daily.sh

```bash
#!/bin/bash
set -euo pipefail
cd /home/sebastian/personal-ai
source .venv/bin/activate

echo "[$(date +'%Y-%m-%d %H:%M:%S')] Legal Compliance Daily Check"

# 1. Deadline monitor + reminders
python3 -c "
from app.analysis.legal_compliance import run_deadline_monitor
result = run_deadline_monitor()
print(f'Deadlines: {result}')
"

echo "[$(date +'%Y-%m-%d %H:%M:%S')] Done"
```

```bash
chmod +x scripts/legal_compliance_daily.sh
```

## WERYFIKACJA

```bash
# 1. Import test
python3 -c "
import sys; sys.path.insert(0, '/home/sebastian/personal-ai')
from app.analysis.legal.obligation_tracker import create_obligation, check_deadlines_and_remind
print('obligation_tracker: OK')
"

# 2. Create test obligation
python3 -c "
import sys; sys.path.insert(0, '/home/sebastian/personal-ai')
from app.analysis.legal_compliance import create_obligation
result = create_obligation(
    area_code='RODO',
    title='Aktualizacja rejestru czynności przetwarzania',
    obligation_type='documentation',
    frequency='annual',
    next_deadline='2026-12-31',
    penalty_description='Kara do 20M EUR lub 4% obrotu',
    applies_to=['REH', 'REF'],
    responsible_role='IOD',
)
print('Created:', result)
"

# 3. List obligations
python3 -c "
import sys; sys.path.insert(0, '/home/sebastian/personal-ai')
from app.analysis.legal_compliance import list_obligations
import json
print(json.dumps(list_obligations(area_code='RODO'), indent=2, default=str))
"

# 4. Deadline monitor dry run
python3 -c "
import sys; sys.path.insert(0, '/home/sebastian/personal-ai')
from app.analysis.legal_compliance import run_deadline_monitor
print(run_deadline_monitor())
"

# 5. Cron script test
bash scripts/legal_compliance_daily.sh

# 6. Non-regression
python3 /home/sebastian/personal-ai/scripts/non_regression_gate.py
```

## ZASADY
- Connection pool: get_pg_connection(), nigdy raw connect
- SQL parameterized, nigdy f-string
- structlog, nigdy print() w produkcji
- Daty absolutne YYYY-MM-DD
