Jesteś ekspertem od reliability. Zadanie: H2 — Budget check fail-safe.

REPO: /home/sebastian/personal-ai

PROBLEM:
app/db/cost_tracker.py — check_budget() zwraca ok=True gdy DB niedostępna.
Jeden niedziałający Postgres = brak limitu kosztów API.

IMPLEMENTACJA:
W app/db/cost_tracker.py w funkcji check_budget():

1. Ustaw timeout 2s na połączenie DB:
   Dodaj na początku try bloku:
   import signal

   Owiń get_pg_connection() w timeout:
   Użyj threading.Timer lub socket timeout w psycopg.

   Najprostsze rozwiązanie — sprawdź czas PRZED i PO:
   import time
   t_start = time.time()
   # ... wywołanie DB ...
   if time.time() - t_start > 2.0:
       return {"ok": False, "reason": "budget check timeout", ...}

2. W bloku except Exception: zmień z:
   return {"ok": True, "reason": "budget check unavailable", ...}
   na:
   log.error("budget_check_db_error", error=str(e))
   return {"ok": False, "reason": f"budget check failed: {str(e)[:50]}",
           "spend_usd": 0.0, "limit_usd": 0.0}

3. Dodaj osobną funkcję is_budget_check_healthy() → bool
   która robi szybki SELECT 1 do sprawdzenia czy DB działa.
   Używana przez /health endpoint.

UWAGA: NIE zmieniaj logiki samych limitów — tylko error handling.

WERYFIKACJA:
python3 -c "
import sys; sys.path.insert(0, '/home/sebastian/personal-ai')
from app.db.cost_tracker import check_budget
result = check_budget('retrieval.answering')
print('Budget check result:', result.get('ok'), result.get('reason',''))
"
python3 /home/sebastian/personal-ai/scripts/non_regression_gate.py
