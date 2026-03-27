"""
Authority Framework — graduated autonomy for Gilbertus.

5 levels of authorization:
  Level 0: INFORM — just do it (send insight, generate report, update DB)
  Level 1: EXECUTE_AND_REPORT — do it, then tell Sebastian what you did
  Level 2: QUICK_APPROVAL — send brief WhatsApp, wait for tak/nie
  Level 3: FULL_PROPOSAL — detailed proposal with analysis, wait for decision
  Level 4: NEVER_ALONE — always requires Sebastian's explicit decision

Each action category has a default level. Sebastian can override per category.
System learns from approval patterns and suggests level changes.

Integrates with: action_pipeline.py (before propose/execute decision)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Any

import structlog
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection

log = structlog.get_logger(__name__)

load_dotenv()

OPENCLAW_BIN = os.getenv("OPENCLAW_BIN", "openclaw")
WA_TARGET = os.getenv("WA_TARGET", "+48505441635")

# Authority levels
INFORM = 0          # Just do it
EXECUTE_REPORT = 1  # Do it, then report
QUICK_APPROVAL = 2  # Brief WhatsApp approval
FULL_PROPOSAL = 3   # Detailed proposal
NEVER_ALONE = 4     # Always requires Sebastian


# ================================================================
# Database
# ================================================================

def _ensure_tables():
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS authority_levels (
                    id BIGSERIAL PRIMARY KEY,
                    action_category TEXT NOT NULL UNIQUE,
                    authority_level INT NOT NULL DEFAULT 2
                        CHECK (authority_level BETWEEN 0 AND 4),
                    max_value_pln NUMERIC,
                    description TEXT,
                    auto_execute BOOLEAN NOT NULL DEFAULT FALSE,
                    require_digest BOOLEAN NOT NULL DEFAULT TRUE,
                    created_by TEXT NOT NULL DEFAULT 'system',
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)

            cur.execute("""
                INSERT INTO authority_levels
                    (action_category, authority_level, description, auto_execute, require_digest)
                VALUES
                    ('generate_report', 0, 'Generate any report or analysis', TRUE, FALSE),
                    ('send_insight', 0, 'Send insight or alert to WhatsApp', TRUE, FALSE),
                    ('update_status', 0, 'Update commitment/task status', TRUE, FALSE),
                    ('trigger_sync', 0, 'Trigger data sync', TRUE, FALSE),
                    ('send_email_standing_order', 1, 'Send email within standing order scope', TRUE, TRUE),
                    ('send_teams_standing_order', 1, 'Send Teams msg within standing order scope', TRUE, TRUE),
                    ('create_ticket', 1, 'Create ticket in Omnius', TRUE, TRUE),
                    ('update_commitment', 1, 'Update commitment status', TRUE, TRUE),
                    ('escalate_overdue', 1, 'Escalate overdue commitment to assignee', TRUE, TRUE),
                    ('send_reminder', 1, 'Send follow-up reminder', TRUE, TRUE),
                    ('send_email_new', 2, 'Send email outside standing order', FALSE, TRUE),
                    ('send_teams_new', 2, 'Send Teams msg outside standing order', FALSE, TRUE),
                    ('schedule_meeting', 2, 'Schedule meeting', FALSE, TRUE),
                    ('change_priority', 2, 'Change task/commitment priority', FALSE, TRUE),
                    ('modify_standing_order', 3, 'Create or modify standing order', FALSE, TRUE),
                    ('strategy_recommendation', 3, 'Strategic recommendation', FALSE, TRUE),
                    ('escalate_conflict', 3, 'Escalate interpersonal conflict', FALSE, TRUE),
                    ('contract_action', 3, 'Any contract-related action', FALSE, TRUE),
                    ('financial_decision', 4, 'Any financial decision', FALSE, TRUE),
                    ('personnel_decision', 4, 'Hire/fire/promote/demote', FALSE, TRUE),
                    ('trading_decision', 4, 'Trading strategy change', FALSE, TRUE),
                    ('board_communication', 4, 'Communication with board/shareholders', FALSE, TRUE)
                ON CONFLICT (action_category) DO NOTHING
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS authority_log (
                    id BIGSERIAL PRIMARY KEY,
                    action_category TEXT NOT NULL,
                    authority_level INT NOT NULL,
                    action_description TEXT,
                    auto_executed BOOLEAN DEFAULT FALSE,
                    approval_requested BOOLEAN DEFAULT FALSE,
                    approved BOOLEAN,
                    approval_time_seconds INT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_authority_log_cat
                    ON authority_log(action_category)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_authority_log_created
                    ON authority_log(created_at)
            """)
        conn.commit()


# ================================================================
# Core functions
# ================================================================

def get_authority_level(action_category: str) -> dict[str, Any]:
    """Look up authority level for an action category.

    Returns dict with keys: level, auto_execute, require_digest, max_value_pln.
    Defaults to level 2 (QUICK_APPROVAL) if category not found.
    """
    _ensure_tables()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT authority_level, auto_execute, require_digest, max_value_pln
                   FROM authority_levels WHERE action_category = %s""",
                (action_category,),
            )
            rows = cur.fetchall()

    if not rows:
        log.warning("authority_category_not_found", category=action_category,
                     default_level=QUICK_APPROVAL)
        return {
            "level": QUICK_APPROVAL,
            "auto_execute": False,
            "require_digest": True,
            "max_value_pln": None,
        }

    row = rows[0]
    return {
        "level": row[0],
        "auto_execute": row[1],
        "require_digest": row[2],
        "max_value_pln": float(row[3]) if row[3] is not None else None,
    }


