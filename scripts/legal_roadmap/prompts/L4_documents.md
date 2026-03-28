Jesteś ekspertem od automatycznej generacji dokumentów prawnych. Zadanie: L4 — Document Generator + Versioning + Signatures.

REPO: /home/sebastian/personal-ai

## KONTEKST
Moduł Legal & Compliance jest w budowie. Istnieją: legal_compliance.py (orchestrator), obligation_tracker.py, regulatory_scanner.py, risk_assessor.py. Tabele DB, API endpointy /compliance/*.

## CO MUSISZ ZROBIĆ

### 1. Utwórz app/analysis/legal/document_generator.py

```python
"""
Document Generator — AI-powered generacja dokumentów compliance.

Typy dokumentów:
- policy: polityka wewnętrzna (np. Polityka Ochrony Danych Osobowych)
- procedure: procedura (np. Procedura reagowania na incydent RODO)
- form: formularz (np. Rejestr czynności przetwarzania)
- internal_regulation: regulamin wewnętrzny (np. Regulamin pracy zdalnej)
- training_material: materiały szkoleniowe
- report: raport compliance
- risk_assessment: ocena ryzyka (pisemna)
- communication: komunikat do pracowników/interesariuszy

Każdy dokument generowany w języku polskim, z numeracją paragrafów,
nagłówkami sekcji, datą, podpisami, klauzulami.
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

#### generate_document()
```python
def generate_document(
    matter_id: int,
    doc_type: str,
    title: str | None = None,
    template_hint: str | None = None,
    signers: list[dict] | None = None,  # [{"name": "Sebastian Jabłoński", "role": "Prezes Zarządu"}]
    valid_months: int = 12,
) -> dict[str, Any]:
    """Generuje dokument compliance z użyciem AI.

    1. Pobierz matter (title, legal_analysis, obligations_report, area)
    2. Pobierz area detail (key_regulations)
    3. Wybierz system prompt wg doc_type:

    Dla policy/internal_regulation:
    'Jesteś prawnikiem korporacyjnym specjalizującym się w prawie polskim.
     Wygeneruj {doc_type_pl} dla polskiej spółki energetycznej.

     KONTEKST PRAWNY:
     {matter.legal_analysis}

     OBOWIĄZKI:
     {matter.obligations_report}

     WYMAGANIA:
     - Język polski, formalny styl prawniczy
     - Numeracja paragrafów (§1, §2, ...)
     - Sekcje: Postanowienia ogólne, Definicje, [treść merytoryczna],
       Obowiązki, Odpowiedzialność, Postanowienia końcowe
     - Data wejścia w życie: {today}
     - Miejsce na podpisy: {signers}
     - Odwołania do konkretnych aktów prawnych (Dz.U.)
     - Klauzula o przeglądzie dokumentu (co 12 miesięcy)

     Tytuł: {title or auto-generate}
     Spółka: Respect Energy Holding sp. z o.o. / Respect Energy Fuels sp. z o.o.'

    Dla procedure:
    - Dodatkowe sekcje: Cel procedury, Zakres, Schemat postępowania (krok po kroku),
      Osoby odpowiedzialne, Terminy, Dokumentacja, Szkolenia

    Dla form:
    - Format tabelaryczny z polami do wypełnienia
    - Nagłówek z logo/nazwą spółki, data, numer dokumentu

    Dla training_material:
    - Struktura modułowa: cel szkolenia, agenda, treść (z przykładami),
      pytania kontrolne, test wiedzy (5-10 pytań), certyfikat ukończenia

    Dla communication:
    - Format komunikatu: Od, Do, Data, Temat, Treść, Załączniki, Podpis

    4. Wywołaj Claude Sonnet (max_tokens=4000, temperature=0.2)
    5. INSERT INTO compliance_documents z:
       - content_text = wygenerowany tekst
       - version = 1 (lub MAX(version)+1 jeśli istnieje dokument o tym samym tytule)
       - valid_from = today
       - valid_until = today + valid_months months
       - review_due = valid_until - 30 days
       - requires_signature = True jeśli policy/internal_regulation/procedure
       - signers = JSONB array z {name, role, signed_at: null, status: 'pending'}
       - signature_status = 'pending' jeśli requires_signature else 'not_required'
       - status = 'draft'
    6. Zwróć: {document_id, title, doc_type, version, requires_signature, signers, status}
    """
```

#### list_documents()
```python
def list_documents(
    area_code: str | None = None,
    doc_type: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Lista dokumentów compliance z filtrami. JOIN z compliance_areas."""
```

#### get_stale_documents()
```python
def get_stale_documents(days_overdue: int = 0) -> list[dict[str, Any]]:
    """Dokumenty z review_due <= TODAY + days_overdue i status = 'active'.
    Zwraca listę z: id, title, doc_type, area_code, review_due, days_overdue."""
```

#### approve_document()
```python
def approve_document(document_id: int, approved_by: str = "sebastian") -> dict[str, Any]:
    """Zatwierdza dokument: status='approved', approved_by, approved_at=NOW().
    Jeśli poprzednia wersja tego dokumentu istnieje (same title, area) → oznacz jako 'superseded'."""
```

#### sign_document()
```python
def sign_document(document_id: int, signer_name: str) -> dict[str, Any]:
    """Rejestruje podpis elektroniczny. Aktualizuje signers JSONB:
    - Znajdź signer po name w signers array
    - Ustaw signed_at = NOW(), status = 'signed'
    - Jeśli wszyscy podpisali → signature_status = 'signed', status = 'active'
    - Jeśli nie wszyscy → signature_status = 'partially_signed'
    Zwraca: {document_id, signer_name, signature_status, all_signed}"""
```

#### run_document_freshness_check()
```python
def run_document_freshness_check() -> dict[str, Any]:
    """Cron: sprawdź freshness dokumentów.
    1. Znajdź dokumenty z review_due <= TODAY i status='active'
    2. Oznacz je status='pending_review'... nie, lepiej: po prostu zwróć listę
    3. Zwróć: {stale_count, documents: [...]}"""
```

### 2. Dodaj wrapper functions w legal_compliance.py

```python
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
```

Dodaj freshness check do istniejącej sekcji w scripts/legal_compliance_daily.sh:
```bash
# Dopisz na końcu skryptu (przed "Done"):

# 2. Document freshness check
python3 -c "
from app.analysis.legal_compliance import run_document_freshness_check
result = run_document_freshness_check()
print(f'Document freshness: {result}')
"
```

### 3. Rozszerz advance_matter_phase() w legal_compliance.py

Dodaj obsługę faz 4-5:
```python
# W advance_matter_phase(), dodaj elif:
# analysis → planning: generuj action_plan z Claude
# planning → document_generation: oznacz jako gotowe do generacji dokumentów

# Faza planning:
# Wywołaj Claude z: 'Na podstawie raportu compliance wygeneruj action_plan jako JSON array:
#   [{step: N, action: "opis", assignee: "rola/osoba", deadline: "YYYY-MM-DD",
#     document_needed: "policy|procedure|form|none", priority: "low|medium|high|critical"}]'
# Zapisz do matter.action_plan

# Faza document_generation:
# Dla każdego stepu z action_plan gdzie document_needed != 'none':
#   generate_document(matter_id, doc_type=step.document_needed)
```

### 4. API endpointy

```python
@app.get("/compliance/documents")
def compliance_documents(area_code: str | None = None, doc_type: str | None = None,
                          status: str | None = None, limit: int = 50):
    from app.analysis.legal_compliance import list_documents
    return {"documents": list_documents(area_code=area_code, doc_type=doc_type, status=status, limit=limit)}

@app.get("/compliance/documents/stale")
def compliance_stale_documents(days: int = 0):
    from app.analysis.legal_compliance import get_stale_documents
    return {"stale_documents": get_stale_documents(days)}

@app.post("/compliance/documents/generate")
def compliance_generate_document(body: dict):
    from app.analysis.legal_compliance import generate_document
    return generate_document(
        matter_id=body["matter_id"], doc_type=body["doc_type"],
        title=body.get("title"), template_hint=body.get("template_hint"),
        signers=body.get("signers"), valid_months=body.get("valid_months", 12))

@app.post("/compliance/documents/{doc_id}/approve")
def compliance_approve_document(doc_id: int, body: dict = {}):
    from app.analysis.legal.document_generator import approve_document
    return approve_document(doc_id, body.get("approved_by", "sebastian"))

@app.post("/compliance/documents/{doc_id}/sign")
def compliance_sign_document(doc_id: int, body: dict):
    from app.analysis.legal.document_generator import sign_document
    return sign_document(doc_id, body["signer_name"])
```

## WERYFIKACJA

```bash
python3 -c "
import sys; sys.path.insert(0, '/home/sebastian/personal-ai')
from app.analysis.legal.document_generator import generate_document, list_documents, get_stale_documents
print('document_generator: OK')
"

# Test generacji (wymaga matter z legal_analysis)
python3 -c "
import sys; sys.path.insert(0, '/home/sebastian/personal-ai')
from app.analysis.legal_compliance import list_matters
matters = list_matters(limit=1)
if matters:
    mid = matters[0]['id']
    from app.analysis.legal_compliance import generate_document
    result = generate_document(mid, 'policy', title='Polityka Ochrony Danych Osobowych REH')
    print(f'Generated doc #{result.get(\"document_id\")}: {result.get(\"title\")}')
else:
    print('No matters found — create one first')
"

python3 /home/sebastian/personal-ai/scripts/non_regression_gate.py
```
