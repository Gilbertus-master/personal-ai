Jesteś ekspertem od audytu. Zadanie: H5 — Audit trail z tożsamością.

REPO: /home/sebastian/personal-ai

PROBLEM:
ask_runs nie zapisuje kto pyta — brak caller_ip, channel_key w tabeli.
Brak możliwości śledzenia skąd przyszedł request.

IMPLEMENTACJA:
1. Migracja DB:
   docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -c "
   ALTER TABLE ask_runs
     ADD COLUMN IF NOT EXISTS caller_ip TEXT,
     ADD COLUMN IF NOT EXISTS channel_key TEXT;
   CREATE INDEX IF NOT EXISTS idx_ask_runs_channel ON ask_runs (channel_key);
   "

2. W app/api/main.py w funkcji ask():
   Pobierz IP z request:
   caller_ip = request.client.host if request.client else None
   channel_key = f"{request.channel or 'api'}:{request.session_id or 'anonymous'}"

3. Przekaż do persist_ask_run_best_effort():
   persist_ask_run_best_effort(
       ...,
       caller_ip=caller_ip,
       channel_key=channel_key,
   )

4. Zaktualizuj create_ask_run() i persist_ask_run_best_effort()
   w app/db/runtime_persistence.py aby przyjmowały i zapisywały nowe pola.

WERYFIKACJA:
curl -s -X POST http://127.0.0.1:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"query": "test audit trail", "answer_length": "short", "channel": "test", "session_id": "audit-test"}'
docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -c "
  SELECT id, caller_ip, channel_key FROM ask_runs ORDER BY id DESC LIMIT 3;"
python3 /home/sebastian/personal-ai/scripts/non_regression_gate.py
