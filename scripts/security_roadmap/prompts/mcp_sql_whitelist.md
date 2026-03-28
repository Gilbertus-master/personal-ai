Jesteś ekspertem od database security. Zadanie: H7 — MCP _sql() whitelist tabel.

REPO: /home/sebastian/personal-ai

PROBLEM:
mcp_gilbertus/server.py — helper _sql() wykonuje dowolne SELECT.
Jeśli prompt injection w MCP query → SQL do dowolnej tabeli Gilbertusa.

IMPLEMENTACJA:
W mcp_gilbertus/server.py znajdź funkcję _sql():

1. Dodaj ALLOWED_TABLES whitelist przed funkcją:
   ALLOWED_SQL_TABLES = {
       "api_costs", "ask_runs", "ask_run_matches", "sessions",
       "action_items", "delegation_tasks", "wa_tasks",
       "events", "entities", "documents", "chunks", "summaries",
       "alerts", "insights", "decisions", "opportunities",
       "relationships", "people", "commitments",
       "conversation_windows", "code_executions",
       "response_feedback", "cost_budgets",
   }

2. Zaktualizuj _sql() aby sprawdzała query:
   import re

   def _sql(query: str, params=None):
       # Wyciągnij nazwy tabel z query (proste regex, nie parser SQL)
       table_names = set(re.findall(
           r'\bFROM\s+(\w+)|\bJOIN\s+(\w+)|\bINTO\s+(\w+)|\bUPDATE\s+(\w+)',
           query, re.IGNORECASE
       ))
       table_names = {t for group in table_names for t in group if t}

       unknown = table_names - ALLOWED_SQL_TABLES
       if unknown:
           raise ValueError(f"SQL access denied: unknown tables {unknown}")

       # ... reszta bez zmian

3. Ogranicz _sql() do SELECT only:
   query_stripped = query.strip().upper()
   if not query_stripped.startswith("SELECT") and not query_stripped.startswith("WITH"):
       raise ValueError("_sql() allows only SELECT/WITH queries")

WERYFIKACJA:
python3 -c "
import sys; sys.path.insert(0, '/home/sebastian/personal-ai')
# Sprawdź że whitelist działa przez import
print('MCP sql whitelist ready')
"
python3 /home/sebastian/personal-ai/scripts/non_regression_gate.py
