Jesteś ekspertem od security. Zadanie: H4 — Weryfikacja nadawcy w WhatsApp approval.

REPO: /home/sebastian/personal-ai

PROBLEM:
app/orchestrator/task_monitor.py i action_pipeline.py — "tak #49" od kogokolwiek
kto wyśle wiadomość na WhatsApp zatwierdza akcję. Brak weryfikacji sender_phone.

IMPLEMENTACJA:
1. W app/orchestrator/task_monitor.py dodaj stałą:
   AUTHORIZED_SENDERS = set(
       s.strip() for s in
       os.getenv("AUTHORIZED_WA_SENDERS", os.getenv("WA_TARGET", "")).split(",")
       if s.strip()
   )

2. W handle_approval_message() i handle_delegation_command() —
   dodaj parametr sender_phone: str = "" i sprawdzaj:

   def handle_approval_message(text: str, sender_phone: str = "") -> dict | None:
       if AUTHORIZED_SENDERS and sender_phone not in AUTHORIZED_SENDERS:
           log.warning("approval_unauthorized_sender",
                      sender=sender_phone, text=text[:50])
           return None  # odrzuć cicho
       # ... reszta bez zmian

3. W miejscu gdzie handle_approval_message() jest wywoływana —
   przekaż sender_phone z metadanych sesji OpenClaw (jeśli dostępne).
   Jeśli nie można uzyskać sender — przepuść (fail-open dla kompatybilności).

4. W .env dodaj komentarz:
   # AUTHORIZED_WA_SENDERS=+48505441635  # Opcjonalnie: whitelist numerów do aprovalu

WERYFIKACJA:
python3 -c "
import sys, os
os.environ['AUTHORIZED_WA_SENDERS'] = '+48505441635'
sys.path.insert(0, '/home/sebastian/personal-ai')
from app.orchestrator.task_monitor import handle_approval_message
# Nieautoryzowany sender — powinno zwrócić None
result = handle_approval_message('tak #1', sender_phone='+48999000000')
print('Unauthorized sender result:', result)  # powinno być None
"
python3 /home/sebastian/personal-ai/scripts/non_regression_gate.py
