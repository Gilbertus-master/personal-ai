# G02: Graph API auth hardening — client_credentials + proactive token refresh

## PROBLEM
Microsoft Graph API token przechowywany w `.ms_graph_token.json` wygasa i wymaga ręcznego refresh.
Jeśli refresh_token wygaśnie (90 dni bez użycia) → cały email/Teams sync umiera i wymaga ręcznej reautoryzacji.

## TASK

### Krok 1: Przeczytaj obecny auth
```bash
cat /home/sebastian/personal-ai/app/ingestion/graph_api/auth.py
```

### Krok 2: Wdróż dual-mode auth
System powinien obsługiwać DWA tryby:

**A. Client Credentials flow (preferred for background sync)**
- NIE wymaga refresh token, NIE wymaga interakcji z użytkownikiem
- Wymaga tylko: tenant_id, client_id, client_secret
- Uprawnienia: Application permissions (Mail.Read, Chat.Read, Calendars.Read) — muszą być nadane w Azure AD admin portal
- Token ważny 60 min, automatycznie odnawialny BEZ interakcji

**B. Delegated flow (fallback, current)**
- Wymaga refresh token
- Potrzebny gdy Application permissions nie są dostępne

### Krok 3: Proaktywny token refresh cron
Stwórz skrypt/moduł:
- Co 30 minut: sprawdź czy token wygaśnie w ciągu 15 min → jeśli tak, odśwież
- Loguj każdy refresh: data, status (ok/failed), czas do wygaśnięcia
- Jeśli refresh FAIL → natychmiastowy alert WhatsApp do Sebastiana z instrukcją:
  "Graph API token expired. Run: `cd /home/sebastian/personal-ai && .venv/bin/python3 -m app.ingestion.graph_api.auth --reauth`"
- Dodaj cron:
  `*/30 * * * * cd /home/sebastian/personal-ai && .venv/bin/python3 -m app.ingestion.graph_api.auth --refresh-proactive >> logs/graph_auth.log 2>&1`

### Krok 4: Token health endpoint
Dodaj do API endpoint: `GET /auth/graph/health`
- Zwraca: `{status: "ok"|"expiring"|"expired", expires_in_minutes, last_refresh, flow_type}`
- Integruje się z dashboardem i alertami

### Krok 5: Weryfikacja
```bash
# Test token refresh
.venv/bin/python3 -m app.ingestion.graph_api.auth --status
# Powinno pokazać: token valid, expires_in > 0

# Test email sync po naprawie auth
.venv/bin/python3 -m app.ingestion.graph_api.email_sync --inbox --limit 5
```

## Pliki do modyfikacji
- `/home/sebastian/personal-ai/app/ingestion/graph_api/auth.py`
- Crontab (dodaj proactive refresh)
- `/home/sebastian/personal-ai/app/api/main.py` (dodaj health endpoint)

## WAŻNE
- NIE usuwaj delegated flow — to fallback
- Preferuj client_credentials dla automatycznych sync'ów
- Loguj STRUKTURALNIE (structlog)
- Timeout na każdym call do Microsoft (30s)