def check_authority(
    action_category: str,
    estimated_value_pln: float = 0,
) -> dict[str, Any]:
    """Check if an action can be auto-executed.

    Returns dict with: authorized (bool), level, action/reason.
    """
    auth = get_authority_level(action_category)

    if auth["max_value_pln"] and estimated_value_pln > auth["max_value_pln"]:
        escalated_level = min(auth["level"] + 1, NEVER_ALONE)
        log.info("authority_value_escalation",
                 category=action_category,
                 value=estimated_value_pln,
                 threshold=auth["max_value_pln"],
                 escalated_to=escalated_level)
        return {
            "authorized": False,
            "level": escalated_level,
            "reason": "value_exceeds_threshold",
        }

    if auth["auto_execute"]:
        return {
            "authorized": True,
            "level": auth["level"],
            "action": "execute",
        }

    if auth["level"] <= EXECUTE_REPORT:
        return {
            "authorized": True,
            "level": auth["level"],
            "action": "execute_and_report",
        }

    return {
        "authorized": False,
        "level": auth["level"],
        "action": "request_approval",
    }


def execute_with_authority(
    action_category: str,
    action_type: str,
    description: str,
    params: dict[str, Any] | None = None,
    estimated_value_pln: float = 0,
) -> dict[str, Any]:
    """Main entry point — replaces direct calls to propose_action.

    Checks authority level, auto-executes or requests approval accordingly.
    """
    params = params or {}
    auth_check = check_authority(action_category, estimated_value_pln)

    log.info("authority_check",
             category=action_category,
             action_type=action_type,
             authorized=auth_check["authorized"],
             level=auth_check.get("level"))

    if auth_check["authorized"]:
        # Level 0-1: auto-execute
        from app.orchestrator.action_pipeline import approve_action, propose_action

        action_id = propose_action(action_type, description, params, notify=False)
        result = approve_action(action_id)

        log_authority_action(
            action_category, auth_check["level"], description,
            auto_executed=True,
        )

        # Level 1: report to Sebastian
        if auth_check["level"] >= EXECUTE_REPORT:
            _send_whatsapp(
                f"\u2139\ufe0f Wykonano automatycznie:\n"
                f"{description[:300]}\n"
                f"Kategoria: {action_category}"
            )

        return {
            "status": "auto_executed",
            "action_id": action_id,
            "result": result,
        }

    # Level 2-4: request approval
    from app.orchestrator.action_pipeline import propose_action

    action_id = propose_action(action_type, description, params, notify=True)

    log_authority_action(
        action_category, auth_check["level"], description,
        approval_requested=True,
    )

    return {
        "status": "approval_requested",
        "action_id": action_id,
        "level": auth_check["level"],
    }


# ================================================================
# Logging
# ================================================================

def log_authority_action(
    action_category: str,
    level: int,
    description: str,
    auto_executed: bool = False,
    approval_requested: bool = False,
    approved: bool | None = None,
    approval_time_seconds: int | None = None,
):
    """Insert into authority_log."""
    _ensure_tables()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO authority_log
                       (action_category, authority_level, action_description,
                        auto_executed, approval_requested, approved,
                        approval_time_seconds)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (action_category, level, description[:1000],
                 auto_executed, approval_requested, approved,
                 approval_time_seconds),
            )
        conn.commit()

    log.info("authority_action_logged",
             category=action_category, level=level,
             auto_executed=auto_executed,
             approval_requested=approval_requested)


# ================================================================
# Management
# ================================================================

