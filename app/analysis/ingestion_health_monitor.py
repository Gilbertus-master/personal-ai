"""
Ingestion Health Monitor — alerts when data sources go stale.

Checks MAX(created_at) per source_type vs configurable thresholds.
If stale → creates alert + sends WhatsApp notification.

Thresholds (hours):
  teams: 24, email: 24, calendar: 48, audio_transcript: 72,
  whatsapp_live: 72, whatsapp: 168
"""
from __future__ import annotations

import structlog
log = structlog.get_logger(__name__)

import os
import subprocess
from datetime import datetime, timezone

from app.db.postgres import get_pg_connection

# Max hours of silence before alert
THRESHOLDS = {
    "teams": 24,
    "email": 24,
    "email_attachment": 24,
    "calendar": 48,
    "audio_transcript": 72,
    "whatsapp_live": 72,
    "whatsapp": 168,
    "document": 168,
    "spreadsheet": 720,  # monthly
    "chatgpt": 720,
}


def check_ingestion_health() -> list[dict]:
    """Check freshness of all sources, return list of stale ones."""
    stale = []
    now = datetime.now(timezone.utc)

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT s.source_type, MAX(d.created_at) as last_doc
                FROM sources s
                JOIN documents d ON d.source_id = s.id
                WHERE d.created_at IS NOT NULL
                GROUP BY s.source_type
            """)
            for source_type, last_doc in cur.fetchall():
                threshold_hours = THRESHOLDS.get(source_type, 168)
                if last_doc is None:
                    continue
                hours_ago = (now - last_doc).total_seconds() / 3600
                if hours_ago > threshold_hours:
                    stale.append({
                        "source_type": source_type,
                        "last_doc": last_doc.isoformat(),
                        "hours_ago": round(hours_ago, 1),
                        "threshold_hours": threshold_hours,
                    })

    return stale


def save_ingestion_alerts(stale_sources: list[dict]) -> int:
    """Save stale source alerts to alerts table (with 24h dedup)."""
    saved = 0
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            for src in stale_sources:
                title = f"Stale source: {src['source_type']} ({src['hours_ago']:.0f}h)"
                # Dedup: one alert per source per 24h
                cur.execute("""
                    SELECT id FROM alerts
                    WHERE alert_type = 'ingestion_stale'
                      AND title LIKE %s
                      AND created_at > NOW() - INTERVAL '24 hours'
                    LIMIT 1
                """, (f"Stale source: {src['source_type']}%",))
                if cur.fetchall():
                    continue

                cur.execute("""
                    INSERT INTO alerts (alert_type, severity, title, description, evidence, is_active)
                    VALUES (%s, %s, %s, %s, %s, TRUE)
                """, (
                    "ingestion_stale",
                    "high" if src["hours_ago"] > src["threshold_hours"] * 2 else "medium",
                    title,
                    f"Source '{src['source_type']}' last document: {src['last_doc']}. "
                    f"Threshold: {src['threshold_hours']}h, actual: {src['hours_ago']:.0f}h.",
                    f'{{"source_type": "{src["source_type"]}", "hours_ago": {src["hours_ago"]}, '
                    f'"threshold_hours": {src["threshold_hours"]}}}',
                ))
                saved += 1
        conn.commit()
    return saved


def notify_stale_sources(stale_sources: list[dict]) -> None:
    """Send WhatsApp alert for stale sources."""
    if not stale_sources:
        return

    lines = [f"\u26a0\ufe0f *Ingestion Health Alert* — {len(stale_sources)} stale source(s):"]
    for src in stale_sources:
        lines.append(f"  \u2022 {src['source_type']}: {src['hours_ago']:.0f}h ago (limit: {src['threshold_hours']}h)")
    lines.append("\nSprawdz logi sync lub uruchom recznie.")

    try:
        subprocess.run(
            ["openclaw", "message", "send",
             "--channel", "whatsapp",
             "--target", os.getenv("WA_TARGET", "+48505441635"),
             "--message", "\n".join(lines)],
            capture_output=True, text=True, timeout=30,
        )
        log.info("ingestion_health_alert_sent", count=len(stale_sources))
    except Exception as e:
        log.error("ingestion_health_notify_failed", error=str(e))


def run_ingestion_health_check(notify: bool = True) -> dict:
    """Full health check pipeline."""
    stale = check_ingestion_health()
    if stale:
        log.warning("ingestion_stale_sources", count=len(stale), sources=[s["source_type"] for s in stale])
        saved = save_ingestion_alerts(stale)
        if notify and saved > 0:
            notify_stale_sources(stale)
        return {"status": "stale", "stale_count": len(stale), "alerts_saved": saved, "sources": stale}
    else:
        log.info("ingestion_health_ok")
        return {"status": "ok", "stale_count": 0}


if __name__ == "__main__":
    import json
    result = run_ingestion_health_check()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
