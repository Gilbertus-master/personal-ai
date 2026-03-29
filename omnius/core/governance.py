"""Omnius Governance Layer — controls what CEO and board can modify.

Rules:
1. CEO/board CAN create new features — only if Omnius validates added value
2. CEO/board CAN improve existing features
3. CEO/board CANNOT delete features or reduce functionality
4. CEO/board CANNOT reduce Omnius's data access scope
5. Non-regression: every change must pass baseline check
6. Rules are role-bound, not person-bound — CEO/board members may change

Gilbertus (gilbertus_admin, level 99) bypasses all governance checks.
"""
from __future__ import annotations

import json
import os
from typing import Any

import structlog
from anthropic import Anthropic

from omnius.db.postgres import get_pg_connection

log = structlog.get_logger(__name__)

ANTHROPIC_MODEL = os.getenv("OMNIUS_LLM_MODEL", "claude-haiku-4-5")

# Actions that are NEVER allowed for CEO/board
FORBIDDEN_ACTIONS = {
    "delete_feature",
    "remove_data_source",
    "reduce_data_scope",
    "delete_role",
    "delete_permission",
    "downgrade_role",
    "disable_sync",
    "disable_cron",
    "remove_endpoint",
    "delete_plugin",
}

# Config keys that CEO/board cannot modify (Gilbertus-only)
PROTECTED_CONFIG_KEYS = {
    "rbac:permissions:",     # Cannot change RBAC from inside
    "governance:",           # Cannot modify governance rules
    "data_sources:",         # Cannot reduce data sources
    "sync:schedule:",        # Cannot disable syncs
    "prompt:system",         # Cannot change system prompts
}


class GovernanceViolation(Exception):
    """Raised when an action violates governance rules."""
    pass


