import os
from fastapi import Request
from fastapi.responses import JSONResponse

GILBERTUS_API_KEY = os.getenv("GILBERTUS_API_KEY", "")

# Endpointy zawsze dostępne bez klucza (health checks, internal calls)
PUBLIC_PATHS = {
    "/health", "/status", "/docs", "/openapi.json", "/redoc",
    "/plaud/webhook",  # Plaud webhook ma własną auth
}

# Źródła zawsze zaufane (wewnętrzne wywołania)
TRUSTED_ORIGINS = {"127.0.0.1", "localhost", "::1"}


async def api_key_middleware(request: Request, call_next):
    """
    Soft API Key enforcement:
    - Jeśli GILBERTUS_API_KEY nie jest ustawiony w .env → przepuszczaj wszystko (dev mode)
    - Jeśli ustawiony → wymagaj X-API-Key header lub ?api_key= param
    - Wewnętrzne wywołania z 127.0.0.1 → zawsze przepuszczaj
    - Public paths → zawsze przepuszczaj
    """
    # Dev mode — brak klucza w env → auth wyłączona
    if not GILBERTUS_API_KEY:
        return await call_next(request)

    # Public paths
    if request.url.path in PUBLIC_PATHS:
        return await call_next(request)

    # Zaufane IP (wewnętrzne wywołania Gilbertusa do siebie)
    client_ip = request.client.host if request.client else ""
    if client_ip in TRUSTED_ORIGINS:
        return await call_next(request)

    # Sprawdź klucz
    provided = (
        request.headers.get("X-API-Key")
        or request.headers.get("Authorization", "").removeprefix("Bearer ")
        or request.query_params.get("api_key", "")
    )

    if provided != GILBERTUS_API_KEY:
        return JSONResponse(
            status_code=401,
            content={"error": "Unauthorized", "detail": "Valid X-API-Key header required"},
        )

    return await call_next(request)
