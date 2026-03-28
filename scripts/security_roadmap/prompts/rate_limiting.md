Jesteś ekspertem od API security. Zadanie: H6 — Rate limiting w app layer.

REPO: /home/sebastian/personal-ai

IMPLEMENTACJA:
1. Zainstaluj slowapi:
   source .venv/bin/activate && pip install slowapi==0.1.*
   Dodaj do requirements.txt: slowapi>=0.1.0

2. W app/api/main.py dodaj rate limiter:

   from slowapi import Limiter, _rate_limit_exceeded_handler
   from slowapi.util import get_remote_address
   from slowapi.errors import RateLimitExceeded

   limiter = Limiter(key_func=get_remote_address)
   app.state.limiter = limiter
   app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

3. Dodaj dekoratory na krytycznych endpointach:

   @app.post("/ask")
   @limiter.limit("30/minute")
   def ask(request: Request, body: AskRequest):
       ...

   @app.post("/evaluate")
   @limiter.limit("5/minute")
   def evaluate(request: Request, req: EvaluateRequest):
       ...

   @app.get("/status")
   @limiter.limit("10/minute")
   def system_status(request: Request):
       ...

   Zastosuj @limiter.limit("30/minute") dla: /ask, /brief, /summary/generate
   Zastosuj @limiter.limit("5/minute") dla: /evaluate, /correlate, /scorecard/*

4. UWAGA: lokalne wywołania z 127.0.0.1 NIE powinny być limitowane.
   Dodaj wyjątek:
   TRUSTED_IPS = {"127.0.0.1", "localhost", "::1"}

   def get_rate_limit_key(request: Request):
       if request.client and request.client.host in TRUSTED_IPS:
           return None  # no rate limit for internal calls
       return get_remote_address(request)

   Użyj get_rate_limit_key zamiast get_remote_address.

WERYFIKACJA:
systemctl --user restart gilbertus-api
curl -s http://127.0.0.1:8000/health  # powinno działać
python3 /home/sebastian/personal-ai/scripts/non_regression_gate.py
