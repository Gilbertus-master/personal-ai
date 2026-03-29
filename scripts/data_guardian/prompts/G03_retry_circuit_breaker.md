# G03: Retry + backoff + circuit breaker na WSZYSTKICH external API calls

## PROBLEM
Żaden external API call nie ma retry. Jeśli Anthropic/OpenAI/Graph API/Plaud/Whisper zwróci 429/500/timeout — call crashuje i dane są stracone.

## TASK

### Krok 1: Zainstaluj tenacity
```bash
cd /home/sebastian/personal-ai && .venv/bin/pip install tenacity
```

### Krok 2: Stwórz moduł resilience
Stwórz `/home/sebastian/personal-ai/app/core/resilience.py`:

```python
"""
Resilience patterns: retry with backoff, circuit breaker, timeout wrapper.
Used by ALL external API calls in Gilbertus.
"""
import time
import threading
from functools import wraps
from typing import Callable
import structlog
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type, before_sleep_log
)

log = structlog.get_logger("resilience")

# --- Retry decorator for external APIs ---
def with_retry(
    max_attempts: int = 3,
    min_wait: float = 2.0,
    max_wait: float = 30.0,
    retryable_exceptions: tuple = (Exception,),
):
    """Retry with exponential backoff + jitter."""
    ...

# --- Circuit Breaker per source ---
class CircuitBreaker:
    """Per-source circuit breaker. States: closed → open → half_open → closed.

    - closed: normal operation
    - open: after N failures, reject calls for cooldown_seconds
    - half_open: allow 1 probe call, if success → closed, if fail → open
    """
    def __init__(self, name: str, failure_threshold: int = 5, cooldown_seconds: int = 300):
        ...

    def call(self, func: Callable, *args, **kwargs):
        """Execute func through circuit breaker."""
        ...

# --- Global circuit breakers (one per external service) ---
BREAKERS = {
    "graph_api": CircuitBreaker("graph_api", failure_threshold=5, cooldown_seconds=300),
    "anthropic": CircuitBreaker("anthropic", failure_threshold=3, cooldown_seconds=120),
    "openai": CircuitBreaker("openai", failure_threshold=3, cooldown_seconds=120),
    "plaud_api": CircuitBreaker("plaud_api", failure_threshold=5, cooldown_seconds=600),
    "whisper": CircuitBreaker("whisper", failure_threshold=3, cooldown_seconds=60),
    "openclaw": CircuitBreaker("openclaw", failure_threshold=5, cooldown_seconds=300),
}
```

### Krok 3: Wrap WSZYSTKIE external calls

Znajdź i owrapuj:
```bash
grep -rn "requests\.\|httpx\.\|client\.messages\.\|client\.embeddings\." /home/sebastian/personal-ai/app/ --include="*.py" | grep -v ".pyc" | head -40
```

**Minimum do owrapowania:**
1. `app/ingestion/graph_api/email_sync.py` — Graph API calls → `BREAKERS["graph_api"]`
2. `app/ingestion/graph_api/teams_sync.py` — Graph API calls
3. `app/ingestion/graph_api/calendar_sync.py` — Graph API calls
4. `app/ingestion/plaud_sync.py` — Plaud API calls → `BREAKERS["plaud_api"]`
5. `app/ingestion/whisper_transcribe.py` — Whisper local → `BREAKERS["whisper"]`
6. `app/retrieval/answering.py` — Anthropic calls → `BREAKERS["anthropic"]`
7. `app/retrieval/index_chunks.py` — OpenAI embeddings → `BREAKERS["openai"]`
8. `app/extraction/entities.py` + `events.py` — Anthropic extraction
9. `app/analysis/legal/document_generator.py` — Anthropic
10. Każdy inny plik robiący HTTP call na zewnątrz

### Krok 4: Dodaj health status circuit breakerów do `/status` endpoint
```python
# W app/api/main.py → GET /status
from app.core.resilience import BREAKERS
breaker_status = {name: {"state": b.state, "failures": b.failure_count} for name, b in BREAKERS.items()}
```

### Krok 5: Weryfikacja
```bash
# Test retry
.venv/bin/python3 -c "
from app.core.resilience import with_retry, BREAKERS
print('Circuit breakers:', {k: v.state for k, v in BREAKERS.items()})
print('All closed — OK')
"

# Upewnij się że build przechodzi
.venv/bin/python3 -c "from app.core.resilience import BREAKERS; print('OK')"
```

## WAŻNE
- NIE dodawaj retry do operacji DB (to nie external API)
- Retry TYLKO na retryable errors (429, 500, 502, 503, 504, timeout, ConnectionError)
- NIE retryuj 401/403 (auth errors — to wymaga human interaction)
- Circuit breaker cooldown: 5 min dla Graph/Plaud, 2 min dla Anthropic/OpenAI, 1 min dla Whisper
- Loguj KAŻDY retry i circuit break (structlog)
