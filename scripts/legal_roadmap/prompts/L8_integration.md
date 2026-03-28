Jesteś ekspertem od integracji systemów. Zadanie: L8 — Integration + Crons + E2E Test + Non-regression.

REPO: /home/sebastian/personal-ai

## KONTEKST
Moduł Legal & Compliance jest kompletny. Wszystkie pliki istnieją: legal_compliance.py, obligation_tracker.py, regulatory_scanner.py, risk_assessor.py, document_generator.py, training_manager.py, communication_planner.py, compliance_reporter.py. MCP tool gilbertus_legal zarejestrowany. Authority categories zaseedowane. Morning brief zintegrowany.

## CO MUSISZ ZROBIĆ

### 1. Cross-reference contracts ↔ compliance_matters

W app/analysis/legal_compliance.py dodaj:

```python
def check_contracts_compliance() -> dict[str, Any]:
    """Sprawdź kontrakty pod kątem compliance.

    1. Pobierz aktywne/expiring kontrakty z contracts table
    2. Dla kontraktów z contract_type zawierającym 'dane', 'personal', 'processing', 'przetwarzanie':
       - Sprawdź czy istnieje compliance_matter z contract_id = contract.id
       - Jeśli nie → create_matter('Przegląd compliance kontraktu: {title}', 'contract_review', 'RODO', contract_id=id)
    3. Dla kontraktów wygasających w ciągu 30 dni:
       - Sprawdź czy istnieje compliance_deadline dla tego kontraktu
       - Jeśli nie → utwórz deadline
    4. Zwróć: {contracts_checked, matters_created, deadlines_created}
    """
```

### 2. Alert integration

W app/analysis/legal_compliance.py dodaj:

```python
def create_compliance_alerts() -> dict[str, Any]:
    """Tworzy alerty compliance w tabeli alerts.

    1. Deadlines overdue → alert severity='high'
    2. Deadlines < 3 dni → alert severity='medium'
    3. Non-compliant obligations → alert severity='high'
    4. Stale documents > 30 dni → alert severity='low'
    5. Overdue trainings → alert severity='medium'

    Dedup: sprawdź czy alert z tym samym title już istnieje i jest active.

    INSERT INTO alerts (alert_type, severity, title, description, evidence, active)
    VALUES ('compliance', severity, title, desc, evidence_json, TRUE)

    Zwróć: {alerts_created}
    """
```

Dodaj wywołanie create_compliance_alerts() na końcu run_daily_compliance_check().

### 3. Rozszerz run_daily_compliance_check()

W legal_compliance.py zaktualizuj:

```python
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
```

### 4. Dodaj run_monthly_verification()

```python
def run_monthly_verification() -> dict[str, Any]:
    """Cron monthly: pełna weryfikacja compliance wszystkich obszarów.

    Per area:
    1. Sprawdź compliance_status każdego obligation
    2. Sprawdź czy dokumenty są aktualne (review_due)
    3. Sprawdź czy szkolenia są ukończone
    4. Wygeneruj area_report
    5. Jeśli area.last_reviewed_at + review_frequency_days < TODAY:
       - Oznacz area status='pending_review'
       - Utwórz matter 'Przegląd obszaru {area.name_pl}'

    Wyślij summary na WhatsApp.
    Zwróć: {areas_reviewed, issues_found, matters_created}
    """
```

### 5. Zarejestruj wszystkie 5 cronów w crontab

Uruchom poniższe komendy (sprawdź najpierw czy nie istnieją):

```bash
# Sprawdź obecny crontab
crontab -l > /tmp/current_crontab.txt

# Dodaj compliance crony (jeśli nie istnieją):

# 1. Daily compliance check (6:15 CET — przed morning brief o 7:00)
grep -q "legal_compliance_daily" /tmp/current_crontab.txt || \
  (crontab -l; echo "15 6 * * * cd /home/sebastian/personal-ai && bash scripts/legal_compliance_daily.sh >> logs/legal_compliance.log 2>&1") | crontab -

# 2. Regulatory scanner (co 6h)
grep -q "regulatory_scanner" /tmp/current_crontab.txt || \
  (crontab -l; echo "0 */6 * * * cd /home/sebastian/personal-ai && .venv/bin/python -c \"from app.analysis.legal.regulatory_scanner import scan_for_regulatory_changes; scan_for_regulatory_changes()\" >> logs/regulatory_scanner.log 2>&1") | crontab -

# 3. Weekly compliance report (niedziela 19:00 — przed weekly synthesis o 20:00)
grep -q "compliance_weekly" /tmp/current_crontab.txt || \
  (crontab -l; echo "0 19 * * 0 cd /home/sebastian/personal-ai && .venv/bin/python -c \"from app.analysis.legal.compliance_reporter import generate_weekly_report; generate_weekly_report()\" >> logs/compliance_weekly.log 2>&1") | crontab -

# 4. Monthly verification (1-szy miesiąca 8:00)
grep -q "run_monthly_verification" /tmp/current_crontab.txt || \
  (crontab -l; echo "0 8 1 * * cd /home/sebastian/personal-ai && .venv/bin/python -c \"from app.analysis.legal_compliance import run_monthly_verification; run_monthly_verification()\" >> logs/compliance_monthly.log 2>&1") | crontab -

# 5. Training deadline check (pon-pią 9:00)
grep -q "check_training_deadlines" /tmp/current_crontab.txt || \
  (crontab -l; echo "0 9 * * 1-5 cd /home/sebastian/personal-ai && .venv/bin/python -c \"from app.analysis.legal.training_manager import check_training_deadlines; check_training_deadlines()\" >> logs/training_check.log 2>&1") | crontab -
```

