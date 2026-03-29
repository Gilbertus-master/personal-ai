# PRIVATE — nie eksponować w Omnius ani publicznym API
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from app.db.postgres import get_pg_connection

log = structlog.get_logger("rel.patterns")
CET = timezone(timedelta(hours=1))


def get_active_patterns(partner_id: int = 1) -> list[dict]:
    """Pobierz aktywne wzorce do monitorowania."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, pattern_name, pattern_type, description,
                          detection_hint, last_seen, occurrences, alert_threshold, active
                   FROM rel_patterns
                   WHERE partner_id = %s AND active = TRUE
                   ORDER BY pattern_type, pattern_name""",
                (partner_id,),
            )
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            for r in rows:
                if r.get("last_seen"):
                    r["last_seen"] = str(r["last_seen"])
            return rows


def mark_pattern_seen(pattern_id: int) -> dict:
    """Oznacz pattern jako zaobserwowany. Inkrementuje licznik."""
    now = datetime.now(CET)
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE rel_patterns
                   SET last_seen = %s, occurrences = occurrences + 1
                   WHERE id = %s
                   RETURNING pattern_name, occurrences, alert_threshold""",
                (now, pattern_id),
            )
            row = cur.fetchone()
            conn.commit()
            if not row:
                return {"error": "Pattern not found"}

            name, occ, threshold = row
            alert = occ >= threshold
            log.info("rel.pattern.seen", pattern_id=pattern_id, occurrences=occ, alert=alert)
            return {
                "pattern_name": name,
                "occurrences": occ,
                "alert_threshold": threshold,
                "alert": alert,
                "message": f"⚠️ ALERT: '{name}' widziany {occ}x (próg: {threshold})" if alert else f"'{name}' widziany {occ}x",
            }


def get_alerts(partner_id: int = 1) -> list[dict]:
    """Pobierz wzorce, które przekroczyły próg alertu."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, pattern_name, pattern_type, description,
                          occurrences, alert_threshold, last_seen
                   FROM rel_patterns
                   WHERE partner_id = %s AND active = TRUE
                         AND occurrences >= alert_threshold
                   ORDER BY occurrences DESC""",
                (partner_id,),
            )
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            for r in rows:
                if r.get("last_seen"):
                    r["last_seen"] = str(r["last_seen"])
            return rows


def create_pattern(
    partner_id: int,
    pattern_name: str,
    description: str,
    pattern_type: str = "warning",
    detection_hint: str | None = None,
    alert_threshold: int = 3,
) -> int:
    """Utwórz nowy wzorzec do monitorowania."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO rel_patterns
                   (partner_id, pattern_name, pattern_type, description, detection_hint, alert_threshold)
                   VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
                (partner_id, pattern_name, pattern_type, description, detection_hint, alert_threshold),
            )
            pid = cur.fetchone()[0]
            conn.commit()
            log.info("rel.pattern.created", pattern_id=pid)
            return pid
