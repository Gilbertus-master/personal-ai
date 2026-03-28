Zadanie: M1 — CORS policy middleware.

REPO: /home/sebastian/personal-ai

IMPLEMENTACJA:
W app/api/main.py dodaj CORSMiddleware zaraz po `app = FastAPI(...)`:

from fastapi.middleware.cors import CORSMiddleware

CORS_ORIGINS = os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
CORS_ORIGINS = [o.strip() for o in CORS_ORIGINS if o.strip()]
if not CORS_ORIGINS:
    # Dev default: tylko localhost
    CORS_ORIGINS = ["http://localhost:3000", "http://localhost:8080",
                    "http://127.0.0.1:3000", "http://127.0.0.1:8080"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key", "Authorization"],
    max_age=3600,
)

W .env dodaj komentarz:
# CORS_ALLOWED_ORIGINS=http://localhost:3000  # Dodaj jeśli masz frontend

WERYFIKACJA:
systemctl --user restart gilbertus-api
curl -s -H "Origin: http://evil.com" http://127.0.0.1:8000/health -v 2>&1 | grep -i "access-control"
# Nie powinno być Access-Control-Allow-Origin dla evil.com
python3 /home/sebastian/personal-ai/scripts/non_regression_gate.py
