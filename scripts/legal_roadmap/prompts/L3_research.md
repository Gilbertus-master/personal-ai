Jesteś ekspertem od AI-powered legal research. Zadanie: L3 — AI Research + Analysis Engine + Risk Assessor.

REPO: /home/sebastian/personal-ai

## KONTEKST
Moduł Legal & Compliance jest w budowie. Istnieją:
- app/analysis/legal_compliance.py — orchestrator z tabelami, CRUD, obligation wrappers
- app/analysis/legal/obligation_tracker.py — deadline monitoring
- 10 tabel DB, 9 areas, API endpointy /compliance/*
- Qdrant vector DB z chunkami (kolekacja gilbertus_chunks, embedding text-embedding-3-large 3072-dim)

## CO MUSISZ ZROBIĆ

### 1. Utwórz app/analysis/legal/regulatory_scanner.py

```python
"""
Regulatory Scanner — skanuje ingested data w poszukiwaniu zmian regulacyjnych.

Szuka w chunkach keywords: rozporządzenie, nowelizacja, Dz.U., obwieszczenie,
koncesja, URE, UODO, AML, KNF, CSRD, ESRS, zmiana przepisów, regulacja, ustawa,
dyrektywa, compliance, obowiązek, termin, kara, sankcja.

Gdy znajdzie nową regulację → auto-tworzy compliance_matter typu 'new_regulation' lub 'regulation_change'.
"""
from __future__ import annotations

import structlog
log = structlog.get_logger(__name__)

import json
import os
from datetime import datetime, timezone, timedelta
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection
from app.db.cost_tracker import log_anthropic_cost

load_dotenv()

ANTHROPIC_FAST = os.getenv("ANTHROPIC_FAST_MODEL", "claude-haiku-4-5")
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=60.0)

REGULATORY_KEYWORDS = [
    "rozporządzenie", "nowelizacja", "Dz.U.", "dziennik ustaw",
    "obwieszczenie", "koncesja", "URE", "UODO", "GIIF", "KNF",
    "CSRD", "ESRS", "zmiana przepisów", "nowa regulacja", "ustawa",
    "dyrektywa", "compliance", "obowiązek regulacyjny", "kara pieniężna",
    "sankcja", "termin sprawozdawczy", "raportowanie ESG", "AML",
    "przeciwdziałanie praniu", "ochrona danych", "RODO", "GDPR",
]
```

Implementuj:

#### scan_for_regulatory_changes()
```python
def scan_for_regulatory_changes(hours: int = 24) -> dict[str, Any]:
    """Skanuje chunki z ostatnich N godzin pod kątem keywords regulacyjnych.

    1. SELECT chunks WHERE created_at > NOW() - hours AND text ILIKE ANY keyword
    2. Grupuj po document_id
    3. Dla każdej grupy: wywołaj Claude Haiku z promptem:
       'Przeanalizuj tekst. Czy zawiera informację o nowej lub zmienionej regulacji
        prawnej dotyczącej spółki energetycznej? Jeśli tak, zwróć JSON:
        {"is_regulatory": true, "title": "...", "area_code": "URE|RODO|AML|...",
         "matter_type": "new_regulation|regulation_change", "description": "...",
         "source_reference": "Dz.U. ...", "priority": "low|medium|high|critical"}
        Jeśli nie — zwróć {"is_regulatory": false}'
    4. Dla każdego znalezionego → sprawdź czy nie istnieje już matter z podobnym tytułem (dedup)
    5. Jeśli nowy → create_matter() z odpowiednimi parametrami

    Zwraca: {scanned_chunks: N, regulatory_found: N, matters_created: N, details: [...]}
    """
```

#### _chunk_mentions_regulation()
```python
def _chunk_mentions_regulation(text: str) -> bool:
    """Szybki pre-filter: czy tekst zawiera którykolwiek z REGULATORY_KEYWORDS (case-insensitive)."""
```

### 2. Utwórz app/analysis/legal/risk_assessor.py

```python
"""
Risk Assessor — ocena ryzyk compliance z matrycą 5×5.

Likelihood: very_low(1), low(2), medium(3), high(4), very_high(5)
Impact: negligible(1), minor(2), moderate(3), major(4), catastrophic(5)
Risk score = likelihood × impact / 25 (normalized 0-1)

Kolory: 0-0.2 green, 0.2-0.4 yellow, 0.4-0.6 orange, 0.6-0.8 red, 0.8-1.0 critical
"""
from __future__ import annotations

import structlog
log = structlog.get_logger(__name__)

import json
import os
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection
from app.db.cost_tracker import log_anthropic_cost

load_dotenv()

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=120.0)

LIKELIHOOD_MAP = {"very_low": 1, "low": 2, "medium": 3, "high": 4, "very_high": 5}
IMPACT_MAP = {"negligible": 1, "minor": 2, "moderate": 3, "major": 4, "catastrophic": 5}
```

Implementuj:

#### assess_risk_for_matter()
```python
def assess_risk_for_matter(matter_id: int) -> list[dict[str, Any]]:
    """AI-powered risk assessment dla sprawy compliance.

    1. Pobierz matter detail (title, description, legal_analysis, area)
    2. Wywołaj Claude Sonnet z promptem:
       'Jesteś ekspertem od ryzyk prawnych w polskiej spółce energetycznej.
        Dla następującej sprawy compliance zidentyfikuj 3-7 ryzyk.
        Dla każdego podaj: risk_title, risk_description, likelihood (very_low..very_high),
        impact (negligible..catastrophic), current_controls, mitigation_plan.
        Zwróć JSON array.'
    3. Oblicz risk_score = LIKELIHOOD_MAP[l] * IMPACT_MAP[i] / 25.0
    4. INSERT INTO compliance_risk_assessments
    5. Zaktualizuj matter.risk_analysis (JSONB) z summary

    Zwraca listę stworzonych risk assessments.
    """
```

#### get_risk_heatmap()
```python
def get_risk_heatmap() -> dict[str, Any]:
    """Agreguj ryzyka per area_code. Zwraca:
    {areas: [{code, name, risk_count, avg_score, max_score, critical_count}],
     total_risks: N, overall_avg: 0.XX}"""
```

#### list_risks()
```python
def list_risks(area_code: str | None = None, status: str = "open", limit: int = 50) -> list[dict[str, Any]]:
    """Lista ryzyk z filtrami."""
```

### 3. Dodaj research_regulation() i generate_compliance_report() w legal_compliance.py

Na końcu pliku legal_compliance.py (przed if __name__), dodaj:

#### research_regulation()
```python
def research_regulation(matter_id: int, query: str | None = None) -> dict[str, Any]:
    """AI-powered research regulacji dla sprawy.

    1. Pobierz matter (title, description, area, source_regulation)
    2. Wyszukaj w Qdrant semantycznie: query lub matter.title + matter.description
       Użyj: from app.retrieval.retriever import search_chunks
       search_chunks(query_text, top_k=15, source_types=['document','email','pdf'])
    3. Zbierz kontekst z chunks
    4. Wywołaj Claude Sonnet z promptem:
       'Jesteś prawnikiem specjalizującym się w polskim prawie energetycznym.
        Przeanalizuj następujące źródła i odpowiedz na pytanie prawne.

        SPRAWA: {matter.title}
        OPIS: {matter.description}
        OBSZAR: {area.name_pl}
        PYTANIE: {query or "Jakie są obowiązki prawne wynikające z tej regulacji?"}

        ŹRÓDŁA:
        {chunks context}

        Odpowiedz w strukturze:
        1. STRESZCZENIE REGULACJI
        2. OBOWIĄZKI (lista konkretnych obowiązków z podstawą prawną)
        3. TERMINY (jakie terminy obowiązują)
        4. KONSEKWENCJE NIEDOPEŁNIENIA (kary, sankcje)
        5. WYMAGANE DOKUMENTY (jakie dokumenty trzeba przygotować)
        6. REKOMENDACJE (co należy zrobić)

        Bądź konkretny, podawaj artykuły ustaw.'
    5. Zapisz wynik do matter.legal_analysis
    6. Zaktualizuj matter.phase = 'research', status = 'researching'

    Zwraca: {matter_id, legal_analysis, chunks_used: N, model_used}
    """
```

Dla search_chunks użyj istniejącej funkcji:
```python
from app.retrieval.retriever import search_chunks
matches = search_chunks(query_text, top_k=15)
context = "\n\n".join([f"[{m.source_type} {m.created_at}] {m.text[:500]}" for m in matches])
```

Jeśli search_chunks nie jest dostępny w tej formie, użyj Qdrant bezpośrednio:
```python
from qdrant_client import QdrantClient
import openai
# embed query, search qdrant, fetch chunk texts from postgres
```

#### generate_compliance_report()
```python
def generate_compliance_report(matter_id: int) -> dict[str, Any]:
    """Generuje pełny raport compliance na bazie legal_analysis.

    1. Pobierz matter z legal_analysis
    2. Wywołaj Claude Sonnet:
       'Na podstawie analizy prawnej wygeneruj kompletny raport compliance:

        RAPORT COMPLIANCE: {matter.title}

        I. PODSUMOWANIE WYKONAWCZE
        II. OBOWIĄZKI PRAWNE (tabela: obowiązek | podstawa prawna | termin | kara)
        III. ANALIZA RYZYK (likelihood × impact)
        IV. WYMAGANE DOKUMENTY (lista z opisem)
        V. PLAN DZIAŁAŃ (kto | co | kiedy | priorytet)
        VI. PLAN KOMUNIKACJI (kogo poinformować | o czym | kanał | kiedy)
        VII. SZKOLENIA (kto musi przejść jakie szkolenie)
        VIII. REKOMENDACJE

        Format: markdown, po polsku, konkretnie z datami i odpowiedzialnymi.'
    3. Zapisz: matter.obligations_report = raport
    4. Wywołaj assess_risk_for_matter(matter_id) z risk_assessor
    5. Zaktualizuj matter.phase = 'analysis', status = 'analyzed'

    Zwraca: {matter_id, report_length, risks_identified, phase}
    """
```

#### advance_matter_phase() — fazy 1-3
```python
def advance_matter_phase(matter_id: int, force_phase: str | None = None) -> dict[str, Any]:
    """Przesuwa sprawę do następnej fazy.

    Fazy 1-3 (implementowane teraz):
    - initiation → research: wywołaj research_regulation()
    - research → analysis: wywołaj generate_compliance_report()
    - analysis → planning: (placeholder, L4+ doimplementuje)

    Sprawdza prerequisites:
    - research wymaga: matter istnieje, ma description lub source_regulation
    - analysis wymaga: legal_analysis nie jest pusty
    - planning wymaga: obligations_report nie jest pusty

    Zwraca: {matter_id, old_phase, new_phase, status}
    """
```

### 4. Dodaj API endpointy

W app/api/main.py po istniejących /compliance/* endpointach:

```python
@app.post("/compliance/matters/{matter_id}/research")
def compliance_research(matter_id: int, body: dict = {}):
    """Trigger AI research on compliance matter."""
    from app.analysis.legal_compliance import research_regulation
    return research_regulation(matter_id, query=body.get("query"))

@app.post("/compliance/matters/{matter_id}/advance")
def compliance_advance(matter_id: int, body: dict = {}):
    """Advance matter to next phase."""
    from app.analysis.legal_compliance import advance_matter_phase
    return advance_matter_phase(matter_id, force_phase=body.get("force_phase"))

@app.post("/compliance/matters/{matter_id}/report")
def compliance_report(matter_id: int):
    """Generate compliance report for matter."""
    from app.analysis.legal_compliance import generate_compliance_report
    return generate_compliance_report(matter_id)

@app.get("/compliance/risks")
def compliance_risks(area_code: str | None = None, status: str = "open", limit: int = 50):
    """List risk assessments."""
    from app.analysis.legal.risk_assessor import list_risks
    return {"risks": list_risks(area_code=area_code, status=status, limit=limit)}

@app.get("/compliance/risks/heatmap")
def compliance_risk_heatmap():
    """Risk heatmap data."""
    from app.analysis.legal.risk_assessor import get_risk_heatmap
    return get_risk_heatmap()
```

## WERYFIKACJA

```bash
# 1. Import test
python3 -c "
import sys; sys.path.insert(0, '/home/sebastian/personal-ai')
from app.analysis.legal.regulatory_scanner import scan_for_regulatory_changes
from app.analysis.legal.risk_assessor import assess_risk_for_matter, get_risk_heatmap
print('L3 modules: OK')
"

# 2. Regulatory scanner (dry run — skanuje ostatnie 24h)
python3 -c "
import sys; sys.path.insert(0, '/home/sebastian/personal-ai')
from app.analysis.legal.regulatory_scanner import scan_for_regulatory_changes
result = scan_for_regulatory_changes(hours=24)
print(f'Scanned: {result}')
"

# 3. Research test (wymaga istniejącej matter)
python3 -c "
import sys; sys.path.insert(0, '/home/sebastian/personal-ai')
from app.analysis.legal_compliance import create_matter, research_regulation
matter = create_matter('Obowiązki CSRD/ESG dla REH', 'new_regulation', 'ESG',
    'Nowe obowiązki raportowania ESG wg dyrektywy CSRD od 2025', 'high')
print('Matter:', matter)
if matter.get('id'):
    result = research_regulation(matter['id'])
    print(f'Research: analysis length={len(result.get(\"legal_analysis\",\"\"))} chars')
"

# 4. Risk heatmap
python3 -c "
import sys; sys.path.insert(0, '/home/sebastian/personal-ai')
from app.analysis.legal.risk_assessor import get_risk_heatmap
import json
print(json.dumps(get_risk_heatmap(), indent=2, default=str))
"

# 5. Non-regression
python3 /home/sebastian/personal-ai/scripts/non_regression_gate.py
```
