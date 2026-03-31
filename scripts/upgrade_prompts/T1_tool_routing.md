# TASK T1: Enable Tool Routing
**Project:** /home/sebastian/personal-ai
**Status file:** /tmp/gilbertus_upgrade/status/T1.done
**Log file:** /tmp/gilbertus_upgrade/logs/T1.log

## Context
Gilbertus is a personal AI assistant with a FastAPI backend at /home/sebastian/personal-ai/app/.
The tool router (`app/retrieval/tool_router.py`) already exists and is implemented, but disabled via .env.
Without it, every query searches ALL source types (email, WA, Teams, spreadsheets) regardless of what the question is about.

## What to do

1. Check current .env content:
   ```
   cat /home/sebastian/personal-ai/.env | grep ENABLE_
   ```

2. Add `ENABLE_TOOL_ROUTING=true` to /home/sebastian/personal-ai/.env
   (append after the existing ENABLE_ lines)

3. Verify the tool_router.py exists and looks healthy:
   ```
   head -20 /home/sebastian/personal-ai/app/retrieval/tool_router.py
   ```

4. Verify it's wired in main.py:
   ```
   grep -n "ENABLE_TOOL_ROUTING\|tool_router" /home/sebastian/personal-ai/app/api/main.py | head -5
   ```

5. Restart the API service:
   ```
   systemctl --user restart gilbertus-api
   sleep 5
   systemctl --user status gilbertus-api --no-pager | tail -5
   ```

6. Test that API still responds:
   ```
   curl -s http://127.0.0.1:8000/health
   ```

7. Quick functional test - verify routing works:
   ```
   curl -s -X POST http://127.0.0.1:8000/ask \
     -H 'Content-Type: application/json' \
     -d '{"query": "wiadomosc od Rocha na whatsapp", "answer_length": "short", "debug": true}' \
     | python3 -c "import sys,json; d=json.load(sys.stdin); print('source_types:', d.get('meta',{}).get('source_types_used','not shown'))"
   ```

## Completion
When done, write to status file:
```
echo "done" > /tmp/gilbertus_upgrade/status/T1.done
echo "T1 DONE: ENABLE_TOOL_ROUTING=true added and API restarted" >> /tmp/gilbertus_upgrade/logs/T1.log
```

Then run:
```
openclaw system event --text "Upgrade T1 done: ENABLE_TOOL_ROUTING enabled" --mode now
```