def update_authority_level(
    action_category: str,
    new_level: int,
    updated_by: str = "sebastian",
) -> dict[str, Any]:
    """Change authority level for a category."""
    if not 0 <= new_level <= 4:
        return {"error": f"Invalid level {new_level}, must be 0-4"}

    _ensure_tables()

    auto_execute = new_level <= EXECUTE_REPORT

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE authority_levels
                   SET authority_level = %s, auto_execute = %s,
                       created_by = %s, updated_at = NOW()
                   WHERE action_category = %s""",
                (new_level, auto_execute, updated_by, action_category),
            )
            updated = cur.rowcount
        conn.commit()

    if updated == 0:
        return {"error": f"Category '{action_category}' not found"}

    log.info("authority_level_updated",
             category=action_category, new_level=new_level,
             updated_by=updated_by)

    return {
        "category": action_category,
        "new_level": new_level,
        "auto_execute": auto_execute,
        "updated_by": updated_by,
    }


def get_approval_stats(days: int = 90) -> dict[str, Any]:
    """Analyze approval patterns and suggest level changes."""
    _ensure_tables()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT
                       action_category,
                       COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE approved = TRUE) AS approved_count,
                       COUNT(*) FILTER (WHERE approved = FALSE) AS rejected_count,
                       ROUND(AVG(approval_time_seconds) FILTER
                           (WHERE approval_time_seconds IS NOT NULL)) AS avg_time
                   FROM authority_log
                   WHERE created_at > NOW() - INTERVAL '%s days'
                     AND approval_requested = TRUE
                   GROUP BY action_category
                   ORDER BY total DESC""",
                (days,),
            )
            stats_rows = cur.fetchall()

            cur.execute(
                """SELECT action_category, authority_level
                   FROM authority_levels ORDER BY action_category""",
            )
            level_map = {r[0]: r[1] for r in cur.fetchall()}

    by_category = {}
    suggestions = []

    for row in stats_rows:
        cat, total, approved, rejected, avg_time = row
        rate = approved / total if total > 0 else 0.0
        current_level = level_map.get(cat, QUICK_APPROVAL)

        entry = {
            "total": total,
            "approved": approved,
            "rejected": rejected,
            "approval_rate": round(rate, 2),
            "avg_approval_time_seconds": int(avg_time) if avg_time else None,
        }

        # Suggest level changes based on approval rate
        if rate >= 0.95 and total >= 10 and current_level >= QUICK_APPROVAL:
            suggested = max(current_level - 1, INFORM)
            entry["suggestion"] = (
                f"Consider upgrading to level {suggested} "
                f"({int(rate * 100)}% approval rate)"
            )
            suggestions.append({
                "category": cat,
                "current_level": current_level,
                "suggested_level": suggested,
                "reason": (
                    f"{int(rate * 100)}% approval rate over {days} days "
                    f"({approved}/{total} approved)"
                ),
            })
        elif current_level == NEVER_ALONE:
            suggestions.append({
                "category": cat,
                "current_level": current_level,
                "suggested_level": NEVER_ALONE,
                "reason": "Keep at level 4 — high impact decisions",
            })

        by_category[cat] = entry

    return {
        "by_category": by_category,
        "suggestions": suggestions,
        "period_days": days,
    }


def list_authority_levels() -> list[dict[str, Any]]:
    """Return all categories with their levels, sorted by level then category."""
    _ensure_tables()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT action_category, authority_level, description,
                       auto_execute, require_digest, max_value_pln
                FROM authority_levels
                ORDER BY authority_level, action_category
            """)
            return [
                {
                    "category": r[0],
                    "level": r[1],
                    "description": r[2],
                    "auto_execute": r[3],
                    "require_digest": r[4],
                    "max_value_pln": float(r[5]) if r[5] is not None else None,
                }
                for r in cur.fetchall()
            ]


# ================================================================
# WhatsApp
# ================================================================

def _send_whatsapp(message: str):
    """Send WhatsApp message via OpenClaw."""
    try:
        subprocess.run(
            [OPENCLAW_BIN, "message", "send", "--channel", "whatsapp",
             "--target", WA_TARGET, "--message", message],
            capture_output=True, text=True, timeout=30,
        )
    except Exception:
        log.warning("whatsapp_send_failed", message_len=len(message))


# ================================================================
# WhatsApp command handler
# ================================================================

def handle_authority_command(text: str) -> dict[str, Any] | None:
    """Handle authority level changes from WhatsApp.

    Format: authority [category] [0-4]
    Example: authority send_email_new 1
    """
    text_lower = text.lower().strip()

    match = re.match(r"authority\s+(\S+)\s+([0-4])", text_lower)
    if not match:
        return None

    category = match.group(1)
    new_level = int(match.group(2))

    result = update_authority_level(category, new_level, updated_by="sebastian_whatsapp")

    if "error" not in result:
        _send_whatsapp(
            f"\u2705 Authority updated:\n"
            f"{category} -> level {new_level}"
        )

    return result


# ================================================================
# CLI
# ================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--stats":
        result = get_approval_stats()
    elif len(sys.argv) > 1 and sys.argv[1] == "--list":
        result = list_authority_levels()
    else:
        result = get_approval_stats()

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
