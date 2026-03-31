#!/usr/bin/env python3
"""Check Anthropic API health and alert if extraction is failing."""
import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
import zoneinfo
from app.db.cost_tracker import log_anthropic_cost
import structlog

load_dotenv(Path(__file__).parent.parent / ".env")

CET = zoneinfo.ZoneInfo('Europe/Warsaw')
logger = structlog.get_logger(__name__)
ALERT_FLAG = Path("/tmp/gilbertus_credit_alert_sent")

def send_alert(msg):
    """Send WhatsApp alert via OpenClaw."""
    # Don't spam - only send once per hour
    if ALERT_FLAG.exists():
        age = datetime.now(tz=CET).timestamp() - ALERT_FLAG.stat().st_mtime
        if age < 3600:
            logger.info("Alert suppressed (sent within last hour)")
            return
    try:
        subprocess.run(
            ["openclaw", "message", "--to", "+48505441635", msg],
            capture_output=True, timeout=10
        )
        ALERT_FLAG.touch()
        logger.info(f"ALERT SENT: {msg}")
    except Exception as e:
        logger.info(f"Failed to send alert: {e}")

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
        logger.info("Anthropic API: OK")
        log_anthropic_cost('claude-haiku-4-5', 'check_api_credits', r.usage)
        # Clear alert flag if it was set
        ALERT_FLAG.unlink(missing_ok=True)
        return True
    except (anthropic.BadRequestError, anthropic.PermissionDeniedError, anthropic.AuthenticationError) as e:
        if any(kw in str(e).lower() for kw in ('credit balance', 'quota', 'insufficient')):
            send_alert("🚨 Gilbertus ALERT: Anthropic credit balance too low! Extraction stopped. Doładuj: console.anthropic.com")
            logger.warning(f"Anthropic CREDIT ERROR: {e}")
        else:
            logger.warning(f"Anthropic API error: {e}")
        return False
    except Exception as e:
        logger.error(f"Anthropic check failed: {e}")
        # Don't alert on transient network errors
        return False

def check_extraction_recent():
    """Check if extraction ran successfully in last 2 hours."""
    from app.db.postgres import get_pg_connection
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT MAX(created_at) FROM events WHERE created_at > NOW() - INTERVAL '2 hours'
                """)
                rows = cur.fetchall()
                last_event = rows[0][0] if rows else None
                if last_event:
                    logger.info(f"Recent extraction activity: {last_event}")
                    return True
                else:
                    logger.warning("No extraction activity in last 2 hours")
                    return False
    except Exception as e:
        logger.error(f"DB check failed: {e}")
        return True  # Don't alert on DB errors

if __name__ == "__main__":
    logger.info("=== Credit check started ===")
    anthropic_ok = check_anthropic()
    if not anthropic_ok:
        sys.exit(1)
    extraction_ok = check_extraction_recent()
    if not extraction_ok:
        send_alert('⚠️ Gilbertus: No extraction activity in 2 hours!')
    logger.info("=== Credit check passed ===" if extraction_ok else "=== Credit check passed (extraction stale) ===")
    sys.exit(0 if (anthropic_ok and extraction_ok) else 1)
