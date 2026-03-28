Jesteś ekspertem od compliance training management. Zadanie: L5 — Training Manager + Delegation Integration.

REPO: /home/sebastian/personal-ai

## KONTEKST
Moduł Legal & Compliance jest w budowie. Istnieją: legal_compliance.py, obligation_tracker.py, regulatory_scanner.py, risk_assessor.py, document_generator.py. Tabele DB (w tym compliance_trainings, compliance_training_records), API endpointy /compliance/*.

Istniejące systemy do reużycia:
- app/orchestrator/delegation_chain.py: delegate_task(assignee, title, description, deadline, priority) → tworzy delegation_tasks z eskalacją
- app/orchestrator/communication.py: _send_whatsapp_to(), send_and_log() → notyfikacje
- people table: osoby z id, first_name, last_name, slug

## CO MUSISZ ZROBIĆ

### 1. Utwórz app/analysis/legal/training_manager.py

```python
"""
Training Manager — tworzenie, przypisywanie i tracking szkoleń compliance.

Workflow:
1. Tworzenie szkolenia (na bazie matter/obligation)
2. Generacja materiałów (via document_generator jeśli potrzebne)
3. Przypisanie do osób (wg target_audience)
4. Notyfikacja (WhatsApp/email)
5. Tracking completions
6. Reminders dla overdue
7. Raportowanie (kto przeszedł, kto nie)
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

Implementuj:

#### create_training()
```python
def create_training(
    title: str,
    area_code: str,
    matter_id: int | None = None,
    training_type: str = "mandatory",
    content_summary: str | None = None,
    target_audience: list[str] | None = None,  # ['all_employees', 'management', 'traders', 'it']
    deadline: str | None = None,  # YYYY-MM-DD
    generate_material: bool = False,
) -> dict[str, Any]:
    """Tworzy szkolenie compliance.

    1. Pobierz area_id z compliance_areas
    2. INSERT INTO compliance_trainings
    3. Jeśli generate_material=True i matter_id podany:
       from app.analysis.legal.document_generator import generate_document
       doc = generate_document(matter_id, 'training_material', title=f'Szkolenie: {title}')
       UPDATE compliance_trainings SET content_document_id = doc['document_id']
    4. Jeśli target_audience podano → wywołaj assign_training_to_audience()
    5. Zwróć: {training_id, title, status, assigned_count}
    """
```

#### assign_training_to_audience()
```python
def assign_training_to_audience(training_id: int, target_audience: list[str]) -> int:
    """Przypisuje szkolenie do osób na podstawie audience.

    Mapping audience → people:
    - 'all_employees': SELECT id FROM people WHERE status != 'inactive' (lub po prostu wszyscy)
    - 'management': SELECT id FROM people WHERE slug IN (lista managerów — hardcode lub z employee_work_profiles)
    - 'traders': analogicznie
    - 'it': analogicznie
    - Konkretne imię: SELECT id FROM people WHERE first_name || ' ' || last_name ILIKE '%name%'

    Dla każdej osoby:
    1. INSERT INTO compliance_training_records (training_id, person_id, status='assigned')
    2. Stwórz delegation_task via:
       from app.orchestrator.delegation_chain import delegate_task
       delegate_task(
           assignee=person_name,
           title=f'Szkolenie compliance: {training_title}',
           description=f'Ukończ szkolenie: {training_title}. Deadline: {deadline}',
           deadline=deadline,
           priority='medium',
       )
       Zapisz delegation_task_id w compliance_training_records
    3. Zaktualizuj training_record.status = 'notified', notified_at = NOW()

    Zwraca liczbę przypisanych osób.
    """
```

#### complete_training()
```python
def complete_training(training_id: int, person_id: int, score: float | None = None) -> dict[str, Any]:
    """Oznacza szkolenie jako ukończone dla osoby.

    1. UPDATE compliance_training_records SET status='completed', completed_at=NOW(), score=score
    2. Jeśli powiązany delegation_task_id → UPDATE delegation_tasks SET status='completed'
    3. Sprawdź czy wszystkie osoby ukończyły → jeśli tak: UPDATE compliance_trainings SET status='completed'
    4. Zwróć: {training_id, person_id, status, all_completed}
    """
```

#### get_training_status()
```python
def get_training_status(training_id: int) -> dict[str, Any]:
    """Status szkolenia: ile osób assigned, notified, completed, overdue.

    SELECT tr.status, COUNT(*), p.first_name, p.last_name
    FROM compliance_training_records tr
    JOIN people p ON p.id = tr.person_id
    WHERE tr.training_id = %s
    GROUP BY tr.status, p.first_name, p.last_name

    Zwraca: {training_id, title, total, completed, overdue, pending, people: [...]}
    """
```

#### check_training_deadlines()
```python
def check_training_deadlines() -> dict[str, Any]:
    """Cron: sprawdź terminy szkoleń.

    1. Szkolenia z deadline < TODAY i status != 'completed':
       - Oznacz training_records jako 'overdue' gdzie status IN ('assigned','notified','started')
    2. Szkolenia z deadline w ciągu 7 dni:
       - Wyślij reminder WhatsApp dla osób ze status 'assigned' lub 'notified'
       - Format: '📚 *Reminder: Szkolenie compliance*\n{title}\nTermin: {deadline}\nStatus: nie ukończone'
    3. Zwróć: {checked, overdue_marked, reminders_sent}
    """
```

#### list_trainings()
```python
def list_trainings(status: str | None = None, area_code: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """Lista szkoleń z filtrami i progress info."""
```

### 2. Dodaj wrappers w legal_compliance.py

```python
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
```

### 3. Rozszerz advance_matter_phase() — fazy 6-7

W legal_compliance.py, w advance_matter_phase() dodaj:
```python
# approval → training:
#   Sprawdź czy matter.action_plan zawiera kroki z training
#   Jeśli tak: create_training() dla każdego kroku szkoleniowego
#   Jeśli nie: skip do communication

# training → communication:
#   Sprawdź czy wszystkie trainings dla matter są completed lub nie ma trainings
#   Jeśli tak: przesuń do communication
```

### 4. API endpointy

```python
@app.get("/compliance/trainings")
def compliance_trainings(status: str | None = None, area_code: str | None = None, limit: int = 20):
    from app.analysis.legal_compliance import list_trainings
    return {"trainings": list_trainings(status=status, area_code=area_code, limit=limit)}

@app.get("/compliance/trainings/{training_id}/status")
def compliance_training_status(training_id: int):
    from app.analysis.legal_compliance import get_training_status
    return get_training_status(training_id)

@app.post("/compliance/trainings")
def create_compliance_training(body: dict):
    from app.analysis.legal_compliance import create_training
    return create_training(**{k: v for k, v in body.items() if v is not None})

@app.post("/compliance/trainings/{training_id}/complete")
def complete_compliance_training(training_id: int, body: dict):
    from app.analysis.legal.training_manager import complete_training
    return complete_training(training_id, body["person_id"], body.get("score"))
```

## WERYFIKACJA

```bash
python3 -c "
import sys; sys.path.insert(0, '/home/sebastian/personal-ai')
from app.analysis.legal.training_manager import create_training, check_training_deadlines, list_trainings
print('training_manager: OK')
"

python3 -c "
import sys; sys.path.insert(0, '/home/sebastian/personal-ai')
from app.analysis.legal_compliance import create_training
result = create_training(
    title='Szkolenie RODO dla pracowników',
    area_code='RODO',
    training_type='mandatory',
    content_summary='Podstawy RODO: przetwarzanie danych, prawa podmiotów, obowiązki administratora',
    target_audience=['all_employees'],
    deadline='2026-06-30',
)
print('Training created:', result)
"

python3 /home/sebastian/personal-ai/scripts/non_regression_gate.py
```
