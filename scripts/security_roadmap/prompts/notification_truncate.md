Zadanie: M3 — Truncate danych w notyfikacjach WhatsApp.

REPO: /home/sebastian/personal-ai

PROBLEM:
app/orchestrator/action_pipeline.py — _notify_proposal() wysyła pełną treść draftu
(body maila, opisy ticketów) w WhatsApp. Potencjalny leak danych wrażliwych.

IMPLEMENTACJA:
W app/orchestrator/action_pipeline.py w funkcji _notify_proposal():

1. Ogranicz params['body'] do 150 znaków w notyfikacji:
   if params.get("body"):
       body_preview = params['body'][:150]
       if len(params['body']) > 150:
           body_preview += "...[pełna treść po zatwierdzeniu]"
       msg_parts.append(f"\n---\n{body_preview}\n---")

2. Nie pokazuj pełnych adresów email w powiadomieniu (tylko domenę):
   if params.get("to"):
       to_display = params['to']
       if '@' in to_display:
           user, domain = to_display.split('@', 1)
           to_display = f"{user[:3]}***@{domain}"
       msg_parts.append(f"\nDo: {to_display}")

3. Dodaj max długość całej notyfikacji WA: 800 znaków.

WERYFIKACJA:
python3 -c "
import sys; sys.path.insert(0, '/home/sebastian/personal-ai')
# Sprawdź że funkcja istnieje i można ją zaimportować
from app.orchestrator.action_pipeline import _notify_proposal
print('notification_truncate: OK')
"
python3 /home/sebastian/personal-ai/scripts/non_regression_gate.py
