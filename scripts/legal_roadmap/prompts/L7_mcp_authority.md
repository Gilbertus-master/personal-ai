Jesteś ekspertem od MCP tools i systemu authority. Zadanie: L7 — MCP Tool + Authority Integration + Morning Brief.

REPO: /home/sebastian/personal-ai

## KONTEKST
Moduł Legal & Compliance jest kompletny funkcjonalnie. Istnieją: legal_compliance.py (orchestrator z wszystkimi wrapper functions), obligation_tracker.py, regulatory_scanner.py, risk_assessor.py, document_generator.py, training_manager.py, communication_planner.py, compliance_reporter.py. 10 tabel DB, ~20 API endpointów /compliance/*.

## CO MUSISZ ZROBIĆ

### 1. Zarejestruj gilbertus_legal MCP tool w mcp_gilbertus/server.py

Znajdź sekcję `@server.list_tools()` i dodaj nowy Tool (wzoruj się na gilbertus_process_intel):

```python
Tool(
    name="gilbertus_legal",
    description="Legal & Compliance Orchestrator: zarządzanie obowiązkami prawnymi, "
                "sprawami compliance, dokumentami, terminami, szkoleniami, ryzykami, "
                "komunikacją. Obszary: URE, RODO, AML, KSH, ESG, prawo pracy, podatki.",
    inputSchema={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "dashboard", "areas", "area_detail",
                    "matters", "create_matter", "matter_detail", "advance",
                    "research", "report",
                    "obligations", "overdue",
                    "deadlines", "deadlines_overdue",
                    "documents", "stale_docs", "generate_doc",
                    "trainings", "training_status",
                    "risks", "risk_heatmap",
                    "daily_report", "area_report",
                    "raci", "verify",
                ],
                "default": "dashboard",
                "description": "Akcja do wykonania"
            },
            "matter_id": {"type": "integer", "description": "ID sprawy compliance"},
            "area_code": {"type": "string", "description": "Kod obszaru: URE, RODO, AML, KSH, ESG, LABOR, TAX, CONTRACT, INTERNAL_AUDIT"},
            "query": {"type": "string", "description": "Zapytanie prawne lub opis sprawy"},
            "matter_type": {"type": "string", "description": "Typ sprawy: new_regulation, regulation_change, audit_finding, incident, license_renewal, contract_review, policy_update, training_need"},
            "doc_type": {"type": "string", "description": "Typ dokumentu: policy, procedure, form, internal_regulation, training_material, report"},
            "priority": {"type": "string", "description": "Priorytet: low, medium, high, critical"},
            "days_ahead": {"type": "integer", "description": "Dni do przodu dla terminów (default: 30)"},
            "obligation_type": {"type": "string", "description": "Typ obowiązku: reporting, licensing, documentation, training, audit, notification"},
        },
        "required": ["action"]
    }
),
```

### 2. Dodaj handler w @server.call_tool()

Znajdź sekcję z handlerami (elif name == "gilbertus_*") i dodaj:

```python
elif name == "gilbertus_legal":
    action = arguments.get("action", "dashboard")
    matter_id = arguments.get("matter_id")
    area_code = arguments.get("area_code")
    query = arguments.get("query", "")
    priority = arguments.get("priority", "medium")

    if action == "dashboard":
        r = _api("GET", "/compliance/dashboard")
    elif action == "areas":
        r = _api("GET", "/compliance/areas")
    elif action == "area_detail":
        r = _api("GET", f"/compliance/areas/{area_code or 'URE'}")
    elif action == "matters":
        params = {}
        if area_code: params["area_code"] = area_code
        if arguments.get("priority"): params["priority"] = priority
        r = _api("GET", "/compliance/matters", params=params)
    elif action == "create_matter":
        r = _api("POST", "/compliance/matters", {
            "title": query or "New compliance matter",
            "matter_type": arguments.get("matter_type", "other"),
            "area_code": area_code,
            "description": query,
            "priority": priority,
        })
    elif action == "matter_detail":
        r = _api("GET", f"/compliance/matters/{matter_id}")
    elif action == "advance":
        r = _api("POST", f"/compliance/matters/{matter_id}/advance")
    elif action == "research":
        r = _api("POST", f"/compliance/matters/{matter_id}/research",
                 {"query": query} if query else {})
    elif action == "report":
        r = _api("POST", f"/compliance/matters/{matter_id}/report")
    elif action == "obligations":
        params = {}
        if area_code: params["area_code"] = area_code
        r = _api("GET", "/compliance/obligations", params=params)
    elif action == "overdue":
        r = _api("GET", "/compliance/obligations/overdue")
    elif action == "deadlines":
        days = arguments.get("days_ahead", 30)
        params = {"days_ahead": days}
        if area_code: params["area_code"] = area_code
        r = _api("GET", "/compliance/deadlines", params=params)
    elif action == "deadlines_overdue":
        r = _api("GET", "/compliance/deadlines/overdue")
    elif action == "documents":
        params = {}
        if area_code: params["area_code"] = area_code
        if arguments.get("doc_type"): params["doc_type"] = arguments["doc_type"]
        r = _api("GET", "/compliance/documents", params=params)
    elif action == "stale_docs":
        r = _api("GET", "/compliance/documents/stale")
    elif action == "generate_doc":
        r = _api("POST", "/compliance/documents/generate", {
            "matter_id": matter_id,
            "doc_type": arguments.get("doc_type", "policy"),
            "title": query,
        })
    elif action == "trainings":
        params = {}
        if area_code: params["area_code"] = area_code
        r = _api("GET", "/compliance/trainings", params=params)
    elif action == "training_status":
        r = _api("GET", f"/compliance/trainings/{matter_id}/status")
    elif action == "risks":
        params = {}
        if area_code: params["area_code"] = area_code
        r = _api("GET", "/compliance/risks", params=params)
    elif action == "risk_heatmap":
        r = _api("GET", "/compliance/risks/heatmap")
    elif action == "daily_report":
        r = _api("GET", "/compliance/report/daily")
    elif action == "area_report":
        r = _api("GET", f"/compliance/report/area/{area_code or 'URE'}")
    elif action == "raci":
        params = {}
        if matter_id: params["matter_id"] = matter_id
        if area_code: params["area_code"] = area_code
        r = _api("GET", "/compliance/raci", params=params)
    elif action == "verify":
        from app.analysis.legal_compliance import advance_matter_phase
        r = json.dumps(advance_matter_phase(matter_id, force_phase="verification"),
                       ensure_ascii=False, default=str)
    else:
        r = json.dumps({"error": f"Unknown action: {action}"})
```

### 3. Dodaj do TOOL_GROUPS i ROUTER_KEYWORD_MAP

W TOOL_GROUPS dodaj gilbertus_legal do odpowiedniej grupy:
```python
# Znajdź "business" group i dodaj:
"business": [..., "gilbertus_legal"],
```

W ROUTER_KEYWORD_MAP dodaj keywords:
```python
# Znajdź "business" keywords i dodaj:
"compliance", "legal", "regulacja", "prawo", "prawny", "URE", "RODO", "GDPR",
"AML", "ESG", "CSRD", "koncesja", "obowiązek", "termin compliance",
"szkolenie compliance", "audyt", "ryzyko prawne", "regulamin", "procedura",
"polityka", "kara", "sankcja", "KSH", "sprawozdanie",
```

### 4. Seed 7 authority categories w app/orchestrator/authority.py

Znajdź w _ensure_tables() sekcję z INSERT INTO authority_levels i dodaj:

```python
# Compliance authority categories
('compliance_research', 0, 'Research regulations and analyze — auto', TRUE, FALSE),
('compliance_report', 1, 'Generate compliance report — auto + digest', TRUE, TRUE),
('compliance_action_plan', 3, 'Propose compliance action plan — full proposal', FALSE, TRUE),
('compliance_document', 3, 'Generate internal regulation/policy — full proposal', FALSE, TRUE),
('compliance_training', 1, 'Create and assign compliance training — auto + digest', TRUE, TRUE),
('compliance_communication', 2, 'Send compliance notifications — quick approval', FALSE, TRUE),
('compliance_escalation', 2, 'Escalate non-compliance finding — quick approval', FALSE, TRUE),
```

UWAGA: Sprawdź istniejący format INSERT — prawdopodobnie jest to INSERT ... ON CONFLICT DO NOTHING lub INSERT ... VALUES z wieloma wierszami. Dodaj w tym samym formacie.

### 5. Integracja z morning brief w app/retrieval/morning_brief.py

Znajdź funkcję build_brief_context() lub generate_brief_text() i dodaj sekcję compliance:

Dodaj nową funkcję fetch:
```python
def fetch_compliance_status() -> dict:
    """Fetch compliance data for morning brief."""
    try:
        from app.analysis.legal_compliance import get_compliance_dashboard
        return get_compliance_dashboard()
    except Exception:
        return {}
```

W build_brief_context() dodaj sekcję po istniejących:
```python
# Compliance section
compliance = fetch_compliance_status()
if compliance:
    overdue = compliance.get("overdue_count", 0)
    upcoming = compliance.get("upcoming_deadlines", 0)
    open_matters = compliance.get("open_matters", 0)
    if overdue or upcoming or open_matters:
        parts.append(f"\n=== COMPLIANCE ===")
        if overdue:
            parts.append(f"⚠️ Overdue terminów: {overdue}")
        if upcoming:
            parts.append(f"📅 Nadchodzące terminy (7d): {upcoming}")
        if open_matters:
            parts.append(f"📂 Otwarte sprawy: {open_matters}")
```

W BRIEF_SYSTEM_PROMPT dodaj sekcję 8:
```
8. Compliance (jeśli są dane) — overdue, nadchodzące terminy, otwarte sprawy
```

### 6. WhatsApp commands w app/orchestrator/task_monitor.py

Znajdź funkcję classify_message() i dodaj rozpoznawanie compliance commands:

```python
# W sekcji query commands dodaj:
if text_lower.startswith("compliance"):
    parts = text_lower.split(maxsplit=1)
    sub = parts[1] if len(parts) > 1 else "status"
    if sub in ("status", "dashboard"):
        # Wywołaj get_compliance_dashboard() i wyślij skrót na WA
        pass
    elif sub in ("deadlines", "terminy"):
        # Wywołaj list_deadlines i wyślij
        pass
    elif sub in ("overdue", "zaległe"):
        # Wywołaj get_overdue_obligations
        pass
```

## WERYFIKACJA

```bash
# 1. MCP tool test (sprawdź że tool jest zarejestrowany)
python3 -c "
import sys; sys.path.insert(0, '/home/sebastian/personal-ai')
# Sprawdź że server.py się importuje bez błędów
import mcp_gilbertus.server
print('MCP server import: OK')
"

# 2. Authority categories
docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -c "
SELECT action_category, authority_level, auto_execute
FROM authority_levels
WHERE action_category LIKE 'compliance_%'
ORDER BY authority_level;"

# 3. Sprawdź API po restarcie
systemctl --user restart gilbertus-api || true
sleep 3
curl -s http://127.0.0.1:8000/compliance/dashboard | python3 -m json.tool

# 4. Non-regression
python3 /home/sebastian/personal-ai/scripts/non_regression_gate.py
```
