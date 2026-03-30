# PRIVATE — nie eksponować w Omnius ani publicznym API
#
# Gottman-inspired Relationship Health Scorer
# Based on: 5:1 positivity ratio, Four Horsemen, emotional safety
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from app.db.postgres import get_pg_connection

log = structlog.get_logger("rel.health")
CET = timezone(timedelta(hours=1))

# Gottman's Four Horsemen of the Apocalypse
FOUR_HORSEMEN = {"criticism", "contempt", "defensiveness", "stonewalling"}

# Weights for health score components (sum = 10)
WEIGHTS = {
    "positivity_ratio": 2.5,     # Gottman 5:1
    "four_horsemen": 2.0,        # absence of destructive patterns
    "initiative_balance": 1.5,   # reciprocity
    "communication_quality": 2.0,
    "emotional_safety": 2.0,
}


def compute_health_score(partner_id: int = 1, days: int = 7) -> dict:
    """Oblicz health score 1-10 na podstawie dostępnych danych."""
    since = datetime.now(CET) - timedelta(days=days)

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # 1. Positivity ratio z eventów
            cur.execute(
                """SELECT
                       COUNT(*) FILTER (WHERE sentiment > 0) as positive,
                       COUNT(*) FILTER (WHERE sentiment < 0) as negative,
                       COUNT(*) as total
                   FROM rel_events
                   WHERE partner_id = %s AND created_at >= %s""",
                (partner_id, since),
            )
            ev = cur.fetchone()
            positive, negative, total = ev[0], ev[1], ev[2]

            # 2. Four Horsemen — szukaj conflict events z keywords
            cur.execute(
                """SELECT COUNT(DISTINCT event_type) as horsemen_count
                   FROM rel_events
                   WHERE partner_id = %s AND created_at >= %s
                         AND event_type = 'conflict'""",
                (partner_id, since),
            )
            conflict_count = cur.fetchall()[0][0]

            # 3. Active alerts (pattern threshold exceeded)
            cur.execute(
                """SELECT COUNT(*) FROM rel_patterns
                   WHERE partner_id = %s AND active = TRUE
                         AND occurrences >= alert_threshold""",
                (partner_id,),
            )
            alert_count = cur.fetchall()[0][0]

            # 4. Latest metrics
            cur.execute(
                """SELECT communication_quality, positivity_ratio,
                          initiative_balance, emotional_safety, vulnerability_level
                   FROM rel_metrics
                   WHERE partner_id = %s
                   ORDER BY week_start DESC LIMIT 1""",
                (partner_id,),
            )
            metrics = cur.fetchone()

    # --- Score calculation ---
    components = {}

    # Positivity ratio (target: 5:1 = perfect 10)
    if total > 0:
        ratio = positive / max(negative, 1)
        pr_score = min(ratio / 5.0, 1.0) * 10
    elif metrics and metrics[1]:
        ratio = float(metrics[1])
        pr_score = min(ratio / 5.0, 1.0) * 10
    else:
        ratio = 0
        pr_score = 5.0  # neutral default
    components["positivity_ratio"] = {"score": round(pr_score, 1), "ratio": round(ratio, 2)}

    # Four Horsemen penalty
    horsemen_score = max(10 - conflict_count * 2.5, 0)
    components["four_horsemen"] = {"score": round(horsemen_score, 1), "conflicts": conflict_count}

    # Initiative balance (from metrics, 1.0 = perfect)
    if metrics and metrics[2] is not None:
        ib = float(metrics[2])
        ib_score = max(0, 10 - abs(ib - 1.0) * 5)
    else:
        ib = None
        ib_score = 5.0
    components["initiative_balance"] = {"score": round(ib_score, 1), "balance": ib}

    # Communication quality (from metrics)
    if metrics and metrics[0]:
        cq_score = float(metrics[0])
    else:
        cq_score = 5.0
    components["communication_quality"] = {"score": round(cq_score, 1)}

    # Emotional safety (from metrics)
    if metrics and metrics[3]:
        es_score = float(metrics[3])
    else:
        es_score = 5.0
    components["emotional_safety"] = {"score": round(es_score, 1)}

    # Weighted average
    weighted_sum = (
        components["positivity_ratio"]["score"] * WEIGHTS["positivity_ratio"]
        + components["four_horsemen"]["score"] * WEIGHTS["four_horsemen"]
        + components["initiative_balance"]["score"] * WEIGHTS["initiative_balance"]
        + components["communication_quality"]["score"] * WEIGHTS["communication_quality"]
        + components["emotional_safety"]["score"] * WEIGHTS["emotional_safety"]
    )
    total_weight = sum(WEIGHTS.values())
    raw_score = weighted_sum / total_weight

    # Alert penalty: -0.5 per active alert
    penalty = alert_count * 0.5
    final_score = max(1.0, min(10.0, raw_score - penalty))

    result = {
        "health_score": round(final_score, 1),
        "components": components,
        "alerts_active": alert_count,
        "penalty": penalty,
        "period_days": days,
        "events_in_period": total,
    }

    log.info("rel.health.scored", score=result["health_score"], events=total, alerts=alert_count)
    return result
