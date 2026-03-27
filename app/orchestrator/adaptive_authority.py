"""
Adaptive Authority — learns from approval patterns and suggests level changes.

Analyzes: approval rate per action category over time.
If approval rate >= 95% over 20+ actions -> suggest upgrading authority level.
If rejection rate >= 30% -> suggest downgrading.

Cron: monthly (1st of month, part of communication_effectiveness.sh)
"""
from __future__ import annotations

import os
import subprocess

import structlog

log = structlog.get_logger(__name__)

from typing import Any

from app.db.postgres import get_pg_connection
from app.orchestrator.authority import get_authority_level

OPENCLAW_BIN = os.getenv("OPENCLAW_BIN", "openclaw")
WA_TARGET = os.getenv("WA_TARGET", "+48505441635")

# Authority level names for display
LEVEL_NAMES = {
    0: "inform (just do it)",
    1: "execute + report",
    2: "quick approval",
    3: "full proposal",
    4: "never alone",
}


# ================================================================
# Core functions
# ================================================================

def analyze_approval_patterns(days: int = 90) -> list[dict[str, Any]]:
    """Analyze approval patterns per action category with trend analysis.

    Returns list of category stats with approval rates and trends.
    """
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    al.action_category,
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE al.approved = TRUE) as approved,
                    COUNT(*) FILTER (WHERE al.approved = FALSE) as rejected,
                    AVG(al.approval_time_seconds) FILTER (WHERE al.approved) as avg_approval_time
                FROM authority_log al
                WHERE al.created_at > NOW() - make_interval(days => %s)
                  AND al.approval_requested = TRUE
                GROUP BY al.action_category
                HAVING COUNT(*) >= 5
                ORDER BY COUNT(*) FILTER (WHERE al.approved)::numeric / COUNT(*) DESC
            """, (days,))
            rows = cur.fetchall()

            # Trend analysis: compare first half vs second half of period
            half_days = days // 2
            cur.execute("""
                SELECT
                    al.action_category,
                    CASE WHEN al.created_at > NOW() - make_interval(days => %s)
                         THEN 'recent' ELSE 'older' END as period,
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE al.approved = TRUE) as approved
                FROM authority_log al
                WHERE al.created_at > NOW() - make_interval(days => %s)
                  AND al.approval_requested = TRUE
                GROUP BY al.action_category, period
            """, (half_days, days))
            trend_rows = cur.fetchall()

    # Build trend map
    trends: dict[str, dict[str, Any]] = {}
    for cat, period, total, approved in trend_rows:
        if cat not in trends:
            trends[cat] = {}
        rate = approved / total if total > 0 else 0.0
        trends[cat][period] = {"total": total, "approved": approved, "rate": round(rate, 2)}

    patterns = []
    for row in rows:
        cat, total, approved, rejected, avg_time = row
        rate = approved / total if total > 0 else 0.0

        # Determine trend
        cat_trend = trends.get(cat, {})
        older_rate = cat_trend.get("older", {}).get("rate", 0)
        recent_rate = cat_trend.get("recent", {}).get("rate", 0)

        if recent_rate > older_rate + 0.1:
            trend = "improving"
        elif recent_rate < older_rate - 0.1:
            trend = "declining"
        else:
            trend = "stable"

        patterns.append({
            "action_category": cat,
            "total": total,
            "approved": approved,
            "rejected": rejected,
            "approval_rate": round(rate, 2),
            "avg_approval_time_seconds": int(avg_time) if avg_time else None,
            "trend": trend,
            "older_rate": older_rate,
            "recent_rate": recent_rate,
        })

    log.info("approval_patterns_analyzed", categories=len(patterns))
    return patterns


def generate_authority_suggestions() -> list[dict[str, Any]]:
    """Generate suggestions for authority level changes based on approval patterns.

    Rules:
    - approval_rate >= 95% over 20+ actions -> suggest upgrading (lower level number)
    - approval_rate < 70% over 10+ actions -> suggest downgrading (higher level number)
    """
    patterns = analyze_approval_patterns(days=90)

    suggestions = []
    for category in patterns:
        rate = category["approval_rate"]
        total = category["total"]
        cat_name = category["action_category"]

        current = get_authority_level(cat_name)
        current_level = current.get("level", 2)

        if rate >= 0.95 and total >= 20:
            if current_level > 0:
                suggestions.append({
                    "category": cat_name,
                    "current_level": current_level,
                    "current_level_name": LEVEL_NAMES.get(current_level, str(current_level)),
                    "suggested_level": current_level - 1,
                    "suggested_level_name": LEVEL_NAMES.get(current_level - 1, str(current_level - 1)),
                    "direction": "upgrade",
                    "approval_rate": rate,
                    "total_actions": total,
                    "trend": category["trend"],
                    "reason": f"{rate:.0%} approval rate over {total} actions",
                })
        elif rate < 0.70 and total >= 10:
            if current_level < 4:
                suggestions.append({
                    "category": cat_name,
                    "current_level": current_level,
                    "current_level_name": LEVEL_NAMES.get(current_level, str(current_level)),
                    "suggested_level": current_level + 1,
                    "suggested_level_name": LEVEL_NAMES.get(current_level + 1, str(current_level + 1)),
                    "direction": "downgrade",
                    "approval_rate": rate,
                    "total_actions": total,
                    "trend": category["trend"],
                    "reason": f"Only {rate:.0%} approval — increase oversight",
                })

    log.info("authority_suggestions_generated", count=len(suggestions))
    return suggestions


def notify_authority_suggestions() -> None:
    """Send WhatsApp notification with authority level suggestions."""
    suggestions = generate_authority_suggestions()

    if not suggestions:
        log.info("no_authority_suggestions")
        return

    lines = ["*Sugestie poziomu autonomii*", ""]

    upgrades = [s for s in suggestions if s["direction"] == "upgrade"]
    downgrades = [s for s in suggestions if s["direction"] == "downgrade"]

    for s in upgrades:
        lines.append(
            f"UP {s['category']}: {s['approval_rate']:.0%} approval ({s['total_actions']} akcji)"
        )
        lines.append(
            f"   Obecny: poziom {s['current_level']} ({s['current_level_name']})"
        )
        lines.append(
            f"   Sugestia: poziom {s['suggested_level']} ({s['suggested_level_name']})"
        )
        lines.append("")

    for s in downgrades:
        lines.append(
            f"DOWN {s['category']}: {s['approval_rate']:.0%} approval ({s['total_actions']} akcji)"
        )
        lines.append(
            f"   Obecny: poziom {s['current_level']} ({s['current_level_name']})"
        )
        lines.append(
            f"   Sugestia: poziom {s['suggested_level']} ({s['suggested_level_name']})"
        )
        lines.append("")

    lines.append("Odpowiedz: authority [category] [level]")

    message = "\n".join(lines)

    try:
        subprocess.run(
            [OPENCLAW_BIN, "message", "send", "--channel", "whatsapp",
             "--target", WA_TARGET, "--message", message],
            capture_output=True, text=True, timeout=30,
        )
        log.info("authority_suggestions_sent", count=len(suggestions))
    except Exception as exc:
        log.error("authority_suggestions_send_failed", error=str(exc))


def run_adaptive_authority() -> dict[str, Any]:
    """Main pipeline: analyze -> generate suggestions -> notify. Return summary."""
    patterns = analyze_approval_patterns(days=90)
    suggestions = generate_authority_suggestions()

    if suggestions:
        notify_authority_suggestions()

    upgrades = [s for s in suggestions if s["direction"] == "upgrade"]
    downgrades = [s for s in suggestions if s["direction"] == "downgrade"]

    result = {
        "categories_analyzed": len(patterns),
        "total_suggestions": len(suggestions),
        "upgrades": len(upgrades),
        "downgrades": len(downgrades),
        "suggestions": suggestions,
        "notified": len(suggestions) > 0,
    }

    log.info("adaptive_authority_complete", **{k: v for k, v in result.items() if k != "suggestions"})
    return result
