# TASK T5: Anthropic/OpenAI Credit Alert
**Project:** /home/sebastian/personal-ai
**Status file:** /tmp/gilbertus_upgrade/status/T5.done

## Context
Previously the extraction pipeline failed silently with "credit balance too low".
We need proactive alerting before the credit runs out.
The system sends WA alerts via OpenClaw: `openclaw message --to +48505441635 "message"`

## What to do

1. Create /home/sebastian/personal-ai/scripts/check_api_credits.py:

```python
#!/usr/bin/env python3
"""Check Anthropic API health and alert if extraction is failing."""
import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

load_dotenv(Path(__file__).parent.parent / ".env")

LOG_FILE = Path(__file__).parent.parent / "logs/credit_check.log"
ALERT_FLAG = Path("/tmp/gilbertus_credit_alert_sent")

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def send_alert(msg):
    """Send WhatsApp alert via OpenClaw."""
    # Don't spam - only send once per hour
    if ALERT_FLAG.exists():
        age = datetime.now().timestamp() - ALERT_FLAG.stat().st_mtime
        if age < 3600:
            log("Alert suppressed (sent within last hour)")
            return
    try:
        subprocess.run(
            ["openclaw", "message", "--to", "+48505441635", msg],
            capture_output=True, timeout=10
        )
        ALERT_FLAG.touch()
        log(f"ALERT SENT: {msg}")
    except Exception as e:
        log(f"Failed to send alert: {e}")

def check_anthropic():
    """Test Anthropic API with a minimal call."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=15.0)
        r = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=5,
            messages=[{"role": "user", "content": "ok"}]
        )
        log("Anthropic API: OK")
        # Clear alert flag if it was set
        ALERT_FLAG.unlink(missing_ok=True)
        return True
    except anthropic.BadRequestError as e:
        if "credit balance" in str(e).lower():
            send_alert("🚨 Gilbertus ALERT: Anthropic credit balance too low! Extraction stopped. Doładuj: console.anthropic.com")
            log(f"Anthropic CREDIT ERROR: {e}")
        else:
            log(f"Anthropic BadRequest: {e}")
        return False
    except Exception as e:
        log(f"Anthropic check failed: {e}")
        # Don't alert on transient network errors
        return False

def check_extraction_recent():
    """Check if extraction ran successfully in last 2 hours."""
    import psycopg
    try:
        conn_str = f"host={os.getenv('POSTGRES_HOST','127.0.0.1')} port={os.getenv('POSTGRES_PORT','5432')} dbname={os.getenv('POSTGRES_DB','gilbertus')} user={os.getenv('POSTGRES_USER','gilbertus')} password={os.getenv('POSTGRES_PASSWORD','gilbertus')}"
        with psycopg.connect(conn_str) as conn:
            with conn.cursor() as cur:
                # Check if any chunks were processed (via embedding_id) in last 2 hours
                cur.execute("""
                    SELECT COUNT(*) FROM chunks 
                    WHERE embedding_id IS NOT NULL 
                    AND chunk_index = 0
                """)
                # Alternative: check extraction log via events table
                cur.execute("""
                    SELECT MAX(created_at) FROM events WHERE created_at > NOW() - INTERVAL '2 hours'
                """)
                last_event = cur.fetchone()[0]
                if last_event:
                    log(f"Recent extraction activity: {last_event}")
                    return True
                else:
                    log("WARNING: No extraction activity in last 2 hours")
                    return False
    except Exception as e:
        log(f"DB check failed: {e}")
        return True  # Don't alert on DB errors

if __name__ == "__main__":
    log("=== Credit check started ===")
    anthropic_ok = check_anthropic()
    if not anthropic_ok:
        sys.exit(1)
    log("=== Credit check passed ===")
    sys.exit(0)
```

2. Make it executable:
   ```
   chmod +x /home/sebastian/personal-ai/scripts/check_api_credits.py
   ```

3. Test it runs:
   ```
   cd /home/sebastian/personal-ai && .venv/bin/python scripts/check_api_credits.py
   ```
   Should print "Anthropic API: OK"

4. Add to crontab (run every 6 hours):
   ```
   (crontab -l 2>/dev/null; echo "0 */6 * * * cd /home/sebastian/personal-ai && .venv/bin/python scripts/check_api_credits.py >> /home/sebastian/personal-ai/logs/credit_check.log 2>&1") | crontab -
   ```

5. Verify cron was added:
   ```
   crontab -l | grep check_api_credits
   ```

## Completion
```
echo "done" > /tmp/gilbertus_upgrade/status/T5.done
openclaw system event --text "Upgrade T5 done: API credit monitoring active" --mode now
```
