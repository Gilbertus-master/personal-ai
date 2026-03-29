# G06: Extraction pipeline watchdog — stall detection + auto-restart

## CEL
Monitoruj extraction pipeline (entities, events, commitments). Jeśli backlog rośnie lub workers stoją → auto-restart.

## TASK

### 1. Stwórz `app/guardian/extraction_watchdog.py`

Sprawdza co 30 minut:
- Ile chunków czeka na entity extraction: `chunks LEFT JOIN entities LEFT JOIN chunks_entity_checked`
- Ile chunków czeka na event extraction: analogicznie
- Ile chunków czeka na embeddings: `chunks WHERE embedding_id IS NULL`
- Ile worker processes działa: `ps aux | grep extraction`
- Czy backlog ROŚNIE (porównanie z poprzednim check)

### 2. Thresholds i akcje
```python
THRESHOLDS = {
    "embedding_backlog": {"warning": 200, "critical": 1000, "action": "restart_embed"},
    "entity_backlog": {"warning": 500, "critical": 2000, "action": "restart_extract"},
    "event_backlog": {"warning": 500, "critical": 2000, "action": "restart_extract"},
    "backlog_growing": {"warning": True, "action": "alert"},
    "zero_workers": {"critical": True, "action": "start_workers"},
    "zombie_workers": {"warning": True, "action": "kill_restart"},
}
```

### 3. Auto-restart
- Embedding: `nohup .venv/bin/python3 -m app.retrieval.index_chunks --batch-size 50 &`
- Extraction: `nohup bash scripts/turbo_extract.sh 3000 12 claude-haiku-4-5-20251001 &`
- Kill zombie: `kill -9` processes older than 60 min z extraction w nazwie

### 4. Stall detection
Jeśli backlog nie zmniejsza się przez 4 godziny mimo running workers → „stall"
- Diagnoza: sprawdź logi extraction, sprawdź Anthropic circuit breaker, sprawdź budżet API
- Auto-fix: restart workers z mniejszym batch (1000 zamiast 3000)
- Jeśli wciąż stall → alert: „Extraction stalled for 4h. Backlog: {n}. Check Anthropic API limits."

### 5. Cron
```
*/30 * * * * cd /home/sebastian/personal-ai && .venv/bin/python3 -m app.guardian.extraction_watchdog >> logs/extraction_watchdog.log 2>&1
```

## WAŻNE
- NIE uruchamiaj nowych workers jeśli stare jeszcze działają (check PID)
- Flock na restart żeby nie uruchamiać podwójnie
- Max 24 workers total (12 entity + 12 event) — nie więcej