### 6. Zaktualizuj CLAUDE.md

W sekcji "Automatyzacja" zmień "37 cron jobów" na "42 cron jobów" i dodaj:
```
compliance daily 6:15, regulatory scan co 6h, compliance weekly Sun 19:00,
compliance monthly 1st 8:00, training check Mon-Fri 9:00
```

W sekcji "MCP Tools" dodaj:
```
**Legal (1):** `gilbertus_legal` (24 akcje: dashboard, areas, matters, create_matter, research, report, obligations, deadlines, documents, generate_doc, trainings, risks, raci, verify, ...)
```

Zmień "43 MCP tools" na "44 MCP tools" w sekcji ZASADA ZERO.

### 7. E2E Test

Uruchom pełny test lifecycle:

```bash
python3 -c "
import sys, json
sys.path.insert(0, '/home/sebastian/personal-ai')
from app.analysis.legal_compliance import (
    create_matter, research_regulation, generate_compliance_report,
    advance_matter_phase, generate_document, get_compliance_dashboard,
    list_matters, run_daily_compliance_check
)

print('=== E2E Legal Compliance Test ===')

# 1. Create matter
matter = create_matter(
    'Wdrożenie RODO w REH — aktualizacja 2026',
    'policy_update', 'RODO',
    'Aktualizacja polityki ochrony danych osobowych i procedur RODO w Respect Energy Holding',
    'high'
)
print(f'1. Matter created: #{matter[\"id\"]} — {matter[\"title\"]}')
mid = matter['id']

# 2. Research
research = research_regulation(mid, 'Jakie są aktualne obowiązki RODO dla spółki energetycznej w Polsce?')
print(f'2. Research: {len(research.get(\"legal_analysis\", \"\"))} chars analysis')

# 3. Report
report = generate_compliance_report(mid)
print(f'3. Report: {report.get(\"risks_identified\", 0)} risks identified')

# 4. Advance to planning
plan = advance_matter_phase(mid)
print(f'4. Phase: {plan.get(\"old_phase\")} → {plan.get(\"new_phase\")}')

# 5. Dashboard
dashboard = get_compliance_dashboard()
print(f'5. Dashboard: {dashboard.get(\"open_matters\", 0)} open matters, {dashboard.get(\"areas_count\", 0)} areas')

# 6. Daily check
daily = run_daily_compliance_check()
print(f'6. Daily check: {daily}')

print('\\n=== E2E Test Complete ===')
"
```

### 8. Verify API health

```bash
systemctl --user restart gilbertus-api || true
sleep 5

# Health check
curl -s http://127.0.0.1:8000/health

# Dashboard
curl -s http://127.0.0.1:8000/compliance/dashboard | python3 -m json.tool

# Areas
curl -s http://127.0.0.1:8000/compliance/areas | python3 -m json.tool

# Matters
curl -s http://127.0.0.1:8000/compliance/matters | python3 -m json.tool

# Deadlines
curl -s http://127.0.0.1:8000/compliance/deadlines | python3 -m json.tool
```

## WERYFIKACJA KOŃCOWA

```bash
# 1. Cron count (powinno być 42)
crontab -l | grep -v "^#" | grep -v "^$" | wc -l

# 2. MCP tool count (powinno być 44)
grep -oP 'name="gilbertus_\w+"|name="omnius_\w+"' mcp_gilbertus/server.py | sort -u | wc -l

# 3. Table count
docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';"

# 4. Compliance tables exist
docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -c "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'compliance_%' ORDER BY tablename;"

# 5. Non-regression gate
python3 /home/sebastian/personal-ai/scripts/non_regression_gate.py

# 6. API smoke test
curl -s http://127.0.0.1:8000/compliance/dashboard | python3 -c "import sys,json; d=json.load(sys.stdin); print('Dashboard OK:', 'areas_count' in str(d) or 'areas' in str(d))"
```
