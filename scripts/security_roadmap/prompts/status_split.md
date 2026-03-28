Zadanie: M2 — Rozdzielenie /health od /status.

REPO: /home/sebastian/personal-ai

PROBLEM:
/status zwraca szczegółowe info o infrastrukturze (ścieżki, crony, wersje serwisów).
Powinno być chronione API key. /health powinno być zawsze publiczne.

IMPLEMENTACJA:
1. W app/api/main.py przy endpoincie /status:
   Dodaj opcjonalną ochronę gdy GILBERTUS_API_KEY jest ustawiony:

   @app.get("/status")
   def system_status(request: Request) -> dict[str, Any]:
       # Chroń /status gdy API key jest skonfigurowany
       api_key = os.getenv("GILBERTUS_API_KEY", "")
       if api_key:
           provided = request.headers.get("X-API-Key", "")
           client_ip = request.client.host if request.client else ""
           if client_ip not in {"127.0.0.1", "localhost", "::1"} and provided != api_key:
               from fastapi import HTTPException
               raise HTTPException(status_code=401, detail="X-API-Key required for /status")
       ...

2. Upewnij się że /health jest minimalistyczny i zawsze publiczny:
   @app.get("/health")
   def health():
       return {"status": "ok", "service": "gilbertus-api"}

   NIE zwracaj w /health: wersji bibliotek, ścieżek, detali infrastruktury.

WERYFIKACJA:
curl -s http://127.0.0.1:8000/health
# Powinno zwrócić {"status": "ok"}
python3 /home/sebastian/personal-ai/scripts/non_regression_gate.py
