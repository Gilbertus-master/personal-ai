# G07: Three-tier alert escalation + human interaction

## CEL
Stwórz inteligentny system alertowania który:
- Tier 1 (AUTO-FIX): naprawia sam, loguje, nie przeszkadza człowiekowi
- Tier 2 (INFO): powiadamia via WhatsApp, ale nie wymaga natychmiastowej akcji
- Tier 3 (CRITICAL): wymaga ludzkiej interwencji, powtarza alert aż ktoś zareaguje

## TASK

### 1. Stwórz `app/guardian/alert_manager.py`

```python
"""
Alert Manager — three-tier escalation with dedup, snooze, and acknowledgment.

Tier 1 (AUTO): System naprawił problem samodzielnie. Log only.
  Examples: token refreshed, worker restarted, retry succeeded, DLQ item resolved

Tier 2 (INFO): Problem wykryty, może się sam naprawić. WhatsApp info 1x.
  Examples: source 50% SLA, circuit breaker opened, budget at 80%, backlog growing

Tier 3 (CRITICAL): Wymaga ludzkiej akcji. WhatsApp co 2h aż acknowledge.
  Examples: source > 100% SLA, token expired (can't auto-refresh), disk > 90%,
            DLQ items abandoned, Graph API auth requires re-login
"""

class AlertManager:
    def __init__(self):
        self.dedup_window = 4 * 3600  # 4 hours
        self.critical_repeat = 2 * 3600  # repeat every 2h until ack

    def send(self, tier: int, category: str, title: str,
             message: str, fix_command: str | None = None):
        """Send alert with dedup and escalation."""
        ...

    def acknowledge(self, alert_id: int):
        """Human acknowledged alert — stop repeating."""
        ...
```

### 2. Tabela alertów
```sql
CREATE TABLE IF NOT EXISTS guardian_alerts (
    id BIGSERIAL PRIMARY KEY,
    tier INT NOT NULL CHECK (tier IN (1, 2, 3)),
    category TEXT NOT NULL,  -- source_freshness, token, extraction, budget, dlq, system
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    fix_command TEXT,  -- konkretna komenda do naprawy
    auto_fix_attempted BOOLEAN DEFAULT FALSE,
    auto_fix_result TEXT,
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by TEXT,
    repeat_count INT DEFAULT 0,
    last_sent_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 3. WhatsApp delivery
Użyj istniejącego openclaw:
```python
def _send_whatsapp(message: str):
    subprocess.run([
        "openclaw", "message", "send",
        "--channel", "whatsapp",
        "--target", "+48505441635",
        "--message", message
    ], timeout=30)
```

### 4. Alert templates

**Tier 2 (INFO):**
```
ℹ️ Gilbertus Info
{title}
{message}
```

**Tier 3 (CRITICAL):**
```
🔴 Gilbertus CRITICAL
{title}
{message}

Fix: {fix_command}

Reply "ok" to acknowledge.
```

### 5. Acknowledge via WhatsApp
Stwórz handler w WhatsApp listener: jeśli Sebastian odpowie "ok" na alert → acknowledge.
Lub dodaj API endpoint: `POST /alerts/{id}/acknowledge`

### 6. Alert categories i przykłady
| Category | Tier | Example | Fix |
|---|---|---|---|
| source_freshness | 3 | Email 6h stale, auto-fix failed | `bash scripts/sync_corporate_data.sh` |
| token | 3 | Graph API refresh failed | `.venv/bin/python3 -m app.ingestion.graph_api.auth --reauth` |
| extraction | 2 | Backlog > 2000 chunks | Auto-restart workers |
| budget | 2 | API costs at 85% daily limit | Review usage |
| dlq | 2 | 5 items abandoned in DLQ | `curl localhost:8000/dlq/retry-all -X POST` |
| system | 3 | Postgres disk > 90% | Free disk space |
| system | 1 | Whisper restarted automatically | Log only |

### 7. Cron for critical repeat
```
0 */2 * * * cd /home/sebastian/personal-ai && .venv/bin/python3 -c "from app.guardian.alert_manager import AlertManager; AlertManager().repeat_unacknowledged()" >> logs/alerts.log 2>&1
```

## WAŻNE
- Dedup: ta sama kategoria + tytuł → nie alertuj ponownie przez 4h
- Critical repeat: co 2h AŻ do acknowledge
- Max 5 alertów WhatsApp / godzinę (prevent spam)
- Fix_command MUSI być copy-paste ready