def check_governance(user: dict[str, Any], action: str,
                     params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Check if an action is allowed under governance rules.

    Returns: {"allowed": bool, "reason": str, "requires_value_check": bool}

    Gilbertus_admin (level 99) always passes.
    CEO/board must pass governance checks.
    """
    role_level = user.get("role_level", 0)
    role_name = user.get("role_name", "unknown")

    # Gilbertus bypasses all governance
    if role_level >= 99:
        return {"allowed": True, "reason": "gilbertus_admin bypass"}

    # Check forbidden actions
    if action in FORBIDDEN_ACTIONS:
        _log_violation(user, action, params, "forbidden_action")
        return {
            "allowed": False,
            "reason": f"Action '{action}' is not permitted for role '{role_name}'. "
                      f"Features cannot be deleted or reduced. Contact Gilbertus admin.",
        }

    # Check protected config keys
    if action in ("push_config", "update_config") and params:
        key = params.get("key", "")
        for protected in PROTECTED_CONFIG_KEYS:
            if key.startswith(protected):
                _log_violation(user, action, params, "protected_config")
                return {
                    "allowed": False,
                    "reason": f"Config key '{key}' is protected. Only Gilbertus admin can modify.",
                }

    # Feature creation requires value validation
    if action in ("create_feature", "propose_feature", "add_endpoint", "add_cron",
                  "deploy_plugin", "review_plugin"):
        return {
            "allowed": True,
            "reason": "pending_value_check",
            "requires_value_check": True,
        }

    # Feature improvement — allowed
    if action in ("improve_feature", "update_feature", "fix_bug"):
        return {"allowed": True, "reason": "improvements are allowed"}

    # Default: allowed for standard operations
    return {"allowed": True, "reason": "standard operation"}


def validate_value(proposal: str, user: dict[str, Any]) -> dict[str, Any]:
    """Use LLM to assess if a proposed feature generates added value.

    Returns: {"approved": bool, "value_score": float, "reasoning": str}
    """
    try:
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=500,
            system=(
                "Jesteś Omnius — korporacyjny AI dla firmy energetycznej. "
                "Oceniasz propozycje nowych funkcjonalności pod kątem wartości dodanej. "
                "Odpowiedz TYLKO w formacie JSON: "
                '{"approved": true/false, "value_score": 0.0-1.0, '
                '"reasoning": "krótkie uzasadnienie po polsku"}'
                "\n\nKryteria oceny:"
                "\n- Czy funkcjonalność rozwiązuje realny problem biznesowy?"
                "\n- Czy generuje oszczędności, przychody lub lepsze decyzje?"
                "\n- Czy nie duplikuje istniejącej funkcjonalności?"
                "\n- Czy effort jest proporcjonalny do wartości?"
                "\n\nOdrzuć propozycje które: są trywialne, duplikują istniejące, "
                "nie mają jasnego ROI, lub próbują zmienić fundamentalną architekturę."
            ),
            messages=[{
                "role": "user",
                "content": f"Propozycja od {user.get('role_name', 'unknown')} "
                           f"({user.get('display_name', 'Unknown')}):\n\n{proposal}",
            }],
        )

        result_text = response.content[0].text.strip()

        # Parse JSON — handle LLM returning markdown-wrapped JSON
        try:
            result = json.loads(result_text)
        except json.JSONDecodeError:
            # Try extracting JSON from markdown code block
            import re
            json_match = re.search(r'\{[^{}]*"approved"[^{}]*\}', result_text)
            if json_match:
                result = json.loads(json_match.group())
            else:
                log.warning("governance_llm_unparseable", response=result_text[:300])
                result = {
                    "approved": False,
                    "value_score": 0.0,
                    "reasoning": "Omnius nie mógł ocenić propozycji (nieparsowalna odpowiedź LLM). "
                                 "Wymagana ręczna akceptacja Gilbertusa.",
                }

        # Validate required fields
        if "approved" not in result:
            result["approved"] = False
        if "value_score" not in result:
            result["value_score"] = 0.0

        # Log the assessment
        _log_value_assessment(user, proposal, result)

        return result

    except Exception as e:
        log.error("value_validation_failed", error=str(e))
        # On error, require Gilbertus approval
        return {
            "approved": False,
            "value_score": 0.0,
            "reasoning": f"Automatyczna ocena nie powiodła się ({e}). "
                         f"Wymagana ręczna akceptacja Gilbertusa.",
        }


def check_non_regression(changes: dict[str, Any]) -> dict[str, Any]:
    """Verify that proposed changes don't reduce existing capabilities.

    Baselines stored in omnius_baselines table (immutable — INSERT only, no UPDATE/DELETE
    allowed for non-admin roles via DB trigger).
    """
    violations = []

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Ensure baseline table exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS omnius_baselines (
                    id SERIAL PRIMARY KEY,
                    metric TEXT NOT NULL,
                    value NUMERIC NOT NULL,
                    recorded_by TEXT DEFAULT 'gilbertus',
                    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            conn.commit()

            # Get latest baseline per metric
            cur.execute("""
                SELECT DISTINCT ON (metric) metric, value
                FROM omnius_baselines
                ORDER BY metric, recorded_at DESC
            """)
            baselines = {row[0]: float(row[1]) for row in cur.fetchall()}

    # Auto-collect active_plugins count if not already in changes
    if "active_plugins" not in changes:
        try:
            with get_pg_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT COUNT(*) FROM omnius_plugins WHERE status = 'active'"
                    )
                    row = cur.fetchone()
                    if row:
                        changes["active_plugins"] = row[0]
        except Exception:
            pass  # Table may not exist yet

    if not baselines:
        return {"passed": True, "reason": "No baseline yet — first deployment"}

    for metric, baseline_value in baselines.items():
        current = changes.get(metric)
        if current is not None:
            try:
                if float(current) < baseline_value:
                    violations.append(
                        f"{metric}: was {baseline_value}, now {current} (regression)"
                    )
            except (ValueError, TypeError):
                pass

    if violations:
        return {
            "passed": False,
            "violations": violations,
            "reason": "Non-regression check failed: " + "; ".join(violations),
        }

    return {"passed": True, "reason": "All baselines maintained"}


def save_baseline(metrics: dict[str, Any]):
    """Save current state as non-regression baseline.

    INSERT-only — new baselines don't overwrite old ones.
    Historical baselines preserved for audit trail.
    """
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS omnius_baselines (
                    id SERIAL PRIMARY KEY,
                    metric TEXT NOT NULL,
                    value NUMERIC NOT NULL,
                    recorded_by TEXT DEFAULT 'gilbertus',
                    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            for key, value in metrics.items():
                try:
                    cur.execute("""
                        INSERT INTO omnius_baselines (metric, value, recorded_by)
                        VALUES (%s, %s, 'gilbertus')
                    """, (key, float(value)))
                except (ValueError, TypeError):
                    log.warning("baseline_skip_non_numeric", metric=key, value=str(value))
        conn.commit()


def _log_violation(user: dict, action: str, params: dict | None, violation_type: str):
    """Log governance violation to audit log."""
    log.warning("governance_violation",
                user=user.get("email", user.get("api_key_name")),
                role=user.get("role_name"),
                action=action,
                violation_type=violation_type,
                params=str(params)[:200] if params else None)

    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO omnius_audit_log
                        (user_id, action, resource, request_summary, result_status)
                    VALUES (%s, %s, %s, %s, 'governance_violation')
                """, (
                    user.get("user_id"),
                    f"governance:{violation_type}",
                    action,
                    json.dumps({"params": params, "type": violation_type}),
                ))
            conn.commit()
    except Exception as audit_err:
        log.error("governance_audit_failed", error=str(audit_err))


def _log_value_assessment(user: dict, proposal: str, result: dict):
    """Log value assessment to audit log."""
    log.info("value_assessment",
             user=user.get("email"),
             approved=result.get("approved"),
             score=result.get("value_score"),
             reasoning=result.get("reasoning", "")[:200])

    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO omnius_audit_log
                        (user_id, action, resource, request_summary, result_status)
                    VALUES (%s, 'governance:value_assessment', %s, %s, %s)
                """, (
                    user.get("user_id"),
                    proposal[:500],
                    json.dumps(result),
                    "approved" if result.get("approved") else "rejected",
                ))
            conn.commit()
    except Exception as audit_err:
        log.error("governance_audit_failed", error=str(audit_err))
